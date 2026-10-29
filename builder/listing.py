"""An app's store listing: the files in its listing/ folder, checked, and listings.json at the repo's top.

listing/ is repo only and never goes in a package. The web app reads listings.json and the files beside it from
raw.githubusercontent.com at the listings tag, never from the board (the owner, 2026-10-29).

  icon-led.png    Home's icon in the built-in icons' LED style (the owner, 2026-10-29): 12 wide, 24 tall, the rest
                  frame on top and the idle move below, black an off dot, 2 KB at most. Home paints it with the
                  built-ins' LED painter and flips it as they do. Optional, never for Ambiance or Clock apps.
  icon-loop.png   the earlier 32 px loop (32 wide, 32 x N tall, N 2 to 8, frame 1 the icon.png), still accepted
                  but no longer drawn; icon-led.png replaces it.
  clip.webp       the store page's clip: animated lossless WebP, 1024 x 256, 3 to 10 s, 600 KB at most.
  shot-1.png ...  2 or 3 stills, 1024 x 256 PNG, 100 KB at most each.
  history.json    what's new per version, newest first: [{"version": "1.1", "date": "YYYY-MM-DD", "notes": "..."}],
                  versions two numbers, the first the manifest's major.minor, notes 500 characters at most.
Python 3 standard library only.
"""
import json
import os
import re
import struct
import zlib

FOLDER = "listing"
TOP = "listings.json"
NO_HOME = ("Ambiance", "Clock", "Faces")   # these install to their pickers with no Home tile
ICON = 32
LOOP_FRAMES = (2, 8)
LOOP_CAP = 8 * 1024
LED = (12, 24)
LED_CAP = 2 * 1024
CLIP = (1024, 256)
CLIP_MS = (3000, 10000)
CLIP_CAP = 600 * 1024
SHOT_CAP = 100 * 1024
SHOTS = (2, 3)
NOTES_MAX = 500
HISTORY_MAX = 50
VERSION = re.compile(r"(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})")
DATE = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])")
PNG = b"\x89PNG\r\n\x1a\n"


class Refused(Exception):
    pass


def _chunks(body, where):
    if body[:8] != PNG:
        raise Refused("%s is not a png" % where)
    pos, out = 8, []
    while pos + 8 <= len(body):
        size, kind = struct.unpack(">I4s", body[pos:pos + 8])
        out.append((kind, body[pos + 8:pos + 8 + size]))
        pos += 12 + size
        if kind == b"IEND":
            return out
    raise Refused("%s is not a whole png" % where)


def png_size(body, where):
    kinds = _chunks(body, where)
    if kinds[0][0] != b"IHDR":
        raise Refused("%s has no header" % where)
    return struct.unpack(">II", kinds[0][1][:8])


