#!/usr/bin/env python3
"""Builds every app in this repo into dist/: <id>-<version>.mooboard, index.json and, with --key, index.sig.

Usage: python3 builder/build.py [--out DIR] [--key PEM] [--generated YYYY-MM-DDTHH:MM:SSZ] [--previous INDEX]
                               [--openssl PATH]

Apps live in <Category>/<App>/: mooboard.json (package format 2), icon.png (32x32), README.md, LICENSE,
data/ and, for Word Guess, words.txt (its guess list, kept beside the package as <id>-<version>.words). A package is a ZIP of stored entries with fixed headers and times, in a fixed order (mooboard.json,
icon.png, then data/ sorted), so the same folder always builds the same bytes. index.sig is the base64 of the
DER ECDSA P-256 signature over index.json's exact bytes, as the firmware's OTA release statement is signed.
Python 3 standard library and the openssl command only.
"""
import argparse
import base64
import calendar
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unicodedata
import zlib

# the store's headings in their order from categories.txt at the repo's top, one a line + apps a to z by folder within
# each (the owner, 2026-10-20) + a new category is a line there and a folder, and boards read it with the catalog
def read_categories(root):
    with open(os.path.join(root, "categories.txt"), encoding="utf-8") as f:
        names = tuple(line.strip() for line in f if line.strip())
    if not names or len(set(names)) != len(names):
        raise SystemExit("categories.txt needs one name a line, none twice")
    for name in names:   # the board's own rule (pw_apps validCategory): a capital then letters, 1 to 24
        if not re.fullmatch(r"[A-Z][A-Za-z]{0,23}", name):
            raise SystemExit("categories.txt: %r is not a capital then letters, 24 at most" % name)
    return names


