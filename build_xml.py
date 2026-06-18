"""
ClaudeCut — Decision-Liste (Datei, In, Out, Grund)  ->  FCP7-XML + Schnittplan.

Hinteres Ende der Pipeline. Die Liste unten kommt im fertigen Tool von der KI
(Whisper -> Claude liest Transkripte + Briefing). Hier steht sie noch als
Ergebnis genau dieses Schritts drin. In/Out in SEKUNDEN (so wie Whisper sie
liefert); ffprobe rechnet pro Clip in Frames um -> robust bei gemischten fps.

Schreibt Video- UND Audiospur. Die echten Datei-Eigenschaften (Kanäle, Rate,
Auflösung) werden per ffprobe gemessen und nachträglich ins XML gepatcht, damit
Premiere die Medien automatisch verbinden kann (sonst Kanal-Mismatch beim Relink).
"""

import copy
import pathlib
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from fractions import Fraction

import opentimelineio as otio

# Windows-Konsole auf UTF-8 (sonst verstümmelt cp1252 Umlaute/→ in Meldungen).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).parent

# --- Auftrag (Briefing, Sequenzformat, EDL) aus cut.py -----------------------
# cut.py wird von prep.py erzeugt und die EDL beim Lesen der Transkripte gefüllt.
# Trennung mit Absicht: build_xml.py ist der reine Übersetzer, cut.py der Auftrag.
try:
    from cut import BRIEFING, CLIPS_DIR, DROPPED, EDL, SEQ_FPS, SEQ_H, SEQ_W
except ImportError:
    sys.exit("Kein cut.py gefunden — erst `python prep.py \"<Footage-Ordner>\"` laufen "
             "lassen (legt cut.py + transcripts.md an), dann die EDL in cut.py füllen.")

CLIPS = pathlib.Path(CLIPS_DIR)
OUT_XML = ROOT / "schnitt.xml"
OUT_PLAN = ROOT / "schnittplan.md"

if not EDL:
    sys.exit("EDL in cut.py ist leer — erst die Soundbite-Auswahl eintragen "
             "(siehe transcripts.md), dann build_xml.py erneut starten.")


# --- ffprobe-Helfer ----------------------------------------------------------
def ffprobe(path, stream, entries):
    return subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", stream,
        "-show_entries", entries,
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]).decode().strip().splitlines()


def media_info(path: pathlib.Path) -> dict:
    """Alles, was das XML über die Datei wissen muss — einmal pro Clip gemessen."""
    num, den = ffprobe(path, "v:0", "stream=r_frame_rate")[0].split("/")
    rate = float(Fraction(int(num), int(den)))
    w = int(ffprobe(path, "v:0", "stream=width")[0])
    h = int(ffprobe(path, "v:0", "stream=height")[0])
    dur_sec = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)]).decode().strip())
    channels = int(ffprobe(path, "a:0", "stream=channels")[0])
    samplerate = int(ffprobe(path, "a:0", "stream=sample_rate")[0])
    return {
        "rate": rate, "width": w, "height": h,
        "total_frames": round(dur_sec * rate),
        "channels": channels, "samplerate": samplerate,
    }


def make_clip(path, info, in_frame, dur_frames):
    """Frische Clip-Instanz (eine pro Spur — otio erlaubt kein doppeltes Parent)."""
    rate = info["rate"]
    return otio.schema.Clip(
        name=path.stem,
        media_reference=otio.schema.ExternalReference(
            target_url=path.as_uri(),
            available_range=otio.opentime.TimeRange(
                otio.opentime.RationalTime(0, rate),
                otio.opentime.RationalTime(info["total_frames"], rate))),
        source_range=otio.opentime.TimeRange(
            otio.opentime.RationalTime(in_frame, rate),
            otio.opentime.RationalTime(dur_frames, rate)),
    )


# --- Timeline bauen (nur Video; Audio fügen wir unten von Hand hinzu) ---------
# otios fcp_xml-Adapter schreibt nur leere Audio-Stubs -> Audiospur bauen wir
# selbst im Post-Processing aus den fertigen Video-Clipitems.
timeline = otio.schema.Timeline(name="ClaudeCut")
v_track = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
timeline.tracks.append(v_track)

