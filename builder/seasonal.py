"""Seasonal faces: each Seasonal/<Event Name>/ folder becomes a format 2 package with uses "seasonal" and a row in
the index's seasonal list. Boards on the Seasonal clock face pull the event whose dates hold today.

An event folder holds face.json (id, name, start, end, clock, and an optional version), background.gif or
background.png (128x32, the GIF apps' frame rules) and optionally README.md and LICENSE. See Seasonal/AUTHORING.md.

The package's entries are mooboard.json, icon.png (cut from the first frame), data/background.bin (every frame as
indices into one palette of at most 256 colors) and data/face.json (the face as the board reads it).
"""
import datetime
import hashlib
import json
import os
import re
import struct

import build
from kit import gif, png

FOLDER = "Seasonal"
W, H = 128, 32
ICON = 32
MAX_FRAMES = 100
SHORTEST_MS = 30
LONGEST_MS = 65535
GIF_CAP = 256 * 1024
PNG_CAP = 256 * 1024
LOWEST_LIT = 5
OVERLAP_YEARS = 10
KEYS = ("id", "name", "start", "end", "clock", "version")
NEEDED = ("id", "name", "start", "end", "clock")
CLOCK_KEYS = ("x", "y", "align", "font", "size", "color")
CLOCK_DEFAULTS = {"x": 64, "y": 9, "align": "center", "font": "clock", "size": 14, "color": "#ffffff"}
ALIGNS = ("left", "center", "right")
# the board's clock faces by role: the semibold clock digits, big time's digits, the light minimal digits, rounded
FONTS = ("clock", "big", "light", "rounded")
SIZES = (6, 28)
EXTRAS = ("README.md", "LICENSE")
BACKGROUNDS = ("background.gif", "background.png")
MAGIC = b"PWSB"
FORMAT = 1
DESCRIPTION = "A seasonal clock face."
MIN_FIRMWARE = "0.3.0"
MONTH_DAY = re.compile(r"([0-9]{2})-([0-9]{2})")
YEAR_MONTH_DAY = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def _day(text, key, where):
    """(year or None, month, day) for MM-DD or YYYY-MM-DD + a yearly feb 29 is refused as it skips three years"""
    bad = build.Refused("%s: %s must be MM-DD or YYYY-MM-DD, a real date" % (where, key))
    if not isinstance(text, str):
        raise bad
    whole = YEAR_MONTH_DAY.fullmatch(text)
    part = MONTH_DAY.fullmatch(text)
    if whole:
        year, month, day = (int(g) for g in whole.groups())
    elif part:
        year, (month, day) = None, (int(g) for g in part.groups())
    else:
        raise bad
    try:
        datetime.date(year or 2001, month, day)
    except ValueError:
        raise bad
    if year is not None and not 2000 <= year <= 2099:
        raise bad
    return year, month, day


def _number(value, low, high):
    return type(value) is int and low <= value <= high


def check_clock(clock, where):
    if not isinstance(clock, dict):
        raise build.Refused("%s: clock must be an object" % where)
    for key in clock:
        if key not in CLOCK_KEYS:
            raise build.Refused("%s: unknown clock key %s" % (where, key))
    out = dict(CLOCK_DEFAULTS, **clock)
    if not _number(out["x"], 0, W - 1):
        raise build.Refused("%s: clock x must be 0 to %d" % (where, W - 1))
    if not _number(out["y"], 0, H - 1):
        raise build.Refused("%s: clock y must be 0 to %d" % (where, H - 1))
    if out["align"] not in ALIGNS:
        raise build.Refused("%s: clock align must be %s" % (where, ", ".join(ALIGNS)))
    if out["font"] not in FONTS:
        raise build.Refused("%s: clock font must be %s" % (where, ", ".join(FONTS)))
    if not _number(out["size"], *SIZES):
        raise build.Refused("%s: clock size must be %d to %d" % (where, SIZES[0], SIZES[1]))
    if not isinstance(out["color"], str) or not COLOR.fullmatch(out["color"]):
        raise build.Refused("%s: clock color must be #rrggbb" % where)
    out["color"] = out["color"].lower()
    if max(bytes.fromhex(out["color"][1:])) < LOWEST_LIT:
        raise build.Refused("%s: clock color is too dim to light" % where)
    return {key: out[key] for key in CLOCK_KEYS}