CATEGORIES = read_categories(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# the catalog's renderers u517 u532 + their sheet is their manifest's settings and controls + the firmware's
# pw_model/store/Keys.h lists the keys each takes and tools/tests/test_store_keys.py there holds this table to it +
# kind is card (takes its turn) hold (holds the panel while it runs) or night (ok to wake: a card by day that holds
# the panel at night) + the firmware's keys are [a-z]+ so digital rain is raincode and ok to wake oktowake
CATALOG_USES = ("pong", "snake", "blocks", "maze", "aquarium", "lava", "aurora", "rain", "sunmoon", "word", "quotes",
                "habits", "timer", "pomodoro", "scoreboard", "dice",
                "breakout", "invaders", "flappy", "cycles", "fireworks", "nightcity", "snowglobe", "raincode",
                "oktowake", "chores", "facts", "jokes", "intervals", "chessclock", "wheel", "tally", "vfdstereo",
                "microracer", "pixelpinball", "microrogue", "spacelander",
                "aibrief", "aipet", "aiscene", "aiface",   # the ai apps u574 c3247
                "flightglance",
                "dinorunner", "missiledefense", "minesweeper", "wordguess",   # app-lab's games and ambiances c3506
                "waterfall", "cybercity", "synthwave", "dune", "pacman")
USES = ("prayer", "countdown", "sketch", "life", "plasma", "starfield", "fireplace") + CATALOG_USES   # the firmware's renderers (pw::AppRenderer), in its order
SPEED = {"speed": ("choice", 3)}
SPEED_COLORS = dict(SPEED, colors=("choice", 2))
COLOR_SPEED = dict({"color": ("color", 0)}, **SPEED)


def _row(kind, settings=None, controls=None, needs=()):
    """needs is what a card waits for before its turn, as the board's table has it (clock, entries, item, place) + minute
    for a turn across the minute's change"""
    return {"kind": kind, "needs": tuple(sorted(needs)), "settings": dict(settings or {}),
            "controls": dict(controls or {})}


def _buttons(*keys):
    return {key: ("button", 0) for key in keys}


RENDERER_KEYS = {
    "pong": _row("card", SPEED_COLORS, needs=("minute",)),   # its turn straddles the minute
    "snake": _row("card", SPEED_COLORS),
    "blocks": _row("card", SPEED),
    "maze": _row("card", SPEED),
    "aquarium": _row("card", {"fish": ("choice", 3)}),
    "lava": _row("card", COLOR_SPEED),
    "aurora": _row("card", dict({"colors": ("choice", 3)}, **SPEED)),
    "rain": _row("card", {"rain": ("choice", 3), "city": ("choice", 2)}),
    "sunmoon": _row("card", needs=("clock", "place")),
    "word": _row("card", needs=("clock", "item")),
    "quotes": _row("card", needs=("clock", "item")),
    "habits": _row("card", controls={"habits": ("list", 6)}, needs=("clock", "entries")),
    "timer": _row("hold", controls=dict(_buttons("start", "add", "pause", "resume", "cancel", "sw_start", "sw_stop",
                                                 "sw_reset"), countdown=("readout", 0), stopwatch=("readout", 0))),
    "pomodoro": _row("hold", {"focus": ("choice", 6), "break": ("choice", 3), "long_break": ("choice", 4)},
                     dict(_buttons("start", "pause", "resume", "skip", "stop"), left=("readout", 0))),
    "scoreboard": _row("hold", {"left": ("text", 8), "right": ("text", 8), "left_color": ("color", 0),
                                "right_color": ("color", 0)},
                       dict({"left": ("stepper", 0), "right": ("stepper", 0)}, **_buttons("reset", "done"))),
    "dice": _row("hold", {"dice": ("choice", 2)}, dict(_buttons("roll", "flip"), result=("readout", 0))),
    # the second wave u532
    "breakout": _row("card", SPEED),
    "invaders": _row("card", SPEED_COLORS),
    "flappy": _row("card", SPEED),
    "cycles": _row("card", dict({"riders": ("choice", 3)}, **SPEED)),
    "fireworks": _row("card", {"colors": ("choice", 3), "show": ("choice", 2)}),
    "nightcity": _row("card"),
    "snowglobe": _row("card", {"scene": ("choice", 3)}),
    "raincode": _row("card", COLOR_SPEED),
    "oktowake": _row("night", {"bedtime": ("choice", 5), "wake": ("choice", 5), "clock": ("toggle", 0)},
                     needs=("clock",)),
    "chores": _row("card", {"people": ("text", 32), "rotate": ("choice", 2)}, {"chores": ("list", 6)},
                   needs=("clock", "entries")),
    "facts": _row("card", needs=("clock", "item")),
    "jokes": _row("card", needs=("clock", "item")),
    "intervals": _row("hold", {"work": ("choice", 5), "rest": ("choice", 4), "rounds": ("choice", 5)},
                      dict(_buttons("start", "pause", "resume", "skip", "stop"), phase=("readout", 0))),
    "chessclock": _row("hold", {"time": ("choice", 6), "increment": ("choice", 5)},
                       _buttons("left", "right", "pause", "reset", "done")),
    "wheel": _row("hold", controls=dict({"items": ("list", 8)}, **_buttons("spin"))),
    "tally": _row("hold", {"label": ("text", 12)}, dict({"count": ("stepper", 0)}, **_buttons("add", "reset", "done"))),
    "vfdstereo": _row("card", {"mode": ("choice", 2), "colors": ("choice", 3)}),
    "microracer": _row("card", {"speed": ("choice", 3), "track": ("choice", 3)}),
    "pixelpinball": _row("card", {"speed": ("choice", 3), "table": ("choice", 3)}),
    "microrogue": _row("card", {"speed": ("choice", 3), "theme": ("choice", 3)}),
    "spacelander": _row("card", {"speed": ("choice", 3), "planet": ("choice", 3)}),
    # the ai apps u574 c3247 + the briefing and the dreamscape wait for an answer from api.mooboard.co/ai
    "aibrief": _row("card", {"tone": ("choice", 3), "personal": ("toggle", 0), "accent": ("color", 0)},
                    needs=("ai", "clock")),
    "aipet": _row("card", {"name": ("text", 12), "color": ("color", 0), "persona": ("choice", 4)}, needs=("clock",)),
    "aiscene": _row("card", {"scene": ("text", 32), "style": ("choice", 3), "refresh": ("choice", 3)}, needs=("ai",)),
    "aiface": _row("card", {"describe": ("text", 32)}, needs=("clock",)),
    "flightglance": _row("card", {"radius": ("choice", 5), "units": ("choice", 2), "follow": ("text", 32),
                                  "follow2": ("text", 32), "cycle": ("choice", 3), "layout": ("choice", 8),
                                  "quiet": ("choice", 4), "title": ("choice", 2)}),
    # app-lab's four games and four ambiances c3506 + their renderers only, no app of the catalog names them yet
    "dinorunner": _row("card", SPEED),
    "missiledefense": _row("card", SPEED),
    "minesweeper": _row("card", SPEED),
    "wordguess": _row("card", SPEED),
    "waterfall": _row("card", {"flow": ("choice", 3), "mist": ("toggle", 0)}),
    "cybercity": _row("card", {"rain": ("choice", 3), "palette": ("choice", 3)}),
    "synthwave": _row("card", {"speed": ("choice", 3), "palette": ("choice", 3)}),
    "dune": _row("card", COLOR_SPEED),
    "pacman": _row("card", SPEED),
}
CATALOG_FIRMWARE = (0, 3, 1)   # the first firmware that carries the catalog's renderers u534
# a renderer added after the first catalog firmware and the firmware that first draws it u574 c3247
USES_FIRMWARE = {"vfdstereo": (0, 3, 2), "microracer": (0, 3, 2), "pixelpinball": (0, 3, 2), "microrogue": (0, 3, 2),
                 "spacelander": (0, 3, 2),
                 "aibrief": (0, 3, 2), "aipet": (0, 3, 2), "aiscene": (0, 3, 2), "aiface": (0, 3, 2),
                 "flightglance": (0, 3, 2),
                 "dinorunner": (0, 3, 2),
                 # u643 c3588 + the app-lab review's fixes and word guess's hosted list come with 0.4.0
                 "missiledefense": (0, 4, 0), "minesweeper": (0, 4, 0), "wordguess": (0, 4, 0),
                 "waterfall": (0, 3, 2), "cybercity": (0, 3, 2), "synthwave": (0, 3, 2), "dune": (0, 3, 2), "pacman": (0, 4, 0)}
BOARDS = ("s3", "p4")
BOARD_CAP = {"s3": 2 * 1024 * 1024, "p4": 8 * 1024 * 1024}
ENTRY_CAP = 512 * 1024
MAX_ENTRIES = 200
MAX_DEPTH = 3
MANIFEST_CAP = 8 * 1024
ICON_CAP = 8 * 1024
INDEX_CAP = 64 * 1024
# the most apps a board reads in one index (pw_apps kCatalogAppsMax) + more and every board on 0.3.1 and 0.3.2-alpha.1
# refuses the whole catalog as bad-package (89 on 2026-10-26) u570
APPS_MAX = 64
ICON = 32
NAME_MAX = 24
DESCRIPTION_MAX = 80
KEYS = ("format", "id", "name", "version", "by", "description", "category", "uses", "minFirmware", "boards",
        "settings", "controls")
SETTING_KEYS = ("key", "type", "label", "default", "max", "options")
CONTROL_KEYS = ("key", "type", "label", "arg", "min", "max", "chars", "add")
SETTINGS_MAX = 8
CONTROLS_MAX = 16
LABEL_MAX = 24
NEEDED_KEYS = ("format", "id", "name", "version", "by", "description", "category")
REPO_ONLY = ("README.md", "LICENSE")
# u644 c3587 + Word Guess's guess list stays on the catalog's release beside its package and never in the package or
# the firmware + words.txt holds one lowercase five-letter word a line a to z once each + it goes out as
# <id>-<version>.words of three bytes a word (its letters in base 26 a = 0 most significant first) so a board finds a
# word by binary search + the index row names it with its size and sha256 + the board's cap (pw_model GuessWords.h)
WORDS_FILE = "words.txt"
WORDS_USES = ("wordguess",)
WORDS_MAX = 16384
WORD = re.compile(r"[a-z]{5}")
NOT_APPS = ("builder", "dist", "Seasonal")

ID = re.compile(r"[a-z0-9-]{1,32}")
KEY = re.compile(r"[a-z][a-z0-9_]{0,15}")
COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
BY = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")
NUMBER = r"(?:0|[1-9][0-9]{0,8})"
SEMVER = re.compile(r"%s\.%s\.%s" % (NUMBER, NUMBER, NUMBER))
SEGMENT = r"[A-Za-z0-9_-]+"
DATA_PATH = re.compile(r"%s(?:/%s){0,%d}\.(?:json|bin)" % (SEGMENT, SEGMENT, MAX_DEPTH - 1))
STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

LOCAL, CENTRAL, END = 0x04034B50, 0x02014B50, 0x06054B50
ZIP_DATE = 0x21
UNIX = 3
MADE_BY = (UNIX << 8) | 20
NEEDED = 10
REGULAR = 0o100644
PNG = b"\x89PNG\r\n\x1a\n"
PNG_KEEP = (b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND")
P256_SPKI_PREFIX = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d03010703420004")


class Refused(Exception):
    """a reason to stop said in one line"""


def _unique(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError(keys)
    return dict(pairs)


def _text(value, most):
    return (isinstance(value, str) and 1 <= len(value) <= most and value == value.strip()
            and not any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value))


def check_manifest(body, category, folder):
    where = "%s/%s/mooboard.json" % (category, folder)
    if len(body) > MANIFEST_CAP:
        raise Refused("%s is over 8 KB" % where)
    try:
        man = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
    except ValueError:
        raise Refused("%s is not valid JSON (or repeats a key)" % where)
    if not isinstance(man, dict):
        raise Refused("%s is not a JSON object" % where)
    for key in man:
        if key not in KEYS:
            raise Refused("%s: unknown key %s" % (where, key))
    for key in NEEDED_KEYS:
        if key not in man:
            raise Refused("%s needs %s" % (where, key))
    if type(man["format"]) is not int or man["format"] != 2:
        raise Refused("%s: format must be 2" % where)
    if not isinstance(man["id"], str) or not ID.fullmatch(man["id"]):
        raise Refused("%s: id must be 1 to 32 of a-z, 0-9 and -" % where)
    if not _text(man["name"], NAME_MAX) or "://" in man["name"]:
        raise Refused("%s: name must be 1 to %d characters on one line" % (where, NAME_MAX))
    if man["name"] != folder:
        raise Refused("%s: name must be the folder's name, %s" % (where, folder))
    if not isinstance(man["version"], str) or not SEMVER.fullmatch(man["version"]):
        raise Refused("%s: version must be X.Y.Z" % where)
    if not isinstance(man["by"], str) or not BY.fullmatch(man["by"]):
        raise Refused("%s: by must be a GitHub-style name" % where)
    if not _text(man["description"], DESCRIPTION_MAX):
        raise Refused("%s: description must be 1 to %d characters on one line" % (where, DESCRIPTION_MAX))
    if man["category"] != category:
        raise Refused("%s: category must be %s, its folder" % (where, category))
    if "uses" not in man:
        raise Refused("%s: GIF apps come to the store later; give uses" % where)
    if man["uses"] not in USES:
        raise Refused("%s: uses must be one of %s" % (where, ", ".join(USES)))
    if "minFirmware" in man and (not isinstance(man["minFirmware"], str)
                                 or not SEMVER.fullmatch(man["minFirmware"])):
        raise Refused("%s: minFirmware must be X.Y.Z" % where)
    boards = man.get("boards", list(BOARDS))
    if (not isinstance(boards, list) or not boards or len(set(map(str, boards))) != len(boards)
            or any(b not in BOARDS for b in boards)):
        raise Refused("%s: boards must be a list of s3 and p4, each once" % where)
    check_sheet(man, where)
    return man


def _label(value, most=LABEL_MAX):
    """the board's validLabel + and no character of unicode's other categories c2910"""
    return _text(value, most) and "://" not in value and not any(unicodedata.category(ch)[0] == "C" for ch in value)


def _words(label):
    """the {key} words of a label in the board's reading + an unclosed brace is plain text"""
    found, at = [], 0
    while True:
        at = label.find("{", at)
        if at < 0:
            return found
        close = min((i for i in (label.find("{", at + 1), label.find("}", at + 1)) if i >= 0), default=-1)
        if close < 0:
            return found
        if label[close] == "{":
            at = close
            continue
        found.append(label[at + 1:close])
        at = close + 1


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def check_settings(settings, where):
    """format 1's settings exactly as the board reads them (pw_apps Manifest.cpp readSettings)"""
    if not isinstance(settings, list) or len(settings) > SETTINGS_MAX:
        raise Refused("%s: settings must be a list of at most %d" % (where, SETTINGS_MAX))
    seen = set()
    for s in settings:
        if not isinstance(s, dict) or not isinstance(s.get("key"), str) or not KEY.fullmatch(s["key"]):
            raise Refused("%s: a setting's key must be a-z then a-z, 0-9 and _, 16 at most" % where)
        what = "%s: setting %s" % (where, s["key"])
        kind = s.get("type")
        allowed = {"key", "type", "label", "default"} | ({"max"} if kind == "text" else set()) | (
            {"options"} if kind == "choice" else set())
        if kind not in ("text", "color", "toggle", "choice") or set(s) - allowed or "default" not in s:
            raise Refused("%s must be text, color, toggle or choice with only its own fields" % what)
        if not _label(s.get("label")):
            raise Refused("%s: label must be 1 to %d characters on one line" % (what, LABEL_MAX))
        if s["key"] in seen:
            raise Refused("%s is there twice" % what)
        seen.add(s["key"])
        default = s["default"]
        if kind == "text" and not (_int(s.get("max"), 1, 32) and isinstance(default, str)
                                   and 1 <= len(default) <= s["max"]):
            raise Refused("%s: max must be 1 to 32 and the default 1 to max characters" % what)
        if kind == "color" and not (isinstance(default, str) and COLOR.fullmatch(default)):
            raise Refused("%s: default must be a color as #RRGGBB" % what)
        if kind == "toggle" and not isinstance(default, bool):
            raise Refused("%s: default must be true or false" % what)
        if kind == "choice":
            options = s.get("options")
            if (not isinstance(options, list) or not 2 <= len(options) <= 8 or len(set(map(str, options))) != len(options)
                    or not all(isinstance(o, str) and 1 <= len(o) <= 16 for o in options) or default not in options):
                raise Refused("%s: options must be 2 to 8 words of 1 to 16 characters and hold the default" % what)


def check_controls(controls, settings, where):
    """a catalog app's controls as the board reads them (pw_apps Manifest.cpp readControls) c2910"""
    if not isinstance(controls, list) or len(controls) > CONTROLS_MAX:
        raise Refused("%s: controls must be a list of at most %d" % (where, CONTROLS_MAX))
    texts = {s["key"] for s in settings if s["type"] == "text"}
    seen = {}
    fields = {"button": {"arg"}, "stepper": {"min", "max"}, "readout": set(), "list": {"max", "chars", "add"}}
    for c in controls:
        if not isinstance(c, dict) or not isinstance(c.get("key"), str) or not KEY.fullmatch(c["key"]):
            raise Refused("%s: a control's key must be a-z then a-z, 0-9 and _, 16 at most" % where)
        what = "%s: control %s" % (where, c["key"])
        kind = c.get("type")
        if kind not in fields or set(c) - ({"key", "type", "label"} | fields[kind]):
            raise Refused("%s must be a button, stepper, readout or list with only its own fields" % what)
        if ("label" in c or kind != "readout") and not _label(c.get("label")):
            raise Refused("%s: label must be 1 to %d characters on one line" % (what, LABEL_MAX))
        if any(word not in texts for word in _words(c.get("label", ""))):
            raise Refused("%s: a {word} in its label must be a text setting" % what)
        if kind == "button" and "arg" in c and not _int(c["arg"], 0, 86400):
            raise Refused("%s: arg must be 0 to 86400" % what)
        if kind == "stepper" and not (_int(c.get("min"), -99999, 99999) and _int(c.get("max"), -99999, 99999)
                                      and c["min"] < c["max"]):
            raise Refused("%s: min and max must be whole numbers with min under max" % what)
        if kind == "list" and not (_int(c.get("max"), 1, 8) and _int(c.get("chars"), 1, 16) and _label(c.get("add"))):
            raise Refused("%s: max must be 1 to 8, chars 1 to 16 and add its button's words" % what)
        if c["key"] in seen:
            other = seen[c["key"]]
            # presets are one button again with an arg of its own
            if not (kind == "button" and all(x["type"] == "button" and "arg" in x for x in other)
                    and "arg" in c and all(x["arg"] != c["arg"] for x in other)):
                raise Refused("%s is there twice (a button may come again with another arg)" % what)
        seen.setdefault(c["key"], []).append(c)


def check_sheet(man, where):
    """settings and controls only for a catalog renderer and only the keys its firmware table takes c2911"""
    settings, controls = man.get("settings", []), man.get("controls", [])
    if man["uses"] not in CATALOG_USES:
        if "settings" in man or "controls" in man:
            raise Refused("%s: a %s app takes no settings or controls" % (where, man["uses"]))
        return
    first = max(CATALOG_FIRMWARE, USES_FIRMWARE.get(man["uses"], CATALOG_FIRMWARE))
    need = ".".join(map(str, first))
    if tuple(int(n) for n in man.get("minFirmware", "0.0.0").split(".")) < first:
        raise Refused("%s: a %s app needs minFirmware %s or later" % (where, man["uses"], need))
    check_settings(settings, where)
    check_controls(controls, settings, where)
    table = RENDERER_KEYS[man["uses"]]
    for s in settings:
        want = table["settings"].get(s["key"])
        if want is None or want[0] != s["type"]:
            raise Refused("%s: %s takes no %s setting %s" % (where, man["uses"], s["type"], s["key"]))
        if s["type"] == "choice" and len(s["options"]) != want[1]:
            raise Refused("%s: setting %s needs %d options" % (where, s["key"], want[1]))
        if s["type"] == "text" and s["max"] > want[1]:
            raise Refused("%s: setting %s is %d characters at most" % (where, s["key"], want[1]))
    for c in controls:
        want = table["controls"].get(c["key"])
        if want is None or want[0] != c["type"]:
            raise Refused("%s: %s takes no %s control %s" % (where, man["uses"], c["type"], c["key"]))
        if c["type"] == "list" and c["max"] > want[1]:
            raise Refused("%s: list %s is %d items at most" % (where, c["key"], want[1]))


def check_icon(body, where):
    """a 32x32 png at most 8 kb whose chunks are whole and only the ones a decoder needs"""
    bad = Refused("%s must be a 32x32 PNG of at most 8 KB with no extra chunks" % where)
    if len(body) > ICON_CAP or body[:8] != PNG:
        raise bad
    pos, kinds = 8, []
    while pos < len(body):
        if pos + 12 > len(body):
            raise bad
        length, kind = struct.unpack(">I4s", body[pos:pos + 8])
        end = pos + 8 + length
        if end + 4 > len(body) or body[end:end + 4] != struct.pack(">I", zlib.crc32(body[pos + 4:end]) & 0xFFFFFFFF):
            raise bad
        kinds.append(kind)
        if kind == b"IHDR" and struct.unpack(">II", body[pos + 8:pos + 16]) != (ICON, ICON):
            raise bad
        pos = end + 4
    if not kinds or kinds[0] != b"IHDR" or kinds[-1] != b"IEND" or any(k not in PNG_KEEP for k in kinds):
        raise bad


def check_prayer(data, where):
    """the aarti pack: pack.json lists every other file by its sha256 and nothing else is there"""
    if "pack.json" not in data:
        raise Refused("%s/data/pack.json is missing" % where)
    try:
        files = json.loads(data["pack.json"].decode("utf-8"))["files"]
        assert isinstance(files, dict)
    except (ValueError, KeyError, TypeError, AssertionError):
        raise Refused("%s/data/pack.json has no files list" % where)
    for path in sorted(data):
        if path != "pack.json" and path not in files:
            raise Refused("%s/data/%s is not in pack.json" % (where, path))
    for path, sha in sorted(files.items()):
        if path not in data:
            raise Refused("%s/data/%s is missing" % (where, path))
        if hashlib.sha256(data[path]).hexdigest() != sha:
            raise Refused("%s/data/%s does not match pack.json" % (where, path))


def check_no_data(uses):
    """a renderer whose settings live on the board + its package is the manifest and the icon alone"""
    def check(data, where):
        if data:
            raise Refused("%s: a %s app carries no data/ (its settings live on the board)" % (where, uses))
    return check


def check_list(data, where):
    """word of the day quotes fun facts and joke of the day carry their list alone + {"format": 1, "items": [[...], ...]} of 64 KB at most u517
    + the words and quotes themselves are the lifestyle batch's to check"""
    if sorted(data) != ["list.json"]:
        raise Refused("%s: its data/ is list.json alone" % where)
    if len(data["list.json"]) > LIST_CAP:
        raise Refused("%s/data/list.json is over 64 KB" % where)
    try:
        body = json.loads(data["list.json"].decode("utf-8"))
    except ValueError:
        raise Refused("%s/data/list.json is not valid JSON" % where)
    if not isinstance(body, dict) or body.get("format") != 1:
        raise Refused("%s/data/list.json must be format 1" % where)
    items = body.get("items")
    if not isinstance(items, list) or not items or not all(
            isinstance(i, list) and i and all(isinstance(t, str) for t in i) for i in items):
        raise Refused("%s/data/list.json needs items, each a list of strings" % where)


def _list_items(data, where):
    """list.json's items as check_list reads its shape + any item may hold more than strings"""
    if sorted(data) != ["list.json"]:
        raise Refused("%s: its data/ is list.json alone" % where)
    if len(data["list.json"]) > LIST_CAP:
        raise Refused("%s/data/list.json is over 64 KB" % where)
    try:
        body = json.loads(data["list.json"].decode("utf-8"))
    except ValueError:
        raise Refused("%s/data/list.json is not valid JSON" % where)
    if not isinstance(body, dict) or body.get("format") != 1:
        raise Refused("%s/data/list.json must be format 1" % where)
    items = body.get("items")
    if not isinstance(items, list) or not items or not all(isinstance(i, list) for i in items):
        raise Refused("%s/data/list.json needs items, each a list" % where)
    return items


def _drawn(text, what, where):
    """a text the board draws + no em dash and nothing of unicode's other categories (a tab, a control)"""
    if "\u2014" in text:
        raise Refused("%s: %s has an em dash" % (where, what))
    if any(unicodedata.category(ch).startswith("C") for ch in text):
        raise Refused("%s: %s has a character the board cannot draw" % (where, what))


def _sized(item, at, name, most, where):
    value = item[at]
    if not isinstance(value, str) or not 1 <= len(value) <= most or value != value.strip():
        raise Refused("%s: %s is 1 to %d characters" % (where, name, most))
    _drawn(value, name, where)
    return value


WORD_KINDS = ("noun", "verb", "adjective", "adverb")


def check_words(data, where):
    """word of the day's list u517 c2948 + [word, kind, meaning] with a word of 12 letters at most, one of four kinds,
    and a meaning of 44 characters at most, each word once"""
    check_list(data, where)
    seen = set()
    for n, item in enumerate(_list_items(data, where)):
        at = "%s/data/list.json item %d" % (where, n + 1)
        if len(item) != 3:
            raise Refused("%s is word, kind, and meaning" % at)
        word = _sized(item, 0, "word", 12, at)
        if item[1] not in WORD_KINDS:
            raise Refused("%s: kind is noun, verb, adjective, or adverb" % at)
        _sized(item, 2, "meaning", 44, at)
        if word.lower() in seen:
            raise Refused("%s: %s is in the list twice" % (at, word.lower()))
        seen.add(word.lower())


QUOTES_LAST_YEAR = 1930   # published in the us in 1930 or before is in the public domain there


def check_quotes(data, where):
    """the quotes' list u517 c2948 + [text, who, work, year] public domain by its year with text of 72 characters
    and who of 24, each text once + the work and year show it is free to use and stay in the repo"""
    seen = set()
    for n, item in enumerate(_list_items(data, where)):
        at = "%s/data/list.json item %d" % (where, n + 1)
        if len(item) != 4:
            raise Refused("%s is text, who, work, and year" % at)
        text = _sized(item, 0, "text", 72, at)
        _sized(item, 1, "who", 24, at)
        _sized(item, 2, "work", 64, at)
        year = item[3]
        if type(year) is not int:
            raise Refused("%s: year is a whole number" % at)
        if year > QUOTES_LAST_YEAR:
            raise Refused("%s: published after %d is not in the public domain" % (at, QUOTES_LAST_YEAR))
        if text in seen:
            raise Refused("%s: %s is in the list twice" % (at, text))
        seen.add(text)


FACT_MAX = 96
JOKE_MAX = 60


def check_facts(data, where):
    """fun facts u532 e7 c3135 + each item [fact, source] with the fact 1 to 96 characters on one line and once in
    the list + the source a url or a book that stays in the repo (LIST_KEEP)"""
    check_list(data, where)
    seen = set()
    for n, item in enumerate(_list_items(data, where), 1):
        what = "%s/data/list.json item %d" % (where, n)
        if len(item) != 2:
            raise Refused("%s must be [fact, source]" % what)
        fact, source = item
        if not _text(fact, FACT_MAX):
            raise Refused("%s: the fact must be 1 to %d characters on one line" % (what, FACT_MAX))
        if not source.strip():
            raise Refused("%s needs its source" % what)
        if fact in seen:
            raise Refused("%s repeats a fact" % what)
        seen.add(fact)


def check_jokes(data, where):
    """joke of the day u532 e7 c3135 + each item [setup, punchline] each 1 to 60 characters on one line + a joke
    once in the list"""
    check_list(data, where)
    seen = set()
    for n, item in enumerate(_list_items(data, where), 1):
        what = "%s/data/list.json item %d" % (where, n)
        if len(item) != 2:
            raise Refused("%s must be [setup, punchline]" % what)
        for part, text in zip(("setup", "punchline"), item):
            if not _text(text, JOKE_MAX):
                raise Refused("%s: the %s must be 1 to %d characters on one line" % (what, part, JOKE_MAX))
        if tuple(item) in seen:
            raise Refused("%s repeats a joke" % what)
        seen.add(tuple(item))


# the fields of each item a package carries + the rest stays in the repo c2946 + a fact's source never reaches the
# board c3135
LIST_KEEP = {"quotes": 2, "facts": 1}


def package_data(uses, data):
    """data/ as the package carries it + a list cut to the fields the board shows"""
    keep = LIST_KEEP.get(uses)
    if keep is None:
        return data
    items = json.loads(data["list.json"].decode("utf-8"))["items"]
    rows = ",\n".join(json.dumps(item[:keep], ensure_ascii=False) for item in items)
    return dict(data, **{"list.json": ('{"format": 1, "items": [\n%s\n]}\n' % rows).encode()})


LIST_CAP = 64 * 1024
USES_CHECKS = {"prayer": check_prayer, "countdown": check_no_data("countdown"), "sketch": check_no_data("sketch")}
# the live renders u487 + their settings live on the board too
USES_CHECKS.update({uses: check_no_data(uses) for uses in ("life", "plasma", "starfield", "fireplace")})
# the catalog apps u517 u532 + their settings live on the board and the four list apps carry their list
USES_CHECKS.update({uses: check_no_data(uses) for uses in CATALOG_USES})
USES_CHECKS.update({uses: check_list for uses in ("word", "quotes", "facts", "jokes")})   # u532 e7
USES_CHECKS.update({"word": check_words, "quotes": check_quotes})   # c2948
USES_CHECKS.update({"facts": check_facts, "jokes": check_jokes})   # c3135


def check_size(app_id, size, boards):
    for board in boards:
        if size > BOARD_CAP[board]:
            raise Refused("%s is %d bytes, over the %s's %d MB" % (app_id, size, board, BOARD_CAP[board] >> 20))


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _visible(names):
    return sorted(n for n in names if not n.startswith("."))


def read_data(folder, where):
    data = {}
    for top, dirs, names in os.walk(folder):
        dirs[:] = _visible(dirs)
        for name in _visible(names):
            path = os.path.relpath(os.path.join(top, name), folder).replace(os.sep, "/")
            if not DATA_PATH.fullmatch(path):
                raise Refused("%s/data/%s is not an allowed name (a-z, A-Z, 0-9, _ and -, .json or .bin, "
                              "%d folders deep at most)" % (where, path, MAX_DEPTH - 1))
            body = _read(os.path.join(top, name))
            if len(body) > ENTRY_CAP:
                raise Refused("%s/data/%s is over %d KB" % (where, path, ENTRY_CAP >> 10))
            data[path] = body
    return data


def read_words(body, where):
    """words.txt as the .words file a board fetches"""
    text = body.decode("ascii", "replace")
    if not text:
        raise Refused("%s/words.txt holds no words" % where)
    if not text.endswith("\n"):
        raise Refused("%s/words.txt line %d does not end with a newline" % (where, text.count("\n") + 1))
    lines = text[:-1].split("\n")
    if len(lines) > WORDS_MAX:
        raise Refused("%s/words.txt has more than %d words" % (where, WORDS_MAX))
    out, last = bytearray(), None
    for n, word in enumerate(lines, 1):
        if not WORD.fullmatch(word):
            raise Refused("%s/words.txt line %d is not five letters a to z" % (where, n))
        if last is not None and word <= last:
            raise Refused("%s/words.txt line %d is not after the line before" % (where, n))
        value = 0
        for ch in word:
            value = value * 26 + ord(ch) - ord("a")
        out += value.to_bytes(3, "big")
        last = word
    return bytes(out)


def manifest_bytes(man):
    """the one way a manifest is laid out in a package + boards always written as the index row has them"""
    man = dict(man, boards=man.get("boards", list(BOARDS)))
    # + each setting and control in the board's key order too c2910
    if "settings" in man:
        man["settings"] = [{k: s[k] for k in SETTING_KEYS if k in s} for s in man["settings"]]
    if "controls" in man:
        man["controls"] = [{k: c[k] for k in CONTROL_KEYS if k in c} for c in man["controls"]]
    return (json.dumps({key: man[key] for key in KEYS if key in man}, ensure_ascii=False, indent=2) + "\n").encode()


def write_zip(entries):
    """stored entries with every header field fixed as the dev kit's package.write lays them"""
    local, central = bytearray(), bytearray()
    for name, data in entries:
        raw = name.encode("ascii")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        header = struct.pack("<HHHHHIII", NEEDED, 0, 0, 0, ZIP_DATE, crc, len(data), len(data))
        offset = len(local)
        local += struct.pack("<I", LOCAL) + header + struct.pack("<HH", len(raw), 0) + raw + data
        central += struct.pack("<IH", CENTRAL, MADE_BY) + header
        central += struct.pack("<HHHHHII", len(raw), 0, 0, 0, 0, REGULAR << 16, offset) + raw
    end = struct.pack("<IHHHHIIH", END, 0, 0, len(entries), len(entries), len(central), len(local), 0)
    return bytes(local + central + end)


def load_app(root, category, folder):
    where = "%s/%s" % (category, folder)
    base = os.path.join(root, category, folder)
    for name in _visible(os.listdir(base)):
        if name not in REPO_ONLY + ("mooboard.json", "icon.png", "data", WORDS_FILE):
            raise Refused("%s/%s is not part of an app (mooboard.json, icon.png, data/, README.md, LICENSE)"
                          % (where, name))
    for name in ("mooboard.json", "icon.png"):
        if not os.path.isfile(os.path.join(base, name)):
            raise Refused("%s/%s is missing" % (where, name))
    man = check_manifest(_read(os.path.join(base, "mooboard.json")), category, folder)
    words = None
    if os.path.isfile(os.path.join(base, WORDS_FILE)):
        if man["uses"] not in WORDS_USES:
            raise Refused("%s/%s is not part of a %s app" % (where, WORDS_FILE, man["uses"]))
        words = read_words(_read(os.path.join(base, WORDS_FILE)), where)
    icon = _read(os.path.join(base, "icon.png"))
    check_icon(icon, where + "/icon.png")
    data = read_data(os.path.join(base, "data"), where) if os.path.isdir(os.path.join(base, "data")) else {}
    if 2 + len(data) > MAX_ENTRIES:
        raise Refused("%s has more than %d entries" % (where, MAX_ENTRIES))
    USES_CHECKS[man["uses"]](data, where)
    data = package_data(man["uses"], data)
    entries = [("mooboard.json", manifest_bytes(man)), ("icon.png", icon)]
    entries += [("data/" + path, data[path]) for path in sorted(data)]
    package = write_zip(entries)
    boards = man.get("boards", list(BOARDS))
    check_size(man["id"], len(package), boards)
    return man, icon, package, boards, len(entries), words


def find_apps(root):
    apps = []
    for top in _visible(os.listdir(root)):
        if not os.path.isdir(os.path.join(root, top)) or top in NOT_APPS:
            continue
        if top not in CATEGORIES:
            raise Refused("%s is not a category (%s)" % (top, ", ".join(CATEGORIES)))
        for folder in _visible(os.listdir(os.path.join(root, top))):
            if os.path.isdir(os.path.join(root, top, folder)):
                apps.append((top, folder))
    return sorted(apps, key=lambda a: (CATEGORIES.index(a[0]), a[1]))


def index_bytes(rows, generated, events=None):
    index = {"format": 1, "generated": generated, "categories": list(CATEGORIES), "apps": rows}
    if events:
        index["seasonal"] = events
    return (json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _openssl(openssl, args, data=None):
    result = subprocess.run([openssl] + list(args), input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Refused("openssl %s failed: %s" % (args[0], result.stderr.decode("utf-8", "replace").strip()))
    return result.stdout


def sign(openssl, key, body):
    """base64 of the der signature over body + checked against the key's public half before it is kept"""
    spki = _openssl(openssl, ["ec", "-in", key, "-pubout", "-outform", "DER"])
    if not spki.startswith(P256_SPKI_PREFIX) or len(spki) != len(P256_SPKI_PREFIX) + 64:
        raise Refused("%s is not an ECDSA P-256 key" % key)
    der = _openssl(openssl, ["dgst", "-sha256", "-sign", key], body)
    scratch = tempfile.mkdtemp()
    try:
        public, sig = os.path.join(scratch, "public.pem"), os.path.join(scratch, "index.der")
        with open(public, "wb") as f:
            f.write(_openssl(openssl, ["ec", "-in", key, "-pubout"]))
        with open(sig, "wb") as f:
            f.write(der)
        check = subprocess.run([openssl, "dgst", "-sha256", "-verify", public, "-signature", sig], input=body,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        shutil.rmtree(scratch)
    if check.returncode != 0:
        raise Refused("openssl could not verify the signature it just made")
    return base64.b64encode(der), hashlib.sha256(spki).hexdigest()


def default_generated():
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    moment = int(epoch) if epoch and epoch.isdigit() else int(time.time())
    return datetime.datetime.utcfromtimestamp(moment).strftime("%Y-%m-%dT%H:%M:%SZ")


AHEAD_LIMIT_SEC = 24 * 3600   # a stamp further ahead than this is a typo or a skewed clock


def previous_generated(path):
    """the generated stamp of an earlier index.json or None when there is none to read"""
    try:
        with open(path, "rb") as f:
            stamp = json.loads(f.read().decode("utf-8")).get("generated")
    except (OSError, ValueError, AttributeError):
        return None
    return stamp if isinstance(stamp, str) and STAMP.fullmatch(stamp) else None


def check_generated(generated, previous=None, now=None):
    """boards refuse an index older than the one they hold and never lower that floor (board review n1) + so a stamp
    must be later than the live catalog's and no more than a day ahead of now"""
    now = time.time() if now is None else now
    moment = calendar.timegm(time.strptime(generated, "%Y-%m-%dT%H:%M:%SZ"))
    if moment > now + AHEAD_LIMIT_SEC:
        raise Refused("--generated %s is more than a day ahead of now; boards would refuse every index after it"
                      % generated)
    if previous is not None and generated <= previous:
        raise Refused("--generated %s is not later than the live catalog's %s; boards would refuse it"
                      % (generated, previous))


def build(root, out, generated=None, key=None, openssl="openssl", say=lambda line: None, previous=None, now=None):
    generated = generated or default_generated()
    if not STAMP.fullmatch(generated):
        raise Refused("--generated must be YYYY-MM-DDTHH:MM:SSZ")
    check_generated(generated, previous, now)
    rows, packages, seen = [], {}, set()
    for category, folder in find_apps(root):
        man, icon, package, boards, count, words = load_app(root, category, folder)
        if man["id"] in seen:
            raise Refused("two apps have the id %s" % man["id"])
        seen.add(man["id"])
        name = "%s-%s.mooboard" % (man["id"], man["version"])
        packages[name] = package
        row = {key_: man[key_] for key_ in ("id", "name", "category", "by", "description", "version", "uses",
                                             "minFirmware") if key_ in man}
        row.update(boards=boards, file=name, size=len(package), sha256=hashlib.sha256(package).hexdigest(),
                   icon=base64.b64encode(icon).decode("ascii"))
        if words is not None:
            hosted = "%s-%s.words" % (man["id"], man["version"])
            packages[hosted] = words
            row["words"] = {"file": hosted, "size": len(words), "sha256": hashlib.sha256(words).hexdigest()}
            say("%s/%s: %s, %d words" % (category, folder, hosted, len(words) // 3))
        rows.append(row)
        say("%s/%s: %s, %d bytes, %d entries" % (category, folder, name, len(package), count))
    import seasonal
    events, event_packages = seasonal.build_events(root, generated, say)
    for row in events:
        if row["id"] in seen:
            raise Refused("two apps have the id %s" % row["id"])
        seen.add(row["id"])
    packages.update(event_packages)
    if len(rows) > APPS_MAX:
        raise Refused("%d apps, over the %d a board reads (pw_apps kCatalogAppsMax)" % (len(rows), APPS_MAX))
    index = index_bytes(rows, generated, events)
    if len(index) > INDEX_CAP:
        raise Refused("index.json is %d bytes, over 64 KB" % len(index))
    signature = sign(openssl, key, index) if key else None
    os.makedirs(out, exist_ok=True)
    for name in os.listdir(out):
        if name.endswith((".mooboard", ".words")) or name in ("index.json", "index.sig"):
            os.remove(os.path.join(out, name))
    for name, package in packages.items():
        with open(os.path.join(out, name), "wb") as f:
            f.write(package)
    with open(os.path.join(out, "index.json"), "wb") as f:
        f.write(index)
    if signature:
        with open(os.path.join(out, "index.sig"), "wb") as f:
            f.write(signature[0])
        say("index.sig: signed with the key %s" % signature[1])
    say("index.json sha256 %s" % hashlib.sha256(index).hexdigest())
    return index


def main(argv=None):
    sys.modules.setdefault("build", sys.modules[__name__])   # seasonal.py raises this module's Refused
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=os.path.join(root, "dist"))
    parser.add_argument("--key", help="the catalog's private key (PEM); signs index.json into index.sig")
    parser.add_argument("--generated", help="the index's time, YYYY-MM-DDTHH:MM:SSZ (default now)")
    parser.add_argument("--previous", help="the live catalog's index.json (default: the one in --out from the last build); "
                                           "the new stamp must be later than its own")
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args(argv)
    previous = previous_generated(args.previous or os.path.join(args.out, "index.json"))
    if args.previous and previous is None:
        print("refused: %s holds no index generated stamp" % args.previous, file=sys.stderr)
        return 1
    try:
        build(root, args.out, args.generated, args.key, args.openssl, say=print, previous=previous)
    except Refused as refused:
        print("refused: %s" % refused, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
