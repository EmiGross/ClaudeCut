# Setup

ClaudeCut needs **three** things: ffmpeg, a Whisper venv (GPU recommended) and an
otio venv. Sounds like a lot — it's a one-time thing.

## 0. Prerequisites

- **Python 3.12**
- **ffmpeg** installed and on the `PATH` (ships `ffprobe` with it). Test: `ffprobe -version`.
- **NVIDIA GPU** for fast Whisper (optional — there's a CPU fallback, but it's slow).
- **Claude Code** — it makes the editorial selection (see README, "the brain").

## 1. otio venv (for `build_xml.py` / `prep.py`)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt   # opentimelineio + otio-fcp-adapter
```

`prep.py` and `build_xml.py` run in this venv.

## 2. Whisper venv (for transcription)

Deliberately **separate** — faster-whisper pulls in CUDA packages.

```bash
python -m venv whisper-venv
whisper-venv\Scripts\activate
pip install faster-whisper
# for GPU additionally (CUDA 12):
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

The `large-v3` model (~3 GB) downloads automatically into the cache on first run.

## 3. Wire up the paths (`config.py`)

`prep.py` calls Whisper through the Whisper venv's Python. Either edit `config.py`
**or** set environment variables (no code edit):

| Variable | Meaning | Default |
|---|---|---|
| `CLAUDECUT_WHISPER_PY` | Python of the Whisper venv | `F:\Anwendungen\Whisper\venv\Scripts\python.exe` |
| `CLAUDECUT_TRANSCRIBE` | Whisper script | the vendored `transcribe.py` |
| `CLAUDECUT_WHISPER_MODELS` | model cache | `F:\Anwendungen\Whisper\models` |

Example (PowerShell):
```powershell
$env:CLAUDECUT_WHISPER_PY = "C:\path\whisper-venv\Scripts\python.exe"
$env:CLAUDECUT_WHISPER_MODELS = "C:\path\models"
```

## 4. Test

```bash
python prep.py "path\to\a\test-folder" --briefing "short test"
```

Expectation: one `.json` per clip (next to the clip), plus `transcripts.md` +
`cut.py` in the project folder, plus a sequence-format suggestion in the console.

## Troubleshooting

- **"Whisper Python not found"** → `CLAUDECUT_WHISPER_PY` points nowhere.
- **`ffprobe` not found** → ffmpeg not on the PATH.
- **GPU init failed** → falls back to CPU (int8) automatically; slower, but it runs.
- **Premiere won't import / wrong resolution** → adjust `SEQ_*` in `cut.py` to the footage; on mixed footage take the warning from `prep.py` seriously.