def check_face(body, folder):
    where = "%s/%s/face.json" % (FOLDER, folder)
    try:
        man = json.loads(body.decode("utf-8"), object_pairs_hook=build._unique)
    except ValueError:
        raise build.Refused("%s is not valid JSON (or repeats a key)" % where)
    if not isinstance(man, dict):
        raise build.Refused("%s is not a JSON object" % where)
    for key in man:
        if key not in KEYS:
            raise build.Refused("%s: unknown key %s" % (where, key))
    for key in NEEDED:
        if key not in man:
            raise build.Refused("%s needs %s" % (where, key))
    if not isinstance(man["id"], str) or not build.ID.fullmatch(man["id"]):
        raise build.Refused("%s: id must be 1 to 32 of a-z, 0-9 and -" % where)
    if not build._text(man["name"], build.NAME_MAX) or "://" in man["name"]:
        raise build.Refused("%s: name must be 1 to %d characters on one line" % (where, build.NAME_MAX))
    if man["name"] != folder:
        raise build.Refused("%s: name must be the folder's name, %s" % (where, folder))
    start, end = _day(man["start"], "start", where), _day(man["end"], "end", where)
    if (start[0] is None) != (end[0] is None):
        raise build.Refused("%s: start and end must both be MM-DD or both YYYY-MM-DD" % where)
    if start[0] is not None and end < start:
        raise build.Refused("%s: end must not be before start" % where)
    version = man.get("version", "1.0.0")
    if not isinstance(version, str) or not build.SEMVER.fullmatch(version):
        raise build.Refused("%s: version must be X.Y.Z" % where)
    return {"id": man["id"], "name": man["name"], "start": man["start"], "end": man["end"],
            "clock": check_clock(man["clock"], where), "version": version, "dates": (start, end)}


def _lit(rgb, i):
    return max(rgb[i * 3:i * 3 + 3]) >= LOWEST_LIT


def read_background(name, body, where):
    """the frames as (rgb, ms) under the gif apps' rules + a png is one still frame"""
    cap = GIF_CAP if name.endswith(".gif") else PNG_CAP
    try:
        if name.endswith(".gif"):
            w, h, frames = gif.decode(body, whole=True)
        else:
            w, h, rgba = png.decode(body)
            frames = [(png.over_black(rgba), 0)]
    except (gif.Unreadable, png.Unreadable):
        raise build.Refused("%s/%s can't be read" % (where, name))
    if (w, h) != (W, H):
        raise build.Refused("%s/%s: the background must be 128x32" % (where, name))
    if len(frames) > MAX_FRAMES:
        raise build.Refused("%s/%s has more than %d frames" % (where, name, MAX_FRAMES))
    if len(body) > cap:
        raise build.Refused("%s/%s is over %d KB" % (where, name, cap >> 10))
    if len(frames) > 1 and any(ms < SHORTEST_MS for _, ms in frames):
        raise build.Refused("%s/%s has frames shorter than %d ms" % (where, name, SHORTEST_MS))
    if len(frames) == 1:
        frames = [(frames[0][0], 0)]
    return [(rgb, min(ms, LONGEST_MS)) for rgb, ms in frames]


def background_bytes(frames):
    """PWSB 1: the header, one palette of at most 256 colors, each frame's delay, then each frame's indices"""
    pixels = [bytes(rgb[i:i + 3]) for rgb, _ in frames for i in range(0, len(rgb), 3)]
    colors = set(pixels)
    mapping = {c: c for c in colors} if len(colors) <= 256 else gif._quantize(pixels)
    palette = sorted(set(mapping.values()))
    index = {c: i for i, c in enumerate(palette)}
    out = bytearray(struct.pack("<4sBBHHHH", MAGIC, FORMAT, 0, W, H, len(frames), len(palette)))
    out += b"".join(palette)
    out += struct.pack("<%dH" % len(frames), *(ms for _, ms in frames))
    for f in range(len(frames)):
        out += bytes(index[mapping[c]] for c in pixels[f * W * H:(f + 1) * W * H])
    return bytes(out)


