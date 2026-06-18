"""
ClaudeCut — prep.py: the front end of the pipeline.

Takes a folder full of clips and prepares everything so Claude (in chat) can make
the editorial selection:

  Folder of clips
    ├─ per clip: faster-whisper → <clip>.json (word timestamps)
    ├─ per clip: ffprobe → fps / resolution / aspect / duration / audio channels
    └─ writes:
         transcripts.md   — all transcripts with timecodes (Claude reads this)
         cut.py           — scaffold: briefing + suggested sequence format +
                            empty EDL + clip catalog (Claude fills the EDL)

After that:  fill the EDL in cut.py  →  `python build_xml.py`  →  cut.xml for Premiere.

Usage:
    python prep.py "D:\\Video\\Example\\Footage"
    python prep.py "D:\\...\\Footage" --briefing "90-sec recap, casual, best lines" --langs de en

Note: prep.py runs in the ClaudeCut venv and calls Whisper through its own venv
Python (subprocess) — the environments stay separate. Already existing <clip>.json
files are skipped (cache), so re-running is cheap.
"""

import argparse
import json
import pathlib
import subprocess
import sys
from collections import Counter
from fractions import Fraction

# Force the Windows console to UTF-8 (otherwise print() crashes on →/×/⚠️ under cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).parent

# Whisper setup: paths come from config.py (overridable via env, see docs/SETUP.md)
from config import TRANSCRIBE_SCRIPT as WHISPER_SCRIPT  # noqa: E402
from config import WHISPER_PYTHON as WHISPER_PY  # noqa: E402

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mxf", ".mts", ".m2ts"}

OUT_TRANSCRIPTS = ROOT / "transcripts.md"
OUT_CUT = ROOT / "cut.py"


# --- ffprobe helper (like in build_xml.py, here tolerant of missing audio) ----
def _ffprobe(path, stream, entries):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", entries,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return out.stdout.strip().splitlines()


def media_info(path: pathlib.Path) -> dict:
    """fps / resolution / duration / audio channels of a clip — for the sequence format."""
    num, den = _ffprobe(path, "v:0", "stream=r_frame_rate")[0].split("/")
    rate = float(Fraction(int(num), int(den)))
    w = int(_ffprobe(path, "v:0", "stream=width")[0])
    h = int(_ffprobe(path, "v:0", "stream=height")[0])
    dur = float(_ffprobe(path, "", "format=duration")[0]) if _ffprobe(path, "", "format=duration") else 0.0
    ch_lines = _ffprobe(path, "a:0", "stream=channels")
    channels = int(ch_lines[0]) if ch_lines else 0
    return {"rate": rate, "width": w, "height": h, "dur": dur, "channels": channels}


def fps_label(rate: float) -> str:
    """Make odd rates readable (29.97, 23.976 ...). Nearest standard rate, tight
    tolerance — otherwise 30 gets wrongly labeled as 29.97 (Δ=0.03)."""
    std = min((23.976, 24, 25, 29.97, 30, 50, 59.94, 60), key=lambda s: abs(s - rate))
    return f"{std:g}" if abs(std - rate) < 0.02 else f"{rate:.3f}"


def aspect_label(w: int, h: int) -> str:
    from math import gcd
    g = gcd(w, h) or 1
    aw, ah = w // g, h // g
    common = {(16, 9): "16:9", (9, 16): "9:16", (4, 3): "4:3", (1, 1): "1:1", (21, 9): "21:9"}
    return common.get((aw, ah), f"{aw}:{ah}")


# --- Transcription -----------------------------------------------------------
def transcribe(clip: pathlib.Path, langs) -> pathlib.Path:
    """Calls transcribe.py in the Whisper venv. Skips finished .json (cache)."""
    json_path = clip.with_suffix(".json")
    if json_path.exists():
        print(f"  [skip] {clip.name}  (transcript exists)")
        return json_path
    print(f"  [whisper] {clip.name} ...", flush=True)
    subprocess.run(
        [str(WHISPER_PY), str(WHISPER_SCRIPT), str(clip), "--langs", *langs],
        check=True)
    return json_path


def load_segments(json_path: pathlib.Path):
    if not json_path.exists():
        return []
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


# --- Suggest sequence format -------------------------------------------------
def suggest_sequence(infos: dict):
    """Suggests a target sequence format from the measured clips + warnings."""
    res = Counter((i["width"], i["height"]) for i in infos.values())
    fps = Counter(round(i["rate"], 3) for i in infos.values())
    orient = Counter("portrait" if i["height"] > i["width"] else "landscape"
                     for i in infos.values())

    (sw, sh), _ = res.most_common(1)[0]
    # fps: on a mix, suggest the lowest as a safe delivery default
    seq_fps = int(round(min(fps)))
    warnings = []
    if len(res) > 1:
        warnings.append(f"MIXED resolutions: {dict(res)} → suggestion = most common ({sw}×{sh})")
    if len(fps) > 1:
        warnings.append(f"MIXED fps: {dict(fps)} → suggestion = lowest ({seq_fps}); "
                        f"60→30 is clean, odd rates (29.97/23.976) may need NTSC")
    if len(orient) > 1:
        warnings.append(f"MIXED orientation: {dict(orient)} → 16:9 OR 9:16? "
                        f"the user must decide")
    return sw, sh, seq_fps, warnings


