"""
config.py — maschinenspezifische Pfade für ClaudeCut.

Andere Nutzer: hier die Pfade an die eigene Installation anpassen ODER per
Umgebungsvariable überschreiben (kein Code-Edit nötig):

    CLAUDECUT_WHISPER_PY    Python eines venv MIT faster-whisper (siehe docs/SETUP.md)
    CLAUDECUT_TRANSCRIBE    Pfad zum Whisper-Skript (Default: das vendored transcribe.py)

ffprobe/ffmpeg werden über den PATH gefunden — ffmpeg muss installiert & auf dem
PATH sein (liefert ffprobe gleich mit).
"""

import os
from pathlib import Path

ROOT = Path(__file__).parent

# Python-Interpreter eines venv, in dem faster-whisper installiert ist.
# Bewusst getrennt vom ClaudeCut-venv (das nur otio braucht) — Whisper zieht
# CUDA-Pakete nach und ist schwergewichtig. Siehe docs/SETUP.md.
WHISPER_PYTHON = Path(os.environ.get(
    "CLAUDECUT_WHISPER_PY",
    r"F:\Anwendungen\Whisper\venv\Scripts\python.exe",  # ← anpassen
))

# Das Whisper-Transkriptionsskript (liegt vendored im Repo).
TRANSCRIBE_SCRIPT = Path(os.environ.get(
    "CLAUDECUT_TRANSCRIBE",
    str(ROOT / "transcribe.py"),
))