def icon_bytes(rgb):
    """the 32x32 square of the first frame around its lit pixels"""
    lit = [(i % W, i // W) for i in range(W * H) if _lit(rgb, i)]
    cx = (min(x for x, _ in lit) + max(x for x, _ in lit) + 1) // 2 if lit else W // 2
    x0 = min(max(cx - ICON // 2, 0), W - ICON)
    crop = b"".join(rgb[(y * W + x0) * 3:(y * W + x0 + ICON) * 3] for y in range(ICON))
    return png.encode(ICON, ICON, crop)


def face_bytes(event):
    face = {"format": FORMAT, "id": event["id"], "name": event["name"], "start": event["start"], "end": event["end"],
            "clock": event["clock"]}
    return (json.dumps(face, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def load_event(root, folder):
    where = "%s/%s" % (FOLDER, folder)
    base = os.path.join(root, FOLDER, folder)
    names = build._visible(os.listdir(base))
    for name in names:
        if name not in EXTRAS + BACKGROUNDS + ("face.json",):
            raise build.Refused("%s/%s is not part of a seasonal face (face.json, background.gif or .png, README.md, "
                                "LICENSE)" % (where, name))
    if "face.json" not in names:
        raise build.Refused("%s/face.json is missing" % where)
    backgrounds = [n for n in names if n in BACKGROUNDS]
    if len(backgrounds) != 1:
        raise build.Refused("%s needs one background, background.gif or background.png" % where)
    event = check_face(build._read(os.path.join(base, "face.json")), folder)
    frames = read_background(backgrounds[0], build._read(os.path.join(base, backgrounds[0])), where)
    man = {"format": 2, "id": event["id"], "name": event["name"], "version": event["version"], "by": "mooboard",
           "description": DESCRIPTION, "category": FOLDER, "uses": "seasonal", "minFirmware": MIN_FIRMWARE}
    entries = [("mooboard.json", build.manifest_bytes(man)), ("icon.png", icon_bytes(frames[0][0])),
               ("data/background.bin", background_bytes(frames)), ("data/face.json", face_bytes(event))]
    for name, body in entries[2:]:
        if len(body) > build.ENTRY_CAP:
            raise build.Refused("%s: %s is over %d KB" % (where, name, build.ENTRY_CAP >> 10))
    package = build.write_zip(entries)
    build.check_size(event["id"], len(package), build.BOARDS)
    return event, package, len(frames)


def _spans(dates, first, years):
    """the event's (start, end) dates in each of the years from first + a yearly one may run into the next year"""
    (sy, sm, sd), (ey, em, ed) = dates
    if sy is not None:
        return [(datetime.date(sy, sm, sd), datetime.date(ey, em, ed))]
    out = []
    for year in range(first, first + years):
        start = datetime.date(year, sm, sd)
        end = datetime.date(year if (em, ed) >= (sm, sd) else year + 1, em, ed)
        out.append((start, end))
    return out


def check_overlaps(events, generated):
    first = int(generated[:4]) - 1
    spans = [(e["name"], _spans(e["dates"], first, OVERLAP_YEARS)) for e in events]
    for i, (a, ours) in enumerate(spans):
        for b, theirs in spans[i + 1:]:
            if any(s1 <= e2 and s2 <= e1 for s1, e1 in ours for s2, e2 in theirs):
                raise build.Refused("%s and %s overlap: a board shows one event at a time" % (a, b))


def find_events(root):
    base = os.path.join(root, FOLDER)
    if not os.path.isdir(base):
        return []
    return [n for n in build._visible(os.listdir(base)) if os.path.isdir(os.path.join(base, n))]


def build_events(root, generated, say=lambda line: None):
    """the seasonal rows in folder order and the packages by file name"""
    events, rows, packages = [], [], {}
    for folder in find_events(root):
        event, package, count = load_event(root, folder)
        events.append(event)
        name = "%s-%s.mooboard" % (event["id"], event["version"])
        packages[name] = package
        rows.append({"id": event["id"], "name": event["name"], "start": event["start"], "end": event["end"],
                     "file": name, "sha256": hashlib.sha256(package).hexdigest(), "size": len(package)})
        say("%s/%s: %s, %d bytes, %d frames" % (FOLDER, folder, name, len(package), count))
    check_overlaps(events, generated)
    return rows, packages
