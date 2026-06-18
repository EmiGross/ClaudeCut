"""
transcribe.py - Zweisprachige (DE/EN) Transkription fuer Premiere / ClaudeCut.

Geht die Audiospur in Fenstern durch, erkennt pro Fenster die Sprache
(Deutsch/Englisch) selbst und transkribiert jeweils im Original. Gibt
Wort-Timestamps als SRT (fuer Premiere-Import) + JSON aus, plus eine
Uebersicht, welches Fenster welche Sprache hat.

ClaudeCut ruft das pro Clip einzeln auf -> die JSON-Timestamps sind dann
clip-relativ (genau das, was die EDL pro Quelldatei braucht).

Aufruf:
    python transcribe.py "D:\\Video\\...\\clip.mov"
    python transcribe.py "D:\\...\\clip.mov" --langs de en --model large-v3

Output liegt neben der Datei: <name>.srt, <name>.json, <name>.segments.txt

Modell-Cache: per Umgebungsvariable CLAUDECUT_WHISPER_MODELS setzbar
(sonst der unten stehende Default-Pfad).
"""

import argparse
import json
import os
import sys

# --- CUDA-Bibliotheken (cuBLAS/cuDNN) aus den pip-Paketen auf den PATH legen,
#     damit CTranslate2 die GPU findet. -----------------------------------------
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

# Modell-Cache: per env überschreibbar (andere Nutzer: anpassen). Leer/None ->
# faster-whisper nutzt den Standard-HF-Cache (~/.cache/huggingface).
MODEL_DIR = os.environ.get("CLAUDECUT_WHISPER_MODELS", r"F:\Anwendungen\Whisper\models")
SR = 16000
WINDOW_SEC = 30.0  # Granularitaet der Sprach-Erkennung


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
    ap.add_argument("audio", help="Pfad zur Audiodatei (WAV/MP3/...)")
    ap.add_argument("--langs", nargs="+", default=["de", "en"],
                    help="Erlaubte Sprachen (Default: de en)")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--compute_type", default="float16")
    args = ap.parse_args()

    audio_path = args.audio
    if not os.path.isfile(audio_path):
        sys.exit(f"Datei nicht gefunden: {audio_path}")

    base = os.path.splitext(audio_path)[0]
    allowed = set(args.langs)

    print(f"Lade Modell {args.model} auf {args.device} ...", flush=True)
    try:
        model = WhisperModel(args.model, device=args.device,
                             compute_type=args.compute_type,
                             download_root=MODEL_DIR)
    except Exception as e:
        print(f"GPU-Init fehlgeschlagen ({e}). Fallback auf CPU.", flush=True)
        model = WhisperModel(args.model, device="cpu",
                             compute_type="int8", download_root=MODEL_DIR)

    print("Dekodiere Audio ...", flush=True)
    audio = decode_audio(audio_path, sampling_rate=SR)
    total_sec = len(audio) / SR
    print(f"Laenge: {total_sec/60:.1f} min", flush=True)

    all_segments = []
    win_overview = []
    win_samples = int(WINDOW_SEC * SR)
    n_windows = (len(audio) + win_samples - 1) // win_samples

    for wi in range(n_windows):
        start_s = wi * win_samples
        chunk = audio[start_s:start_s + win_samples]
        offset = start_s / SR

        # Sprache fuer dieses Fenster erkennen, auf erlaubte Sprachen begrenzen.
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

    # --- SRT schreiben ---
    srt_path = base + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, s in enumerate(all_segments, 1):
            f.write(f"{i}\n{fmt_ts(s['start'])} --> {fmt_ts(s['end'])}\n"
                    f"{s['text']}\n\n")

    # --- JSON (Wort-Timestamps) ---
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_segments, f, ensure_ascii=False, indent=2)

    # --- Sprach-Uebersicht pro Fenster ---
    seg_path = base + ".segments.txt"
    with open(seg_path, "w", encoding="utf-8") as f:
        for offset, lang, prob in win_overview:
            f.write(f"{fmt_ts(offset)}\t{lang}\t{prob:.2f}\n")

    print("\nFertig:")
    print(f"  SRT : {srt_path}")
    print(f"  JSON: {json_path}")
    print(f"  Sprachen pro Fenster: {seg_path}")


if __name__ == "__main__":
    main()
