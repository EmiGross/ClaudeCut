"""
config.py — machine-specific paths for ClaudeCut.

Other users: adjust the paths to your own install here OR override them via
environment variables (no code edit needed):

    CLAUDECUT_WHISPER_PY    Python of a venv WITH faster-whisper (see docs/SETUP.md)
    CLAUDECUT_TRANSCRIBE    path to the Whisper script (default: the vendored transcribe.py)

ffprobe/ffmpeg are found via the PATH — ffmpeg must be installed & on the PATH
(it ships ffprobe with it).
"""

import os
from pathlib import Path

ROOT = Path(__file__).parent

# Python interpreter of a venv that has faster-whisper installed.
# Deliberately separate from the ClaudeCut venv (which only needs otio) — Whisper
# pulls in CUDA packages and is heavy. See docs/SETUP.md.
WHISPER_PYTHON = Path(os.environ.get(
    "CLAUDECUT_WHISPER_PY",
    r"F:\Anwendungen\Whisper\venv\Scripts\python.exe",  # ← adjust
))

# The Whisper transcription script (vendored in the repo).
TRANSCRIBE_SCRIPT = Path(os.environ.get(
    "CLAUDECUT_TRANSCRIBE",
    str(ROOT / "transcribe.py"),
))
