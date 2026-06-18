# ClaudeCut — guide for Claude Code

You are the "brain" of this pipeline. When the user hands you a **footage folder +
a briefing** ("make X out of this"), you run the flow below. The scripts do the
mechanical part; **you make the editorial selection**.

## Flow

1. **Run `prep.py`**
   ```
   python prep.py "<footage folder>" --briefing "<the user's one sentence>"
   ```
   This transcribes every clip (Whisper, JSON is cached), measures the metadata
   and writes `transcripts.md` + a scaffold `cut.py`.

2. **Read `transcripts.md`** — the transcripts are in there with **clip-relative
   timecodes in seconds**. Make the editorial decision:
   - which soundbites stay, which go (misspeaks, repetitions, weak takes, filler),
   - in what **order** (thematic: hook → blocks → outro, not necessarily chronological),
   - a reason per choice.

3. **Fill the EDL in `cut.py`** — format `(filename, in-second, out-second, reason)`.
   Cut on **word boundaries** (the `words[]` in the JSON give the exact times).
   Also fill `DROPPED` (discarded clips + reason) — it lands in the cut plan.

4. **Check the sequence format.** `prep.py` suggests one. On **ambiguity, do NOT
   decide silently — ask the user:**
   - mixed frame rate (e.g. 30 + 60) → which target fps?
   - portrait + landscape mixed → 16:9 or 9:16?
   - 4K footage → deliver in 4K or 1080p?
   This is their delivery decision. Adjust the suggested value in `cut.py` (`SEQ_FPS`, `SEQ_W`, `SEQ_H`) if needed.

5. **Show the user the cut plan BEFORE building** (their control stop). Only after
   their OK:
   ```
   python build_xml.py
   ```
   → `cut.xml` + `cut_plan.md`.

6. **Announce the Premiere import**: `File → Import → cut.xml`.

## Rules

- **Subtitles** come at the very end, freshly from the *cut* audio — not from the raw transcript.
- Call Whisper per clip (that's what `prep.py` does) → timecodes stay clip-relative = EDL-ready.
- `cut.py` is per project; do not commit it to the repo (it's in `.gitignore`).
- With many/long clips, transcription takes a while — existing `.json` files are skipped.

## When paths are missing

`config.py` holds the Whisper paths (or `CLAUDECUT_WHISPER_PY` env). If `prep.py`
fails with "Whisper Python not found" → point the user to `docs/SETUP.md`.