# --- Write transcripts.md ----------------------------------------------------
def write_transcripts(clips, infos, briefing, seq, warnings):
    sw, sh, seq_fps = seq
    with open(OUT_TRANSCRIPTS, "w", encoding="utf-8") as f:
        f.write("# ClaudeCut — transcripts & footage overview\n\n")
        f.write(f"**Briefing:** {briefing or '(none yet — set it with --briefing on the run)'}\n\n")
        f.write(f"**Sequence suggestion:** {sw}×{sh}, {seq_fps} fps, "
                f"{aspect_label(sw, sh)}\n\n")
        if warnings:
            f.write("> ⚠️ **Clarify before building:**\n")
            for w in warnings:
                f.write(f"> - {w}\n")
            f.write("\n")
        f.write("## Clip overview\n\n")
        f.write("| # | File | Resolution | fps | Aspect | Duration | Audio |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for i, clip in enumerate(clips, 1):
            info = infos[clip.name]
            f.write(f"| {i} | `{clip.name}` | {info['width']}×{info['height']} | "
                    f"{fps_label(info['rate'])} | {aspect_label(info['width'], info['height'])} | "
                    f"{info['dur']:.1f}s | {info['channels']}ch |\n")
        f.write("\n---\n\n## Transcripts (timecodes clip-relative, in seconds)\n\n")
        for clip in clips:
            segs = load_segments(clip.with_suffix(".json"))
            f.write(f"### `{clip.name}`\n\n")
            if not segs:
                f.write("_(no transcript — silent or Whisper failed)_\n\n")
                continue
            for s in segs:
                f.write(f"- `[{s['start']:.2f}–{s['end']:.2f}]` ({s.get('lang','?')}) "
                        f"{s['text']}\n")
            f.write("\n")
    print(f"\nWritten: {OUT_TRANSCRIPTS}")


# --- Write cut.py scaffold (only if not present) -----------------------------
def write_cut_scaffold(clips_dir, clips, infos, briefing, seq):
    if OUT_CUT.exists():
        print(f"Note: {OUT_CUT.name} already exists → NOT overwritten "
              f"(your EDL stays). Adjust by hand or delete if needed.")
        return
    sw, sh, seq_fps = seq
    catalog = "\n".join(
        f'#   "{c.name}"  ({infos[c.name]["width"]}×{infos[c.name]["height"]}, '
        f'{fps_label(infos[c.name]["rate"])} fps, {infos[c.name]["dur"]:.1f}s)'
        for c in clips)
    content = f'''"""
cut.py — the cut job (generated by prep.py, EDL filled by Claude).

Seconds as the unit (clip-relative, like in transcripts.md). build_xml.py reads
this file and builds cut.xml from it. Adjust the sequence format to the footage.
"""

from pathlib import Path

# Footage folder (absolute paths; build_xml.py references the clips from here)
CLIPS_DIR = Path(r"{clips_dir}")

BRIEFING = {briefing!r}

# Target sequence format — suggestion from prep.py, check before building.
SEQ_FPS = {seq_fps}
SEQ_W, SEQ_H = {sw}, {sh}

# Available clips (catalog — copy the names into the EDL):
{catalog}

# (filename, in-second, out-second, reason) — filled by Claude.
EDL = [
]

# Deliberately NOT used (documented for the cut plan):
DROPPED = [
]
'''
    OUT_CUT.write_text(content, encoding="utf-8")
    print(f"Written: {OUT_CUT}  (EDL still empty — fill it now)")


def main():
    ap = argparse.ArgumentParser(description="ClaudeCut prep: clips → transcripts + cut.py")
    ap.add_argument("folder", help="Folder with the clips")
    ap.add_argument("--briefing", default="", help="One sentence: what should it become?")
    ap.add_argument("--langs", nargs="+", default=["de", "en"], help="Whisper languages")
    args = ap.parse_args()

    folder = pathlib.Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"Folder not found: {folder}")
    if not WHISPER_PY.exists():
        sys.exit(f"Whisper Python not found: {WHISPER_PY}")

    clips = sorted(p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if not clips:
        sys.exit(f"No video files in {folder} "
                 f"(looked for: {', '.join(sorted(VIDEO_EXTS))})")

    print(f"{len(clips)} clip(s) in {folder}\n")
    print("1) Measuring metadata (ffprobe) ...")
    infos = {c.name: media_info(c) for c in clips}
    for c in clips:
        i = infos[c.name]
        print(f"  {c.name[:40]:40s} {i['width']}×{i['height']} "
              f"{fps_label(i['rate'])}fps {aspect_label(i['width'], i['height'])} "
              f"{i['dur']:.1f}s {i['channels']}ch")

    print("\n2) Transcribing (Whisper, already existing ones are skipped) ...")
    for c in clips:
        transcribe(c, args.langs)

    print("\n3) Suggesting sequence format ...")
    sw, sh, seq_fps, warnings = suggest_sequence(infos)
    print(f"  Suggestion: {sw}×{sh}, {seq_fps} fps, {aspect_label(sw, sh)}")
    for w in warnings:
        print(f"  ⚠️  {w}")

    print("\n4) Writing outputs ...")
    write_transcripts(clips, infos, args.briefing, (sw, sh, seq_fps), warnings)
    write_cut_scaffold(folder.resolve(), clips, infos, args.briefing, (sw, sh, seq_fps))

    print("\nDone. Next steps:")
    print(f"  • read transcripts.md → pick soundbites")
    print(f"  • fill the EDL in cut.py")
    print(f"  • python build_xml.py   → cut.xml for Premiere")


if __name__ == "__main__":
    main()
