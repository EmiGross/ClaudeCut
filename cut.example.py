"""
cut.example.py — Referenz: der framegenau bestätigte China-Vlog-Schnitt (18.06.).

So sieht ein gefülltes cut.py aus. Zum Ausprobieren in `cut.py` umbenennen und
CLIPS_DIR auf den echten Footage-Ordner zeigen lassen.
"""

from pathlib import Path

CLIPS_DIR = Path(r"D:\Video\ChinaTrip\Footage")  # anpassen

BRIEFING = "Knackiger China-Trip-Vlog (letzter Tag). Stärkste Aussagen, Unwichtiges raus."

# Per Rückfrage festgelegt (gemischtes 30/60-Footage): 30 fps, 1080p 16:9.
SEQ_FPS = 30
SEQ_W, SEQ_H = 1920, 1080

# (Dateiname, In-Sekunde, Out-Sekunde, Begründung)
EDL = [
    ("26-01-29 04-53-01 20260129.mp4", 2.30, 16.35,
     "Intro/Hook: letzter Tag in China, Tagesplan (Meetings, Kundenbesuch, "
     "zurück nach Deutschland). Verabschiedung 'Have a good day, bye bye' gekappt."),
    ("26-01-29 08-17-50 3439.mov", 17.00, 29.32,
     "Kunden-Meeting, die STARKE Take: 'second customer meeting ... really proud "
     "to be here'. Die schwache Dublette bei ~3 s und die abgebrochenen Halbsätze "
     "danach ('let's go to the car / OK') wurden verworfen."),
    ("26-01-29 08-40-42 3464.mov", 0.35, 6.90,
     "Abschluss: 'customer visit is finished, heading to the airport, back to "
     "Germany'. Sauberer Outro-Satz."),
]

# Bewusst NICHT verwendet (für den Schnittplan dokumentiert):
DROPPED = [
    ("26-01-29 07-30-34 3434.mov",
     "Markt-Geplänkel ('Can you speak if you want to?', 'How much is it? – 8 or 9 "
     "yuan'). Trägt die Story nicht -> komplett raus."),
]
