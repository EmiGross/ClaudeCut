"""
cut.example.py — reference: a made-up example cut (city-trip vlog).

This is what a filled cut.py looks like. The clips here are fictional — to try it
for real, rename to `cut.py`, point CLIPS_DIR at your own footage folder (then let
prep.py drop in the real filenames).
"""

from pathlib import Path

CLIPS_DIR = Path(r"D:\Video\Example\Footage")  # adjust

BRIEFING = "Punchy city-trip recap (~60 s). Strongest lines, drop the filler."

# Decided via a follow-up question (mixed 30/60 footage): 30 fps, 1080p 16:9.
SEQ_FPS = 30
SEQ_W, SEQ_H = 1920, 1080

# (filename, in-second, out-second, reason)
EDL = [
    ("intro.mp4", 2.30, 16.35,
     "Intro/hook: arriving in the city, quick plan for the day (old town, "
     "market, viewpoint). Greeting chatter before it ('so, here we are') trimmed."),
    ("market.mov", 17.00, 29.32,
     "Market scene, the STRONG take: 'the fresh fish here is unreal'. The weak "
     "duplicate at ~3 s and the cut-off half-sentences after it ('come on, let's "
     "go / OK') were discarded."),
    ("viewpoint.mov", 0.35, 6.90,
     "Closer: 'from up here you can see the whole bay — perfect ending'. "
     "Clean outro line."),
]

# Deliberately NOT used (documented for the cut plan):
DROPPED = [
    ("cafe.mov",
     "Cafe chatter ('what are you getting? – no idea, maybe a cappuccino'). "
     "Doesn't carry the story -> dropped entirely."),
]