print(f"Briefing: {BRIEFING}\n")
infos, rows, seq_pos = {}, [], []
tl_sec = 0.0  # laufende Timeline-Position in Sekunden -> Sequenz-Frames @ SEQ_FPS
for filename, in_sec, out_sec, grund in EDL:
    path = (CLIPS / filename).resolve()
    info = media_info(path)
    infos[filename] = info

    in_frame = round(in_sec * info["rate"])
    dur_frames = round((out_sec - in_sec) * info["rate"])

    # Timeline-Position in der Ziel-Framerate (unabhängig von der Quell-fps)
    dur_sec = dur_frames / info["rate"]
    s = round(tl_sec * SEQ_FPS)
    tl_sec += dur_sec
    e = round(tl_sec * SEQ_FPS)
    seq_pos.append((s, e))

    v_track.append(make_clip(path, info, in_frame, dur_frames))

    rows.append((filename, info["rate"], in_sec, out_sec, dur_frames / info["rate"], grund))
    print(f"  {filename[:28]:28s} @{info['rate']:g}fps  {in_sec:6.2f}->{out_sec:6.2f}s "
          f"({dur_frames/info['rate']:4.1f}s, {info['channels']}ch)")

total_sec = sum(r[4] for r in rows)
print(f"\nGesamtlänge Vlog: {total_sec:.1f}s")

# --- FCP7-XML schreiben ------------------------------------------------------
otio.adapters.write_to_file(timeline, str(OUT_XML), adapter_name="fcp_xml")


# --- XML patchen: echte Datei-Eigenschaften eintragen ------------------------
# otio lässt <video/>/<audio/> leer -> Premiere rät 1 Mono-Kanal und verweigert
# den Relink. Wir tragen die gemessenen Werte pro <file> ein.
def patch_file_media(file_el, info):
    for m in file_el.findall("media"):
        file_el.remove(m)
    media = ET.SubElement(file_el, "media")
    video = ET.SubElement(media, "video")
    vsc = ET.SubElement(video, "samplecharacteristics")
    ET.SubElement(vsc, "width").text = str(info["width"])
    ET.SubElement(vsc, "height").text = str(info["height"])
    audio = ET.SubElement(media, "audio")
    asc = ET.SubElement(audio, "samplecharacteristics")
    ET.SubElement(asc, "depth").text = "16"
    ET.SubElement(asc, "samplerate").text = str(info["samplerate"])
    ET.SubElement(audio, "channelcount").text = str(info["channels"])


tree = ET.parse(OUT_XML)
root = tree.getroot()

# (0) Sequenzformat setzen: Framerate, Auflösung, Pixel-Aspect, Timeline-Positionen.
# otio lässt <format/> leer (-> Premiere nimmt 640×480/4:3) und legt die Positionen
# in der Quell-fps an. Wir tragen das Ziel-Format ein und rechnen start/end auf SEQ_FPS.
seq = root.find(".//sequence")
seq.find("rate/timebase").text = str(SEQ_FPS)
seq.find("rate/ntsc").text = "FALSE"
seq.find("duration").text = str(seq_pos[-1][1])

vmedia = seq.find("media/video")
fmt = vmedia.find("format")
for ch in list(fmt):
    fmt.remove(ch)
sc = ET.SubElement(fmt, "samplecharacteristics")
rt = ET.SubElement(sc, "rate")
ET.SubElement(rt, "timebase").text = str(SEQ_FPS)
ET.SubElement(rt, "ntsc").text = "FALSE"
ET.SubElement(sc, "width").text = str(SEQ_W)
ET.SubElement(sc, "height").text = str(SEQ_H)
ET.SubElement(sc, "pixelaspectratio").text = "square"
ET.SubElement(sc, "fielddominance").text = "none"

for i, vci in enumerate(vmedia.findall("track/clipitem")):
    s, e = seq_pos[i]
    vci.find("start").text = str(s)   # Timeline-Position jetzt in 30er-Frames
    vci.find("end").text = str(e)

