"""
cut.example.py — Referenz: ein erfundener Beispiel-Schnitt (Städtetrip-Vlog).

So sieht ein gefülltes cut.py aus. Die Clips hier sind ausgedacht — zum echten
Ausprobieren in `cut.py` umbenennen und CLIPS_DIR auf einen eigenen Footage-
Ordner zeigen lassen (dann von prep.py die echten Dateinamen einsetzen lassen).
"""

from pathlib import Path

CLIPS_DIR = Path(r"D:\Video\Beispiel\Footage")  # anpassen

BRIEFING = "Knackiger Städtetrip-Recap (~60 s). Stärkste Aussagen, Unwichtiges raus."

# Per Rückfrage festgelegt (gemischtes 30/60-Footage): 30 fps, 1080p 16:9.
SEQ_FPS = 30
SEQ_W, SEQ_H = 1920, 1080

# (Dateiname, In-Sekunde, Out-Sekunde, Begründung)
EDL = [
    ("intro.mp4", 2.30, 16.35,
     "Intro/Hook: Ankunft in der Stadt, kurzer Plan für den Tag (Altstadt, "
     "Markt, Aussichtspunkt). Begrüßungs-Gerede davor ('so, da wären wir') gekappt."),
    ("markt.mov", 17.00, 29.32,
     "Markt-Szene, die STARKE Take: 'der frische Fisch hier ist der Wahnsinn'. "
     "Die schwache Dublette bei ~3 s und die abgebrochenen Halbsätze danach "
     "('komm, weiter / OK') wurden verworfen."),
    ("aussicht.mov", 0.35, 6.90,
     "Abschluss: 'von hier oben sieht man die ganze Bucht — perfekter Abschluss'. "
     "Sauberer Outro-Satz."),
]

# Bewusst NICHT verwendet (für den Schnittplan dokumentiert):
DROPPED = [
    ("cafe.mov",
     "Café-Geplänkel ('was nimmst du? – keine Ahnung, vielleicht 'nen Cappuccino'). "
     "Trägt die Story nicht -> komplett raus."),
]
