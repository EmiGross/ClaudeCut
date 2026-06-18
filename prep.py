"""
ClaudeCut — prep.py: das Vorderteil der Pipeline.

Nimmt einen Ordner voller Clips und bereitet alles vor, damit Claude (im Chat)
die inhaltliche Auswahl treffen kann:

  Ordner Clips
    ├─ pro Clip: faster-whisper (F:\\Anwendungen\\Whisper) → <clip>.json (Wort-Timestamps)
    ├─ pro Clip: ffprobe → fps / Auflösung / Seitenverhältnis / Dauer / Audiokanäle
    └─ schreibt:
         transcripts.md   — alle Transkripte mit Timecodes (Claude liest das)
         cut.py           — Scaffold: Briefing + vorgeschlagenes Sequenzformat +
                            leere EDL + Clip-Katalog (Claude füllt die EDL)

Danach:  EDL in cut.py füllen  →  `python build_xml.py`  →  schnitt.xml für Premiere.

Aufruf:
    python prep.py "D:\\Video\\ChinaTrip\\Footage"
    python prep.py "D:\\...\\Footage" --briefing "90-Sek-Recap, locker, beste Aussagen" --langs de en

Hinweis: prep.py läuft im ClaudeCut-venv und ruft Whisper über dessen eigenes
venv-Python auf (subprocess) — die Umgebungen bleiben getrennt. Schon vorhandene
<clip>.json werden übersprungen (Cache), erneutes Laufen ist also billig.
"""

import argparse
import json
import pathlib
import subprocess
import sys
from collections import Counter
from fractions import Fraction

# Windows-Konsole auf UTF-8 (sonst crasht print() an →/×/⚠️ unter cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).parent

# Whisper-Setup: Pfade kommen aus config.py (per env überschreibbar, siehe docs/SETUP.md)
from config import TRANSCRIBE_SCRIPT as WHISPER_SCRIPT  # noqa: E402
from config import WHISPER_PYTHON as WHISPER_PY  # noqa: E402

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mxf", ".mts", ".m2ts"}

OUT_TRANSCRIPTS = ROOT / "transcripts.md"
OUT_CUT = ROOT / "cut.py"


# --- ffprobe-Helfer (wie in build_xml.py, hier tolerant ggü. fehlendem Audio) -
def _ffprobe(path, stream, entries):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", entries,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return out.stdout.strip().splitlines()


def media_info(path: pathlib.Path) -> dict:
    """fps / Auflösung / Dauer / Audiokanäle eines Clips — fürs Sequenz-Format."""
    num, den = _ffprobe(path, "v:0", "stream=r_frame_rate")[0].split("/")
    rate = float(Fraction(int(num), int(den)))
    w = int(_ffprobe(path, "v:0", "stream=width")[0])
    h = int(_ffprobe(path, "v:0", "stream=height")[0])
    dur = float(_ffprobe(path, "", "format=duration")[0]) if _ffprobe(path, "", "format=duration") else 0.0
    ch_lines = _ffprobe(path, "a:0", "stream=channels")
    channels = int(ch_lines[0]) if ch_lines else 0
    return {"rate": rate, "width": w, "height": h, "dur": dur, "channels": channels}


def fps_label(rate: float) -> str:
    """Krumme Raten lesbar machen (29.97, 23.976 ...). Nächste Standardrate,
    enge Toleranz — sonst wird 30 fälschlich als 29.97 gelabelt (Δ=0.03)."""
    std = min((23.976, 24, 25, 29.97, 30, 50, 59.94, 60), key=lambda s: abs(s - rate))
    return f"{std:g}" if abs(std - rate) < 0.02 else f"{rate:.3f}"


def aspect_label(w: int, h: int) -> str:
    from math import gcd
    g = gcd(w, h) or 1
    aw, ah = w // g, h // g
    common = {(16, 9): "16:9", (9, 16): "9:16", (4, 3): "4:3", (1, 1): "1:1", (21, 9): "21:9"}
    return common.get((aw, ah), f"{aw}:{ah}")


