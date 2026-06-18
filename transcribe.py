"""
transcribe.py - bilingual (DE/EN) transcription for Premiere / ClaudeCut.

Walks the audio track in windows, detects the language per window (German/English)
on its own and transcribes each in the original. Outputs word timestamps as SRT
(for Premiere import) + JSON, plus an overview of which window is which language.

ClaudeCut calls this per clip -> the JSON timestamps are then clip-relative
(exactly what the EDL needs per source file).

Usage:
    python transcribe.py "D:\\Video\\...\\clip.mov"
    python transcribe.py "D:\\...\\clip.mov" --langs de en --model large-v3

Output goes next to the file: <name>.srt, <name>.json, <name>.segments.txt

Model cache: set via the CLAUDECUT_WHISPER_MODELS environment variable
(otherwise the default path below).
"""

import argparse
import json
import os
import sys

# --- Put the CUDA libraries (cuBLAS/cuDNN) from the pip packages on the PATH so
#     that CTranslate2 finds the GPU. ------------------------------------------
def _add_cuda_to_path():
    import importlib.util
    for pkg in ("nvidia.cublas", "nvidia.cudnn"):
        spec = importlib.util.find_spec(pkg)
        if spec and spec.submodule_search_locations:
            binp = os.path.join(spec.submodule_search_locations[0], "bin")
            if os.path.isdir(binp):
                os.add_dll_directory(binp)
                os.environ["PATH"] = binp + os.pathsep + os.environ["PATH"]

_add_cuda_to_path()

from faster_whisper import WhisperModel, decode_audio  # noqa: E402

# Model cache: overridable via env (other users: adjust). Empty/None ->
# faster-whisper uses the default HF cache (~/.cache/huggingface).
MODEL_DIR = os.environ.get("CLAUDECUT_WHISPER_MODELS", r"F:\Anwendungen\Whisper\models")
SR = 16000
WINDOW_SEC = 30.0  # granularity of the language detection


def fmt_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", help="Path to the audio file (WAV/MP3/...)")
    ap.add_argument("--langs", nargs="+", default=["de", "en"],
                    help="Allowed languages (default: de en)")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--compute_type", default="float16")
    args = ap.parse_args()

    audio_path = args.audio
    if not os.path.isfile(audio_path):
        sys.exit(f"File not found: {audio_path}")

    base = os.path.splitext(audio_path)[0]
    allowed = set(args.langs)

    print(f"Loading model {args.model} on {args.device} ...", flush=True)
    try:
        model = WhisperModel(args.model, device=args.device,
                             compute_type=args.compute_type,
                             download_root=MODEL_DIR)
    except Exception as e:
        print(f"GPU init failed ({e}). Falling back to CPU.", flush=True)
        model = WhisperModel(args.model, device="cpu",
                             compute_type="int8", download_root=MODEL_DIR)

    print("Decoding audio ...", flush=True)
    audio = decode_audio(audio_path, sampling_rate=SR)
    total_sec = len(audio) / SR
    print(f"Length: {total_sec/60:.1f} min", flush=True)

    all_segments = []
    win_overview = []
    win_samples = int(WINDOW_SEC * SR)
    n_windows = (len(audio) + win_samples - 1) // win_samples

    for wi in range(n_windows):
        start_s = wi * win_samples
        chunk = audio[start_s:start_s + win_samples]
        offset = start_s / SR

        # Detect the language for this window, restrict to allowed languages.
        lang, prob, all_probs = model.detect_language(chunk)
        if lang not in allowed:
            lang = max(allowed, key=lambda L: dict(all_probs).get(L, 0.0))
        win_overview.append((offset, lang, prob))
        print(f"  [{fmt_ts(offset)}] -> {lang} ({prob:.2f})", flush=True)

        segs, _ = model.transcribe(
            chunk, language=lang, word_timestamps=True,
            vad_filter=True, beam_size=5,
            condition_on_previous_text=False,
        )
        for s in segs:
            words = [
                {"start": round(w.start + offset, 3),
                 "end": round(w.end + offset, 3),
                 "word": w.word}
                for w in (s.words or [])
            ]
            all_segments.append({
                "start": round(s.start + offset, 3),
                "end": round(s.end + offset, 3),
                "lang": lang,
                "text": s.text.strip(),
                "words": words,
            })

    # --- Write SRT ---
    srt_path = base + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, s in enumerate(all_segments, 1):
            f.write(f"{i}\n{fmt_ts(s['start'])} --> {fmt_ts(s['end'])}\n"
                    f"{s['text']}\n\n")

    # --- JSON (word timestamps) ---
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_segments, f, ensure_ascii=False, indent=2)

    # --- Language overview per window ---
    seg_path = base + ".segments.txt"
    with open(seg_path, "w", encoding="utf-8") as f:
        for offset, lang, prob in win_overview:
            f.write(f"{fmt_ts(offset)}\t{lang}\t{prob:.2f}\n")

    print("\nDone:")
    print(f"  SRT : {srt_path}")
    print(f"  JSON: {json_path}")
    print(f"  languages per window: {seg_path}")


if __name__ == "__main__":
    main()
