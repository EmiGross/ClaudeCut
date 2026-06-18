# ClaudeCut

Ein selbstgebauter „AutoEdit"-Ersatz: **Ordner voller Clips + ein Satz Briefing →
fertig vorgeschnittene Premiere-Timeline.** Claude versteht den *Inhalt* der
Aufnahmen (über die Transkripte), wählt die stärksten Soundbites, sortiert sie
thematisch und schreibt eine Premiere-importierbare XML. Du steigst direkt beim
Feinschnitt ein.

Gedacht für **inhaltsgetriebene Videos** — Vlogs, Erklärvideos, Podcasts: alles,
wo die *Aussage* zählt, nicht das Bild.

> ## ⚠️ Wichtig: Das „Gehirn" ist Claude Code
> Die eigentliche inhaltliche Auswahl (welche Soundbites rein, in welche
> Reihenfolge, was raus) macht **Claude in [Claude Code](https://claude.ai/code)**,
> indem es die Transkripte liest. Dieses Repo ist **kein** Standalone-Programm —
> es ist eine **Claude-Code-Vorlage**. Ohne Claude Code hast du nur die beiden
> mechanischen Enden (Transkribieren + XML bauen), aber nicht die Auswahl.
> Eine vollautomatische Variante (lokales LLM / API) wäre „Stufe 2" — bewusst
> (noch) nicht gebaut.

## Pipeline

```
Ordner Clips
  │
  ▼  prep.py            ── Whisper pro Clip (Wort-Timestamps) + ffprobe-Metadaten
  │                        schreibt: transcripts.md  +  cut.py (Scaffold)
  ▼  [Claude liest transcripts.md]   ◄── das "Gehirn": Auswahl + Sortierung
  │                        füllt die EDL in cut.py
  ▼  [du prüfst & korrigierst cut.py]   ◄── dein Kontroll-Stopp vor dem Bau
  │
  ▼  build_xml.py        ── baut FCP7-XML (Bild + Stereo-Audio + Sequenzformat)
  │                        schreibt: schnitt.xml  +  schnittplan.md
  ▼
Import in Premiere  →  fertig vorgeschnittene Sequenz
```

## Die drei Skripte

| Datei | Rolle |
|---|---|
| **`prep.py`** | *Vorderteil.* `python prep.py "<Ordner>" --briefing "…"` → geht alle Clips durch, ruft Whisper pro Clip (JSON wird gecacht/übersprungen), misst fps/Auflösung/Seitenverhältnis per ffprobe, schreibt `transcripts.md` und scaffoldet `cut.py`. Schlägt das Sequenzformat vor und **warnt bei Mischfootage**. |
| **`cut.py`** | *Der Auftrag* (pro Projekt, von `prep.py` erzeugt). Hält `CLIPS_DIR`, `BRIEFING`, `SEQ_*` und die **EDL** — Letztere füllt Claude beim Lesen von `transcripts.md`. `cut.example.py` zeigt einen fertigen Schnitt. |
| **`build_xml.py`** | *Hinterteil / Übersetzer.* Importiert aus `cut.py`, baut die FCP7-XML + einen menschenlesbaren `schnittplan.md`. |

`transcribe.py` ist das (vendored) Whisper-Skript; `config.py` hält die Pfade.

## Was „EDL" heißt

**Edit Decision List** — die Liste, die sagt „nimm aus *dieser* Datei den Abschnitt
von *Sekunde X* bis *Sekunde Y*", pro Clip, in der Reihenfolge des fertigen Videos:

```python
EDL = [
    ("intro.mp4",   2.30, 16.35, "Hook: worum geht's heute"),
    ("meeting.mov", 17.00, 29.32, "die starke Take, Wiederholung verworfen"),
]
```

## Schnellstart

1. **Setup** einmalig — siehe [`docs/SETUP.md`](docs/SETUP.md) (zwei venvs: otio + Whisper, ffmpeg, Pfade in `config.py`).
2. In Claude Code: *„Ordner `D:\…\Footage`, mach 90-Sek-Recap, beste Aussagen, locker."*
3. Claude fährt: `prep.py` → liest `transcripts.md` → füllt `cut.py` → (du prüfst) → `build_xml.py`.
4. In Premiere: `Datei → Importieren → schnitt.xml`.

Wie Claude den Ablauf fährt, steht in [`CLAUDE.md`](CLAUDE.md).

## Gelöste Stolperfallen (das eigentliche Know-how)

OpenTimelineIOs `fcp_xml`-Adapter schreibt eine unvollständige XML — drei Dinge
mussten per ffprobe-Messung + XML-Post-Processing nachgetragen werden, sonst
verweigert Premiere:

1. **Audio-Kanäle/Samplerate pro `<file>`** — fehlen → „Kanal-Mismatch", Premiere rät Mono, Relink scheitert.
2. **Echte Audio-Clipitems** — der Adapter legt nur leere Stubs an → kein Ton; wir bauen die Stereospuren aus den Video-Clipitems und verlinken sie.
3. **Sequenz-`<format>`** — fehlt → Premiere nimmt 640×480 / 4:3; wir tragen Auflösung/fps/Pixel-Aspect ein und rechnen die Clip-Positionen auf die Ziel-Framerate um.

Bei **gemischtem Footage** (z. B. 30 + 60 fps) wird pro Clip die echte Rate per
ffprobe gelesen und framegenau umgerechnet; das Ziel-Sequenzformat schlägt
`prep.py` vor und fragt im Zweifel nach (raten wäre falsch).

## Grenzen (ehrlich)

- Claude urteilt nur über den **Transkript-Inhalt** — nicht über Bild, Schärfe, Framing. Stark bei Talking-Head ohne B-Roll, schwach bei bildgetriebener Story.
- Whisper labelt **keine Sprecher** (Diarization wäre eine Ausbaustufe).
- Premiere ist beim XML-Import wählerisch — getestet mit FCP7-XML (`fcp_xml`), framegenau bestätigt.