# --- Transkription -----------------------------------------------------------
def transcribe(clip: pathlib.Path, langs) -> pathlib.Path:
    """Ruft transcribe.py im Whisper-venv auf. Überspringt fertige .json (Cache)."""
    json_path = clip.with_suffix(".json")
    if json_path.exists():
        print(f"  [skip] {clip.name}  (Transkript existiert)")
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


# --- Sequenz-Format vorschlagen ----------------------------------------------
def suggest_sequence(infos: dict):
    """Schlägt aus den gemessenen Clips ein Ziel-Sequenzformat vor + Warnungen."""
    res = Counter((i["width"], i["height"]) for i in infos.values())
    fps = Counter(round(i["rate"], 3) for i in infos.values())
    orient = Counter("portrait" if i["height"] > i["width"] else "landscape"
                     for i in infos.values())

    (sw, sh), _ = res.most_common(1)[0]
    # fps: bei Mischung die niedrigste als sicheren Liefer-Default vorschlagen
    seq_fps = int(round(min(fps)))
    warnings = []
    if len(res) > 1:
        warnings.append(f"GEMISCHTE Auflösungen: {dict(res)} → Vorschlag = häufigste ({sw}×{sh})")
    if len(fps) > 1:
        warnings.append(f"GEMISCHTE fps: {dict(fps)} → Vorschlag = niedrigste ({seq_fps}); "
                        f"60→30 ist sauber, krumme (29.97/23.976) ggf. NTSC nötig")
    if len(orient) > 1:
        warnings.append(f"GEMISCHTE Ausrichtung: {dict(orient)} → 16:9 ODER 9:16? "
                        f"muss Emiliano entscheiden")
    return sw, sh, seq_fps, warnings