# (a) Datei-Specs eintragen
patched = 0
for file_el in root.iter("file"):
    name_el = file_el.find("name")
    if name_el is None:
        continue
    decoded = urllib.parse.unquote(name_el.text)  # otio kodiert Leerzeichen als %20
    if decoded in infos:  # nur voll definierte <file>
        patch_file_media(file_el, infos[decoded])
        patched += 1


# (b) Stereo-Audiospuren aus den Video-Clipitems bauen
def sub(parent, tag, text=None):
    e = ET.SubElement(parent, tag)
    if text is not None:
        e.text = str(text)
    return e


def link_block(parent, ref, mediatype, trackindex, clipindex):
    lk = ET.SubElement(parent, "link")
    sub(lk, "linkclipref", ref)
    sub(lk, "mediatype", mediatype)
    sub(lk, "trackindex", trackindex)
    sub(lk, "clipindex", clipindex)


nch = max(info["channels"] for info in infos.values())  # Stereo -> 2 Audiospuren
seq_media = root.find(".//sequence/media")
audio_sec = seq_media.find("audio")
for t in audio_sec.findall("track"):          # otios leere Stubs raus
    audio_sec.remove(t)
a_tracks = [ET.SubElement(audio_sec, "track") for _ in range(nch)]

v_items = seq_media.findall("video/track/clipitem")
for idx, vci in enumerate(v_items, 1):
    vid_id = vci.get("id")
    file_id = vci.find("file").get("id")
    audio_ids = [f"clipitem-a{ch+1}-{idx}" for ch in range(nch)]

    # Link-Gruppe: Video + alle Audiokanäle gehören zusammen
    members = [(vid_id, "video", 1)] + [(audio_ids[ch], "audio", ch + 1) for ch in range(nch)]

    def add_links(target):
        for ref, mt, ti in members:
            link_block(target, ref, mt, ti, idx)

    add_links(vci)  # Links auch an den Video-Clip

    for ch in range(nch):
        aci = ET.SubElement(a_tracks[ch], "clipitem")
        aci.set("id", audio_ids[ch])
        sub(aci, "name", vci.find("name").text)
        aci.append(copy.deepcopy(vci.find("rate")))
        sub(aci, "duration", vci.find("duration").text)
        sub(aci, "start", vci.find("start").text)
        sub(aci, "end", vci.find("end").text)
        sub(aci, "in", vci.find("in").text)
        sub(aci, "out", vci.find("out").text)
        ET.SubElement(aci, "file").set("id", file_id)  # gleiche Datei, nur Referenz
        st = ET.SubElement(aci, "sourcetrack")
        sub(st, "mediatype", "audio")
        sub(st, "trackindex", ch + 1)
        add_links(aci)

tree.write(OUT_XML, encoding="utf-8", xml_declaration=True)
print(f"XML gepatcht: {patched} Datei-Specs + {nch} Audiospuren ({len(v_items)} Clips, verlinkt).")

# --- Schnittplan.md schreiben (menschenlesbar) -------------------------------
with open(OUT_PLAN, "w", encoding="utf-8") as f:
    f.write("# Schnittplan — ClaudeCut China-Vlog\n\n")
    f.write(f"**Briefing:** {BRIEFING}\n\n")
    f.write(f"**Gesamtlänge:** {total_sec:.1f}s · {len(rows)} Clips\n\n")
    f.write("## Verwendet (in Reihenfolge)\n\n")
    for i, (fn, rate, a, b, dur, grund) in enumerate(rows, 1):
        f.write(f"{i}. **{fn}** @{rate:g}fps — `{a:.2f}–{b:.2f}s` ({dur:.1f}s)\n"
                f"   - {grund}\n\n")
    f.write("## Verworfen\n\n")
    for fn, grund in DROPPED:
        f.write(f"- **{fn}** — {grund}\n")

print(f"\nGeschrieben:\n  {OUT_XML}\n  {OUT_PLAN}")