def png_pixels(body, where):
    """the png's rows of (r, g, b, a) + 8 bit and palette pngs of 1 to 8 bits, not interlaced"""
    chunks = _chunks(body, where)
    width, height, depth, kind, _, _, laced = struct.unpack(">IIBBBBB", chunks[0][1])
    if laced or kind not in (0, 2, 3, 4, 6) or (kind != 3 and kind != 0 and depth != 8) or depth not in (1, 2, 4, 8):
        raise Refused("%s: an 8 bit or palette png that is not interlaced" % where)
    palette = [tuple(c[i:i + 3]) for c in [b"".join(b for k, b in chunks if k == b"PLTE")] for i in range(0, len(c), 3)]
    alpha = b"".join(b for k, b in chunks if k == b"tRNS")
    raw = zlib.decompress(b"".join(b for k, b in chunks if k == b"IDAT"))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[kind]
    stride = (width * channels * depth + 7) // 8
    step = max(1, channels * depth // 8)
    rows, prior, pos = [], bytearray(stride), 0
    for _ in range(height):
        kind_f, line = raw[pos], bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            a = line[i - step] if i >= step else 0
            b = prior[i]
            c = prior[i - step] if i >= step else 0
            if kind_f == 1:
                line[i] = (line[i] + a) & 255
            elif kind_f == 2:
                line[i] = (line[i] + b) & 255
            elif kind_f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind_f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prior = line
        row = []
        for x in range(width):
            if depth < 8:
                bit = x * depth
                v = (line[bit // 8] >> (8 - depth - bit % 8)) & ((1 << depth) - 1)
                if kind == 3:
                    row.append(palette[v] + ((alpha[v] if v < len(alpha) else 255),))
                else:
                    g = v * 255 // ((1 << depth) - 1)
                    row.append((g, g, g, 255))
                continue
            px = line[x * channels:(x + 1) * channels]
            if kind == 3:
                row.append(palette[px[0]] + ((alpha[px[0]] if px[0] < len(alpha) else 255),))
            elif kind == 0:
                row.append((px[0], px[0], px[0], 255))
            elif kind == 4:
                row.append((px[0], px[0], px[0], px[1]))
            elif kind == 2:
                row.append(tuple(px) + (255,))
            else:
                row.append(tuple(px))
        rows.append(row)
    return rows


def webp_clip(body, where):
    """(width, height, frames, milliseconds) of an animated lossless webp"""
    if body[:4] != b"RIFF" or body[8:12] != b"WEBP" or struct.unpack("<I", body[4:8])[0] + 8 != len(body):
        raise Refused("%s is not a webp" % where)
    pos, size, frames, ms, lossless = 12, None, 0, 0, True
    while pos + 8 <= len(body):
        kind, n = body[pos:pos + 4], struct.unpack("<I", body[pos + 4:pos + 8])[0]
        data = body[pos + 8:pos + 8 + n]
        if kind == b"VP8X":
            if not data[0] & 0x02:
                raise Refused("%s is not animated" % where)
            size = (int.from_bytes(data[4:7], "little") + 1, int.from_bytes(data[7:10], "little") + 1)
        elif kind == b"ANMF":
            frames += 1
            ms += int.from_bytes(data[12:15], "little")
            lossless = lossless and data[16:20] == b"VP8L"
        pos += 8 + n + (n & 1)
    if size is None or not frames:
        raise Refused("%s is not an animated webp" % where)
    if not lossless:
        raise Refused("%s is lossy; the led dots need lossless webp" % where)
    return size[0], size[1], frames, ms


def check_history(body, version, where):
    try:
        rows = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Refused("%s is not json" % where)
    if not isinstance(rows, list) or not 1 <= len(rows) <= HISTORY_MAX:
        raise Refused("%s is a list of 1 to %d versions" % (where, HISTORY_MAX))
    seen = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"version", "date", "notes"}:
            raise Refused("%s: each version has version, date, and notes alone" % where)
        if not isinstance(row["version"], str) or not VERSION.fullmatch(row["version"]):
            raise Refused("%s: %r is not two numbers like 1.0" % (where, row["version"]))
        if not isinstance(row["date"], str) or not DATE.fullmatch(row["date"]):
            raise Refused("%s: %r is not YYYY-MM-DD" % (where, row["date"]))
        notes = row["notes"]
        if not isinstance(notes, str) or not notes.strip() or len(notes) > NOTES_MAX or notes != notes.strip():
            raise Refused("%s: version %s needs notes of 1 to %d characters" % (where, row["version"], NOTES_MAX))
        seen.append((tuple(int(p) for p in row["version"].split(".")), row["date"]))
    for (newer, newer_date), (older, older_date) in zip(seen, seen[1:]):
        if not newer > older or newer_date < older_date:
            raise Refused("%s is not newest first" % where)
    major_minor = ".".join(version.split("-")[0].split(".")[:2])
    if rows[0]["version"] != major_minor:
        raise Refused("%s starts at %s but the app is %s" % (where, rows[0]["version"], major_minor))
    return rows


def check(base, man, icon, category, where):
    """the listing's row for listings.json, or None when the app has no listing/ yet"""
    folder = os.path.join(base, FOLDER)
    if not os.path.isdir(folder):
        return None
    where = where + "/" + FOLDER
    names = sorted(n for n in os.listdir(folder) if not n.startswith("."))
    shots = [n for n in names if re.fullmatch(r"shot-[1-9]\.png", n)]
    known = {"icon-loop.png", "icon-led.png", "clip.webp", "history.json"} | set(shots)
    for name in names:
        if name not in known or os.path.islink(os.path.join(folder, name)):
            raise Refused("%s/%s is not part of a listing" % (where, name))

    def read(name):
        with open(os.path.join(folder, name), "rb") as f:
            return f.read()
    for name in ("clip.webp", "history.json"):
        if name not in names:
            raise Refused("%s/%s is missing" % (where, name))
    row = {"path": "%s/%s/%s/" % (category, os.path.basename(base), FOLDER)}
    if "icon-loop.png" in names:
        if category in NO_HOME:
            raise Refused("%s/icon-loop.png: %s apps have no Home tile" % (where, category))
        body = read("icon-loop.png")
        if len(body) > LOOP_CAP:
            raise Refused("%s/icon-loop.png is over 8 KB" % where)
        width, height = png_size(body, where + "/icon-loop.png")
        if width != ICON or height % ICON or not LOOP_FRAMES[0] <= height // ICON <= LOOP_FRAMES[1]:
            raise Refused("%s/icon-loop.png is 32 wide and 2 to 8 frames of 32 tall" % where)
        if png_pixels(body, where)[:ICON] != png_pixels(icon, where):
            raise Refused("%s/icon-loop.png's first frame is not icon.png" % where)
        row["loop"] = height // ICON
    if "icon-led.png" in names:
        if category in NO_HOME:
            raise Refused("%s/icon-led.png: %s apps have no Home tile" % (where, category))
        body = read("icon-led.png")
        if len(body) > LED_CAP or png_size(body, where + "/icon-led.png") != LED:
            raise Refused("%s/icon-led.png is 12 wide and 24 tall (two frames), 2 KB at most" % where)
        dots = png_pixels(body, where + "/icon-led.png")
        if any(0 < px[3] < 255 for row in dots for px in row):
            raise Refused("%s/icon-led.png: a dot is on or off, never see-through" % where)
        if dots[:12] == dots[12:]:
            raise Refused("%s/icon-led.png: the idle frame is the rest frame" % where)
        row["led"] = True
    body = read("clip.webp")
    if len(body) > CLIP_CAP:
        raise Refused("%s/clip.webp is over 600 KB" % where)
    width, height, frames, ms = webp_clip(body, where + "/clip.webp")
    if (width, height) != CLIP or not CLIP_MS[0] <= ms <= CLIP_MS[1] or frames < 2:
        raise Refused("%s/clip.webp is 1024 x 256 and 3 to 10 s" % where)
    if shots != ["shot-%d.png" % i for i in range(1, len(shots) + 1)] or not SHOTS[0] <= len(shots) <= SHOTS[1]:
        raise Refused("%s needs shot-1.png to shot-2.png or shot-3.png" % where)
    for name in shots:
        body = read(name)
        if len(body) > SHOT_CAP or png_size(body, where + "/" + name) != CLIP:
            raise Refused("%s/%s is a 1024 x 256 png of 100 KB at most" % (where, name))
    row["shots"] = len(shots)
    row["history"] = check_history(read("history.json"), man["version"], where + "/history.json")
    return row


def top_bytes(rows):
    """listings.json: every listed app by id, sorted, one stable form"""
    return (json.dumps({"format": 1, "apps": dict(sorted(rows.items()))}, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")