# --- transcripts.md schreiben ------------------------------------------------
def write_transcripts(clips, infos, briefing, seq, warnings):
    sw, sh, seq_fps = seq
    with open(OUT_TRANSCRIPTS, "w", encoding="utf-8") as f:
        f.write("# ClaudeCut — Transkripte & Footage-Übersicht\n\n")
        f.write(f"**Briefing:** {briefing or '(noch keins — beim Lauf mit --briefing setzen)'}\n\n")
        f.write(f"**Sequenz-Vorschlag:** {sw}×{sh}, {seq_fps} fps, "
                f"{aspect_label(sw, sh)}\n\n")
        if warnings:
            f.write("> ⚠️ **Vor dem Bauen klären:**\n")
            for w in warnings:
                f.write(f"> - {w}\n")
            f.write("\n")
        f.write("## Clip-Übersicht\n\n")
        f.write("| # | Datei | Auflösung | fps | Seiten | Dauer | Audio |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for i, clip in enumerate(clips, 1):
            info = infos[clip.name]
            f.write(f"| {i} | `{clip.name}` | {info['width']}×{info['height']} | "
                    f"{fps_label(info['rate'])} | {aspect_label(info['width'], info['height'])} | "
                    f"{info['dur']:.1f}s | {info['channels']}ch |\n")
        f.write("\n---\n\n## Transkripte (Timecodes clip-relativ, in Sekunden)\n\n")
        for clip in clips:
            segs = load_segments(clip.with_suffix(".json"))
            f.write(f"### `{clip.name}`\n\n")
            if not segs:
                f.write("_(kein Transkript — stumm oder Whisper fehlgeschlagen)_\n\n")
                continue
            for s in segs:
                f.write(f"- `[{s['start']:.2f}–{s['end']:.2f}]` ({s.get('lang','?')}) "
                        f"{s['text']}\n")
            f.write("\n")
    print(f"\nGeschrieben: {OUT_TRANSCRIPTS}")


# --- cut.py Scaffold schreiben (nur wenn nicht vorhanden) --------------------
def write_cut_scaffold(clips_dir, clips, infos, briefing, seq):
    if OUT_CUT.exists():
        print(f"Hinweis: {OUT_CUT.name} existiert schon → NICHT überschrieben "
              f"(deine EDL bleibt). Bei Bedarf von Hand anpassen oder löschen.")
        return
    sw, sh, seq_fps = seq
    catalog = "\n".join(
        f'#   "{c.name}"  ({infos[c.name]["width"]}×{infos[c.name]["height"]}, '
        f'{fps_label(infos[c.name]["rate"])} fps, {infos[c.name]["dur"]:.1f}s)'
        for c in clips)
    content = f'''"""
cut.py — der Schnitt-Auftrag (von prep.py erzeugt, EDL von Claude gefüllt).

Sekunden als Einheit (clip-relativ, wie in transcripts.md). build_xml.py liest
diese Datei und baut daraus schnitt.xml. Sequenzformat ggf. an Footage anpassen.
"""

from pathlib import Path

# Footage-Ordner (absolute Pfade; build_xml.py referenziert die Clips von hier)
CLIPS_DIR = Path(r"{clips_dir}")

BRIEFING = {briefing!r}

# Ziel-Sequenzformat — Vorschlag aus prep.py, vor dem Bauen prüfen.
SEQ_FPS = {seq_fps}
SEQ_W, SEQ_H = {sw}, {sh}

# Verfügbare Clips (Katalog — Namen in die EDL kopieren):
{catalog}

# (Dateiname, In-Sekunde, Out-Sekunde, Begründung) — von Claude gefüllt.
EDL = [
]

# Bewusst NICHT verwendet (für den Schnittplan dokumentiert):
DROPPED = [
]
'''
    OUT_CUT.write_text(content, encoding="utf-8")
    print(f"Geschrieben: {OUT_CUT}  (EDL noch leer — jetzt füllen)")


def main():
    ap = argparse.ArgumentParser(description="ClaudeCut-Vorbereitung: Clips → Transkripte + cut.py")
    ap.add_argument("folder", help="Ordner mit den Clips")
    ap.add_argument("--briefing", default="", help="Ein Satz: was soll es werden?")
    ap.add_argument("--langs", nargs="+", default=["de", "en"], help="Whisper-Sprachen")
    args = ap.parse_args()

    folder = pathlib.Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"Ordner nicht gefunden: {folder}")
    if not WHISPER_PY.exists():
        sys.exit(f"Whisper-Python nicht gefunden: {WHISPER_PY}")

    clips = sorted(p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if not clips:
        sys.exit(f"Keine Videodateien in {folder} "
                 f"(gesucht: {', '.join(sorted(VIDEO_EXTS))})")

    print(f"{len(clips)} Clip(s) in {folder}\n")
    print("1) Metadaten messen (ffprobe) ...")
    infos = {c.name: media_info(c) for c in clips}
    for c in clips:
        i = infos[c.name]
        print(f"  {c.name[:40]:40s} {i['width']}×{i['height']} "
              f"{fps_label(i['rate'])}fps {aspect_label(i['width'], i['height'])} "
              f"{i['dur']:.1f}s {i['channels']}ch")

    print("\n2) Transkribieren (Whisper, schon vorhandene werden übersprungen) ...")
    for c in clips:
        transcribe(c, args.langs)

    print("\n3) Sequenzformat vorschlagen ...")
    sw, sh, seq_fps, warnings = suggest_sequence(infos)
    print(f"  Vorschlag: {sw}×{sh}, {seq_fps} fps, {aspect_label(sw, sh)}")
    for w in warnings:
        print(f"  ⚠️  {w}")

    print("\n4) Ausgaben schreiben ...")
    write_transcripts(clips, infos, args.briefing, (sw, sh, seq_fps), warnings)
    write_cut_scaffold(folder.resolve(), clips, infos, args.briefing, (sw, sh, seq_fps))

    print("\nFertig. Nächste Schritte:")
    print(f"  • transcripts.md lesen → Soundbites wählen")
    print(f"  • EDL in cut.py füllen")
    print(f"  • python build_xml.py   → schnitt.xml für Premiere")


if __name__ == "__main__":
    main()
