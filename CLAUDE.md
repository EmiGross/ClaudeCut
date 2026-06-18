# ClaudeCut — Anleitung für Claude Code

Du bist das „Gehirn" dieser Pipeline. Wenn der Nutzer dir einen **Footage-Ordner +
ein Briefing** gibt („mach mir X draus"), fährst du den folgenden Ablauf. Die
Skripte machen das Mechanische; die **inhaltliche Auswahl machst du**.

## Ablauf

1. **`prep.py` laufen lassen**
   ```
   python prep.py "<Footage-Ordner>" --briefing "<der eine Satz des Nutzers>"
   ```
   Das transkribiert jeden Clip (Whisper, JSON wird gecacht), misst die
   Metadaten und schreibt `transcripts.md` + ein Scaffold `cut.py`.

2. **`transcripts.md` lesen** — die Transkripte stehen mit **clip-relativen
   Timecodes in Sekunden** drin. Triff die inhaltliche Entscheidung:
   - welche Soundbites rein, welche raus (Versprecher, Wiederholungen, schwache Takes, Füllmaterial),
   - in welche **Reihenfolge** (thematisch: Hook → Blöcke → Outro, nicht zwingend chronologisch),
   - Begründung pro Auswahl.

3. **EDL in `cut.py` füllen** — Format `(Dateiname, In-Sekunde, Out-Sekunde, Grund)`.
   Schneide auf **Wortgrenzen** (die `words[]` im JSON geben die genauen Zeiten).
   Auch `DROPPED` füllen (verworfene Clips + Grund) — landet im Schnittplan.

4. **Sequenzformat prüfen.** `prep.py` schlägt eins vor. Bei **Mehrdeutigkeit
   NICHT still entscheiden, sondern den Nutzer fragen:**
   - gemischte Framerate (z. B. 30 + 60) → welche Ziel-fps?
   - Hochkant + Quer gemischt → 16:9 oder 9:16?
   - 4K-Footage → in 4K oder 1080p liefern?
   Das ist seine Liefer-Entscheidung. Den vorgeschlagenen Wert in `cut.py` (`SEQ_FPS`, `SEQ_W`, `SEQ_H`) ggf. korrigieren.

5. **Dem Nutzer den Schnittplan zeigen, BEVOR gebaut wird** (sein Kontroll-Stopp).
   Erst nach seinem OK:
   ```
   python build_xml.py
   ```
   → `schnitt.xml` + `schnittplan.md`.

6. **Premiere-Import** ansagen: `Datei → Importieren → schnitt.xml`.

## Regeln

- **Untertitel** kommen ganz am Ende, neu aus der *geschnittenen* Audio — nicht aus dem Roh-Transkript.
- Whisper pro Clip aufrufen (macht `prep.py` so) → Timecodes bleiben clip-relativ = EDL-tauglich.
- `cut.py` ist pro Projekt; nicht ins Repo committen (steht in `.gitignore`).
- Bei sehr vielen/langen Clips dauert die Transkription — vorhandene `.json` werden übersprungen.

## Wenn Pfade fehlen

`config.py` hält die Whisper-Pfade (oder `CLAUDECUT_WHISPER_PY` env). Schlägt
`prep.py` mit „Whisper-Python nicht gefunden" fehl → Nutzer auf `docs/SETUP.md` verweisen.
