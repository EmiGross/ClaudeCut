# Setup

ClaudeCut braucht **drei** Dinge: ffmpeg, ein Whisper-venv (GPU empfohlen) und
ein otio-venv. Klingt nach viel — ist einmalig.

## 0. Voraussetzungen

- **Python 3.12**
- **ffmpeg** installiert und auf dem `PATH` (liefert `ffprobe` mit). Test: `ffprobe -version`.
- **NVIDIA-GPU** für schnelles Whisper (optional — CPU-Fallback ist drin, aber langsam).
- **Claude Code** — das macht die inhaltliche Auswahl (siehe README, „das Gehirn").

## 1. otio-venv (für `build_xml.py` / `prep.py`)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt   # opentimelineio + otio-fcp-adapter
```

`prep.py` und `build_xml.py` laufen in diesem venv.

## 2. Whisper-venv (für die Transkription)

Bewusst **getrennt** — faster-whisper zieht CUDA-Pakete nach.

```bash
python -m venv whisper-venv
whisper-venv\Scripts\activate
pip install faster-whisper
# für GPU zusätzlich (CUDA 12):
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

Das Modell `large-v3` (~3 GB) lädt beim ersten Lauf automatisch in den Cache.

## 3. Pfade verdrahten (`config.py`)

`prep.py` ruft Whisper über das Whisper-venv-Python auf. Entweder `config.py`
editieren **oder** Umgebungsvariablen setzen (kein Code-Edit):

| Variable | Bedeutung | Default |
|---|---|---|
| `CLAUDECUT_WHISPER_PY` | Python des Whisper-venv | `F:\Anwendungen\Whisper\venv\Scripts\python.exe` |
| `CLAUDECUT_TRANSCRIBE` | Whisper-Skript | das vendored `transcribe.py` |
| `CLAUDECUT_WHISPER_MODELS` | Modell-Cache | `F:\Anwendungen\Whisper\models` |

Beispiel (PowerShell):
```powershell
$env:CLAUDECUT_WHISPER_PY = "C:\pfad\whisper-venv\Scripts\python.exe"
$env:CLAUDECUT_WHISPER_MODELS = "C:\pfad\models"
```

## 4. Test

```bash
python prep.py "pfad\zu\einem\test-ordner" --briefing "kurzer Test"
```

Erwartung: pro Clip ein `.json` (neben dem Clip), dazu `transcripts.md` + `cut.py`
im Projektordner, plus ein Sequenzformat-Vorschlag in der Konsole.

## Troubleshooting

- **„Whisper-Python nicht gefunden"** → `CLAUDECUT_WHISPER_PY` zeigt ins Leere.
- **`ffprobe` not found** → ffmpeg nicht auf dem PATH.
- **GPU-Init fehlgeschlagen** → fällt automatisch auf CPU (int8) zurück; langsamer, aber läuft.
- **Premiere importiert nicht / falsche Auflösung** → `SEQ_*` in `cut.py` ans Footage anpassen; bei Mischfootage die Warnung von `prep.py` ernst nehmen.
