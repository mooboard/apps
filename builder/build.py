#!/usr/bin/env python3
"""Builds every app in this repo into dist/: <id>-<version>.mooboard, index.json, index2.json, icons2.bin, every
core in Cores/ as <id>-<version>.core with cores.json and, with --key, index.sig, index2.sig and cores.sig.

Usage: python3 builder/build.py [--out DIR] [--key PEM] [--generated YYYY-MM-DDTHH:MM:SSZ] [--previous INDEX]
                               [--previous-cores CORES] [--openssl PATH]

Apps live in <Category>/<App>/: mooboard.json (package format 2), icon.png (32x32), README.md, LICENSE,
data/ and, for Word Guess, words.txt (its guess list, kept beside the package as <id>-<version>.words). A package is a ZIP of stored entries with fixed headers and times, in a fixed order (mooboard.json,
icon.png, then data/ sorted), so the same folder always builds the same bytes. index.sig is the base64 of the
DER ECDSA P-256 signature over index.json's exact bytes, as the firmware's OTA release statement is signed, and
index2.sig and cores.sig the same over theirs. index.json is the legacy catalog older firmware reads (64 apps, 64 KB);
index2.json lists every app with its icon as a slice of icons2.bin (256 apps, 192 KB), and its listing's icon-led.png
as a second slice, "led", when it has one. A core is a shared data
package (a font family) apps name in "cores"; Cores/<id>/ holds core.json and data/ and cores.json lists every
version, the ones --previous-cores lists too, so older pins still resolve.
The firmware carries font-nunito and font-product-sans (BUILT_IN_CORES), so an app names them with no .core.
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

import listing

# the store's headings in their order from categories.txt at the repo's top, one a line + apps a to z by folder within
# each (the owner, 2026-10-20) + a new category is a line there and a folder, and boards read it with the catalog
def read_categories(root):
    with open(os.path.join(root, "categories.txt"), encoding="utf-8") as f:
        names = tuple(line.strip() for line in f if line.strip())
    if not names or len(set(names)) != len(names):
        raise SystemExit("categories.txt needs one name a line, none twice")
    for name in names:   # the board's own rule (pw_apps validCategory): a capital then letters, 1 to 24
        if len(name)>24 or not re.fullmatch(r"[A-Z][A-Za-z]*(?: [A-Z][A-Za-z]*)*", name):
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
                "waterfall", "cybercity", "synthwave", "dune",
                "game",   # the game vm's abi 1 programs u653 + after the rest as the firmware's table has it c3741
                "doom")   # the real doom engine after the game vm, renderer 62 c3870
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
                                  "follow2": ("text", 32), "cycle": ("choice", 4), "layout": ("choice", 8),
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
    "game": _row("card", SPEED),   # every game program takes the speed choice alone
    "doom": _row("card"),   # no settings, the pad or the wad's own demos c3875
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
                 "waterfall": (0, 3, 2), "cybercity": (0, 3, 2), "synthwave": (0, 3, 2), "dune": (0, 3, 2)}
# the first firmware with cores, the game vm, and lua u652 u653 + an app that needs one carries it
RUNTIME_FIRMWARE = "0.4.0-alpha.3"
USES_FIRMWARE["game"] = RUNTIME_FIRMWARE
RUNTIMES = {"game": "game", "lua54": "lua"}   # uses to index2's runtime + the legacy index lists neither
# the first firmware with doom c3870 + its pre-release keeps it out of the legacy index
USES_FIRMWARE["doom"] = "0.4.0-alpha.4"
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
# the legacy index lists only apps every board on it runs + a bare minFirmware this old at most, no cores, no runtime
LEGACY_FIRMWARE = (0, 4, 0)
# index2.json u653 + boards from RUNTIME_FIRMWARE read it alone (and index.json when it is missing) into psram
INDEX2_CAP = 192 * 1024
APPS2_MAX = 256
# 0.4.0-alpha.4 + an app's listing/icon-led.png (listing.py checks it) as index2's "led" slice of icons2.bin right
# after its icon, which a board writes to /apps/<id>/icon-led.png for Home's grid + never in the package, which older
# boards refuse past icon.png, and never in index.json
LED_FILE = "icon-led.png"
ICON = 32
NAME_MAX = 24
DESCRIPTION_MAX = 80
KEYS = ("format", "id", "name", "version", "by", "description", "category", "uses", "minFirmware", "boards",
        "cores", "settings", "controls")
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
NOT_APPS = ("builder", "dist", "Seasonal", "Cores")
# cores u652 + Cores/<id>/ is core.json and data/ + a core is never listed as an app and has no icon
CORES_DIR = "Cores"
# the cores the firmware carries, as pw_apps Cores.h kBuiltInCores lists them + an app names one with no .core at a
# version it meets (its major, its version or lower) and cores.json never lists one + index2's row keeps it as the
# manifest names it, since the board holds the two to the same cores (Package.cpp sameCores) and downloads nothing for
# a built-in id (Cores.cpp planCores)
BUILT_IN_CORES = {"font-nunito": "1.0.0", "font-product-sans": "1.0.0"}
CORE_KEYS = ("format", "kind", "id", "version", "type", "minFirmware", "boards", "roles", "files")
CORE_NEEDED = ("format", "kind", "id", "version", "type", "files")
CORE_TYPES = ("font", "data")
CORES_CAP = 16 * 1024
CORES_MAX = 64
APP_CORES_MAX = 8

ID = re.compile(r"[a-z0-9-]{1,32}")
KEY = re.compile(r"[a-z][a-z0-9_]{0,15}")
COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
BY = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")
NUMBER = r"(?:0|[1-9][0-9]{0,8})"
SEMVER = re.compile(r"%s\.%s\.%s" % (NUMBER, NUMBER, NUMBER))
SEGMENT = r"[A-Za-z0-9_-]+"
DATA_PATH = re.compile(r"%s(?:/%s){0,%d}\.(?:json|bin)" % (SEGMENT, SEGMENT, MAX_DEPTH - 1))
CORE_PATH = re.compile(r"data/%s(?:/%s){0,%d}\.[a-z0-9]{1,8}" % (SEGMENT, SEGMENT, MAX_DEPTH - 1))
ROLE = re.compile(r"[A-Z][A-Za-z0-9]{0,31}")
SHA256 = re.compile(r"[0-9a-f]{64}")
# pw_ota's order X.Y.Z-alpha.N < X.Y.Z-alpha < X.Y.Z-beta.N < X.Y.Z-beta < X.Y.Z u653
STAGES = ("alpha", "beta")
FIRMWARE = re.compile(r"(%s)\.(%s)\.(%s)(?:-(alpha|beta)(?:\.([1-9][0-9]{0,8}))?)?" % (NUMBER, NUMBER, NUMBER))
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


class Skipped(Exception):
    """an app the build leaves out with a note while the rest of the catalog builds + only DOOM, whose WAD chunks are
    never in git (doom.py)"""


class Refused(Exception):
    """a reason to stop said in one line"""


listing.Refused = Refused   # listing.py refuses as this module does


def _unique(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError(keys)
    return dict(pairs)


def firmware_floor(text):
    """the oldest firmware a minFirmware lets in as a key in pw_ota's order + a bare X.Y.Z is met by any X.Y.Z-*
    (Package.cpp) so it sorts under X.Y.Z's first pre-release u653"""
    match = FIRMWARE.fullmatch(text)
    if match is None:
        raise ValueError(text)
    head = tuple(int(n) for n in match.group(1, 2, 3))
    if match.group(4) is None:
        return head + (-1, 0)
    return head + (STAGES.index(match.group(4)), int(match.group(5)) if match.group(5) else 1 << 32)


def _firmware(version):
    return version if isinstance(version, str) else ".".join(map(str, version))


def _semver(text):
    return tuple(int(n) for n in text.split("."))


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
                                 or not FIRMWARE.fullmatch(man["minFirmware"])):
        raise Refused("%s: minFirmware must be X.Y.Z, X.Y.Z-alpha.N, or X.Y.Z-beta.N" % where)
    boards = man.get("boards", list(BOARDS))
    if (not isinstance(boards, list) or not boards or len(set(map(str, boards))) != len(boards)
            or any(b not in BOARDS for b in boards)):
        raise Refused("%s: boards must be a list of s3 and p4, each once" % where)
    if "cores" in man:
        check_cores_field(man, where)
    check_sheet(man, where)
    return man


def check_cores_field(man, where):
    """the cores an app names as {"id": "X.Y.Z"} + at least that version and below its next major u652 + resolved
    against cores.json in build"""
    cores = man["cores"]
    if (not isinstance(cores, dict) or not 1 <= len(cores) <= APP_CORES_MAX
            or not all(ID.fullmatch(k) and isinstance(v, str) and SEMVER.fullmatch(v) and _semver(v)[0] >= 1
                       for k, v in cores.items())):
        raise Refused('%s: cores must name 1 to %d cores as {"id": "X.Y.Z"}, 1.0.0 or later'
                      % (where, APP_CORES_MAX))
    if firmware_floor(man.get("minFirmware", "0.0.0")) < firmware_floor(RUNTIME_FIRMWARE):
        raise Refused("%s: an app with cores needs minFirmware %s or later" % (where, RUNTIME_FIRMWARE))


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
    need = max(_firmware(CATALOG_FIRMWARE), _firmware(USES_FIRMWARE.get(man["uses"], CATALOG_FIRMWARE)),
               key=firmware_floor)
    if firmware_floor(man.get("minFirmware", "0.0.0")) < firmware_floor(need):
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
    """data/ as the package carries it + a list cut to the fields the board shows + a game's source compiled to its
    abi 1 program u653"""
    if uses == "game":
        import game
        return {"game.bin": game.compile_game(data["game.json"]) if "game.json" in data
                else game.validate_binary(data["game.bin"])}
    keep = LIST_KEEP.get(uses)
    if keep is None:
        return data
    items = json.loads(data["list.json"].decode("utf-8"))["items"]
    rows = ",\n".join(json.dumps(item[:keep], ensure_ascii=False) for item in items)
    return dict(data, **{"list.json": ('{"format": 1, "items": [\n%s\n]}\n' % rows).encode()})


def check_game(data, where):
    """a game carries its program alone as data/game.json (assembly) or data/game.bin (abi 1) u653"""
    import game
    if set(data) not in ({"game.json"}, {"game.bin"}):
        raise Refused(where + ": a game needs data/game.json or data/game.bin alone")
    try:
        if "game.json" in data:
            game.compile_game(data["game.json"])
        else:
            game.validate_binary(data["game.bin"])
    except (ValueError, UnicodeError, TypeError) as e:
        raise Refused(where + ": " + str(e)) from e


def check_doom(data, where):
    """DOOM carries the shareware WAD alone as data/wad-0.bin to wad-3.bin + without them or with any other WAD the
    build skips it with a note and builds the rest c3874"""
    import doom
    if not data:
        raise Skipped("%s: data/ has no WAD chunks, %s" % (where, doom.HOW))
    try:
        doom.unpack(data)
    except ValueError as e:
        raise Skipped("%s: %s, %s" % (where, e, doom.HOW)) from e


LIST_CAP = 64 * 1024
USES_CHECKS = {"prayer": check_prayer, "countdown": check_no_data("countdown"), "sketch": check_no_data("sketch")}
# the live renders u487 + their settings live on the board too
USES_CHECKS.update({uses: check_no_data(uses) for uses in ("life", "plasma", "starfield", "fireplace")})
# the catalog apps u517 u532 + their settings live on the board and the four list apps carry their list
USES_CHECKS.update({uses: check_no_data(uses) for uses in CATALOG_USES})
USES_CHECKS.update({uses: check_list for uses in ("word", "quotes", "facts", "jokes")})   # u532 e7
USES_CHECKS.update({"word": check_words, "quotes": check_quotes})   # c2948
USES_CHECKS.update({"facts": check_facts, "jokes": check_jokes})   # c3135
USES_CHECKS.update({"game": check_game, "doom": check_doom})   # u653 c3874


def check_size(app_id, size, boards, what=""):
    for board in boards:
        if size > BOARD_CAP[board]:
            raise Refused("%s%s is %d bytes, over the %s's %d MB" % (app_id, what, size, board, BOARD_CAP[board] >> 20))


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
    if "cores" in man:
        man["cores"] = dict(sorted(man["cores"].items()))
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
    try:
        kind=json.loads(_read(os.path.join(base,"mooboard.json")))
    except (OSError,ValueError):
        kind=None
    if isinstance(kind,dict) and kind.get("format")==3:
        import importlib.util
        import types
        spec=importlib.util.spec_from_file_location("store_runtime",os.path.join(os.path.dirname(__file__),"runtime.py"))
        runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
        loaded=runtime.load(base,category,types.SimpleNamespace(CATEGORIES=CATEGORIES,Refused=Refused,USES=USES,check_icon=check_icon))
        least=loaded[0]["minFirmware"]
        if not FIRMWARE.fullmatch(least) or firmware_floor(least) < firmware_floor(RUNTIME_FIRMWARE):   # u653
            raise Refused("%s: a lua app needs minFirmware %s or later" % (where, RUNTIME_FIRMWARE))
        return loaded
    for name in _visible(os.listdir(base)):
        if name not in REPO_ONLY + ("mooboard.json", "icon.png", "data", WORDS_FILE, listing.FOLDER):
            raise Refused("%s/%s is not part of an app (mooboard.json, icon.png, data/, listing/, README.md, LICENSE)"
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
    try:
        data = read_data(os.path.join(base, "data"), where) if os.path.isdir(os.path.join(base, "data")) else {}
    except Refused as refused:
        if man["uses"] != "doom":
            raise
        import doom
        raise Skipped("%s, %s" % (refused, doom.HOW)) from refused
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


def check_core(body, folder, where):
    """core.json u652 + {format 1, kind core, id, version 1.0.0 or later, type, files: {data path: sha256}} and a font's
    roles {face: data path} + minFirmware and boards are RUNTIME_FIRMWARE and both boards when left out"""
    if len(body) > MANIFEST_CAP:
        raise Refused("%s is over 8 KB" % where)
    try:
        core = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
    except ValueError:
        raise Refused("%s is not valid JSON (or repeats a key)" % where)
    if not isinstance(core, dict):
        raise Refused("%s is not a JSON object" % where)
    for key in core:
        if key not in CORE_KEYS:
            raise Refused("%s: unknown key %s" % (where, key))
    for key in CORE_NEEDED:
        if key not in core:
            raise Refused("%s needs %s" % (where, key))
    if type(core["format"]) is not int or core["format"] != 1 or core["kind"] != "core":
        raise Refused('%s: format must be 1 and kind "core"' % where)
    if core["id"] != folder or not ID.fullmatch(folder):
        raise Refused("%s: id must be its folder's name, 1 to 32 of a-z, 0-9 and -" % where)
    if not isinstance(core["version"], str) or not SEMVER.fullmatch(core["version"]) or _semver(core["version"])[0] < 1:
        raise Refused("%s: version must be X.Y.Z, 1.0.0 or later" % where)
    if core["type"] not in CORE_TYPES:
        raise Refused("%s: type must be font or data" % where)
    least = core.get("minFirmware", RUNTIME_FIRMWARE)
    if (not isinstance(least, str) or not FIRMWARE.fullmatch(least)
            or firmware_floor(least) < firmware_floor(RUNTIME_FIRMWARE)):
        raise Refused("%s: minFirmware must be %s or later" % (where, RUNTIME_FIRMWARE))
    boards = core.get("boards", list(BOARDS))
    if (not isinstance(boards, list) or not boards or len(set(map(str, boards))) != len(boards)
            or any(b not in BOARDS for b in boards)):
        raise Refused("%s: boards must be a list of s3 and p4, each once" % where)
    files = core["files"]
    if (not isinstance(files, dict) or not files
            or not all(CORE_PATH.fullmatch(k) and isinstance(v, str) and SHA256.fullmatch(v) for k, v in files.items())):
        raise Refused("%s: files must list each data/ file with its sha256" % where)
    roles = core.get("roles")
    if (core["type"] == "font") != (roles is not None):
        raise Refused("%s: a font core and only a font core has roles" % where)
    if roles is not None and (not isinstance(roles, dict) or not roles
                              or not all(ROLE.fullmatch(k) and v in files for k, v in roles.items())):
        raise Refused("%s: roles must name a face and one of its files" % where)
    return core


def load_core(root, folder):
    """a core's package + core.json as committed then data/ sorted in the stored zip apps use, so the board and the
    catalog hold the same bytes + each file pinned by its sha256 in core.json"""
    where = "%s/%s" % (CORES_DIR, folder)
    base = os.path.join(root, CORES_DIR, folder)
    for name in _visible(os.listdir(base)):
        if name not in REPO_ONLY + ("core.json", "data"):
            raise Refused("%s/%s is not part of a core (core.json, data/, README.md, LICENSE)" % (where, name))
    if not os.path.isfile(os.path.join(base, "core.json")):
        raise Refused("%s/core.json is missing" % where)
    body = _read(os.path.join(base, "core.json"))
    core = check_core(body, folder, where + "/core.json")
    data = {}
    for top, dirs, names in os.walk(os.path.join(base, "data")):
        dirs[:] = _visible(dirs)
        for name in _visible(names):
            path = os.path.relpath(os.path.join(top, name), base).replace(os.sep, "/")
            if not CORE_PATH.fullmatch(path):
                raise Refused("%s/%s is not an allowed name" % (where, path))
            data[path] = _read(os.path.join(top, name))
            if len(data[path]) > ENTRY_CAP:
                raise Refused("%s/%s is over %d KB" % (where, path, ENTRY_CAP >> 10))
    if sorted(data) != sorted(core["files"]):
        raise Refused("%s: core.json files must list every data/ file and nothing else" % where)
    for path in sorted(data):
        if hashlib.sha256(data[path]).hexdigest() != core["files"][path]:
            raise Refused("%s/%s does not match core.json" % (where, path))
    if 1 + len(data) > MAX_ENTRIES:
        raise Refused("%s has more than %d entries" % (where, MAX_ENTRIES))
    package = write_zip([("core.json", body)] + [(path, data[path]) for path in sorted(data)])
    check_size(core["id"], len(package), core.get("boards", list(BOARDS)))
    return core, package


CORE_ROW = ("id", "version", "type", "file", "size", "sha256", "minFirmware", "boards")


def read_previous_cores(path):
    """the rows of the live catalog's cores.json + None when there is none to read"""
    try:
        with open(path, "rb") as f:
            rows = json.loads(f.read().decode("utf-8"))["cores"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(rows, list) or not all(
            isinstance(r, dict) and list(r) == list(CORE_ROW) and ID.fullmatch(str(r["id"]))
            and SEMVER.fullmatch(str(r["version"])) and r["file"] == "%s-%s.core" % (r["id"], r["version"])
            and FIRMWARE.fullmatch(str(r["minFirmware"])) and type(r["size"]) is int
            and isinstance(r["boards"], list) and all(b in BOARDS for b in r["boards"]) for r in rows):
        return None
    return rows


def build_cores(root, previous=None, say=lambda line: None):
    """every core in Cores/ as its row and package + the earlier versions of the live cores.json stay listed so
    older pins still resolve, and a version already out never changes its bytes u652"""
    rows, packages = [], {}
    top = os.path.join(root, CORES_DIR)
    for folder in _visible(os.listdir(top)) if os.path.isdir(top) else []:
        if not os.path.isdir(os.path.join(top, folder)):
            raise Refused("%s/%s is not a core folder" % (CORES_DIR, folder))
        if folder in BUILT_IN_CORES:
            raise Refused("%s/%s is built into the firmware and has no .core" % (CORES_DIR, folder))
        core, package = load_core(root, folder)
        name = "%s-%s.core" % (core["id"], core["version"])
        packages[name] = package
        rows.append({"id": core["id"], "version": core["version"], "type": core["type"], "file": name,
                     "size": len(package), "sha256": hashlib.sha256(package).hexdigest(),
                     "minFirmware": core.get("minFirmware", RUNTIME_FIRMWARE),
                     "boards": core.get("boards", list(BOARDS))})
        say("%s/%s: %s, %d bytes" % (CORES_DIR, folder, name, len(package)))
    built = {(r["id"], r["version"]): r for r in rows}
    for row in previous or []:
        same = built.get((row["id"], row["version"]))
        if same is None:
            rows.append(row)
        elif same["sha256"] != row["sha256"]:
            raise Refused("%s/%s %s is not the bytes already out; give it a new version"
                          % (CORES_DIR, row["id"], row["version"]))
    rows.sort(key=lambda r: (r["id"], _semver(r["version"])))
    if len(rows) > CORES_MAX:
        raise Refused("%d cores, over the %d cores.json holds" % (len(rows), CORES_MAX))
    return rows, packages


def resolve_cores(man, size, boards, cores):
    """the cores an app names as a board picks them, the newest from its minimum below the next major that its
    boards and firmware take + the app and those cores fit each board together"""
    total = size
    floor = firmware_floor(man.get("minFirmware", "0.0.0"))
    for core_id, least in sorted(man.get("cores", {}).items()):
        low = _semver(least)
        if core_id in BUILT_IN_CORES:
            have = BUILT_IN_CORES[core_id]
            if low[0] != _semver(have)[0] or low > _semver(have):
                raise Refused("%s: %s is built into the firmware at %s, below the %s it names"
                              % (man["id"], core_id, have, least))
            continue
        fits = [r for r in cores if r["id"] == core_id and low <= _semver(r["version"]) < (low[0] + 1, 0, 0)
                and all(b in r["boards"] for b in boards) and firmware_floor(r["minFirmware"]) <= floor]
        if not fits:
            raise Refused("%s: cores.json has no %s from %s below %d.0.0 for its boards and minFirmware"
                          % (man["id"], core_id, least, low[0] + 1))
        total += max(fits, key=lambda r: _semver(r["version"]))["size"]
    check_size(man["id"], total, boards, " with its cores")


def in_legacy_index(man):
    """older firmware (0.3.x, 0.4.0-alpha.1 and .2) reads index.json alone + so it lists only what each of them runs,
    a bare minFirmware of 0.4.0 at most with no cores and no runtime u653"""
    match = FIRMWARE.fullmatch(man.get("minFirmware", "0.0.0"))
    return (match.group(4) is None and firmware_floor(match.group(0))[:3] <= LEGACY_FIRMWARE
            and "cores" not in man and man["uses"] not in RUNTIMES)


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


def led_strip(root, category, folder, shown):
    """the app's listing/icon-led.png for index2's led slice + listing.check refused one that breaks its rules + None
    for an app without one"""
    if shown is None or "led" not in shown:
        return None
    return _read(os.path.join(root, category, folder, listing.FOLDER, LED_FILE))


def index_bytes(rows, generated, events=None):
    index = {"format": 1, "generated": generated, "categories": list(CATEGORIES), "apps": rows}
    if events:
        index["seasonal"] = events
    return (json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def index2_bytes(rows, generated, events=None):
    """index2.json u653 + index.json's rows with cores, runtime, and the icon and the LED icon as slices of icons2.bin"""
    index = {"format": 2, "stamp": generated, "categories": list(CATEGORIES), "apps": rows}
    if events:
        index["seasonal"] = events
    return (json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def cores_bytes(rows, generated):
    return (json.dumps({"format": 1, "stamp": generated, "cores": rows}, separators=(",", ":")) + "\n").encode()


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


SIGNED = (("index.json", "index.sig"), ("index2.json", "index2.sig"), ("cores.json", "cores.sig"))


def build(root, out, generated=None, key=None, openssl="openssl", say=lambda line: None, previous=None, now=None,
          previous_cores=None):
    generated = generated or default_generated()
    if not STAMP.fullmatch(generated):
        raise Refused("--generated must be YYYY-MM-DDTHH:MM:SSZ")
    check_generated(generated, previous, now)
    cores, packages = build_cores(root, previous_cores, say)
    rows, rows2, icons2, seen, listed_apps = [], [], bytearray(), set(), {}
    for category, folder in find_apps(root):
        try:
            man, icon, package, boards, count, words = load_app(root, category, folder)
        except Skipped as skipped:
            say("skipped %s" % skipped)
            continue
        if man["id"] in seen:
            raise Refused("two apps have the id %s" % man["id"])
        seen.add(man["id"])
        shown = listing.check(os.path.join(root, category, folder), man, icon, category, "%s/%s" % (category, folder))
        if shown is not None:
            listed_apps[man["id"]] = shown
        led = led_strip(root, category, folder, shown)
        resolve_cores(man, len(package), boards, cores)
        name = "%s-%s.mooboard" % (man["id"], man["version"])
        packages[name] = package
        row = {key_: man[key_] for key_ in ("id", "name", "category", "by", "description", "version", "uses",
                                             "minFirmware") if key_ in man}
        row.update(boards=boards, file=name, size=len(package), sha256=hashlib.sha256(package).hexdigest())
        hosted = {}
        if words is not None:
            file = "%s-%s.words" % (man["id"], man["version"])
            packages[file] = words
            hosted["words"] = {"file": file, "size": len(words), "sha256": hashlib.sha256(words).hexdigest()}
            say("%s/%s: %s, %d words" % (category, folder, file, len(words) // 3))
        if in_legacy_index(man):
            rows.append(dict(row, icon=base64.b64encode(icon).decode("ascii"), **hosted))
        row.update(hosted)
        if "cores" in man:
            row["cores"] = dict(sorted(man["cores"].items()))
        if man["uses"] in RUNTIMES:
            row["runtime"] = RUNTIMES[man["uses"]]
        row["icon"] = {"offset": len(icons2), "length": len(icon), "sha256": hashlib.sha256(icon).hexdigest()}
        icons2 += icon
        if led is not None:
            row["led"] = {"offset": len(icons2), "length": len(led), "sha256": hashlib.sha256(led).hexdigest()}
            icons2 += led
        rows2.append(row)
        say("%s/%s: %s, %d bytes, %d entries" % (category, folder, name, len(package), count))
    import seasonal
    events, event_packages = seasonal.build_events(root, generated, say)
    for row in events:
        if row["id"] in seen:
            raise Refused("two apps have the id %s" % row["id"])
        seen.add(row["id"])
    packages.update(event_packages)
    clash = sorted({r["id"] for r in cores} & seen)
    if clash:
        raise Refused("the core %s has an app's id" % clash[0])
    if len(rows) > APPS_MAX:
        raise Refused("%d apps, over the %d a board reads (pw_apps kCatalogAppsMax)" % (len(rows), APPS_MAX))
    if len(rows2) > APPS2_MAX:
        raise Refused("%d apps, over the %d index2.json holds" % (len(rows2), APPS2_MAX))
    index, index2, listed = index_bytes(rows, generated, events), index2_bytes(rows2, generated, events), \
        cores_bytes(cores, generated)
    for body, file, cap in ((index, "index.json", INDEX_CAP), (index2, "index2.json", INDEX2_CAP),
                            (listed, "cores.json", CORES_CAP)):
        if len(body) > cap:
            raise Refused("%s is %d bytes, over %d KB" % (file, len(body), cap >> 10))
    check_listings_top(root, listed_apps)
    bodies = {"index.json": index, "index2.json": index2, "cores.json": listed, "icons2.bin": bytes(icons2)}
    signatures = {sig: sign(openssl, key, bodies[file]) for file, sig in SIGNED} if key else {}
    os.makedirs(out, exist_ok=True)
    kept = {r["file"] for r in cores}
    for name in os.listdir(out):
        if (name.endswith((".mooboard", ".words")) or name in bodies or name in dict(SIGNED).values()
                or (name.endswith(".core") and name not in kept)):
            os.remove(os.path.join(out, name))
    for name, package in sorted(packages.items()):
        with open(os.path.join(out, name), "wb") as f:
            f.write(package)
    for name, body in sorted(bodies.items()):
        with open(os.path.join(out, name), "wb") as f:
            f.write(body)
    for name, signature in sorted(signatures.items()):
        with open(os.path.join(out, name), "wb") as f:
            f.write(signature[0])
        say("%s: signed with the key %s" % (name, signature[1]))
    say("index.json: %d apps, %d bytes, sha256 %s" % (len(rows), len(index), hashlib.sha256(index).hexdigest()))
    say("index2.json: %d apps, %d bytes, sha256 %s" % (len(rows2), len(index2), hashlib.sha256(index2).hexdigest()))
    say("cores.json: %d cores, %d bytes, sha256 %s" % (len(cores), len(listed), hashlib.sha256(listed).hexdigest()))
    return index


def listings_rows(root):
    """every app's listing row by id, checked (listing.py)"""
    rows = {}
    for category, folder in find_apps(root):
        try:
            man, icon = load_app(root, category, folder)[:2]
        except Skipped:
            continue
        shown = listing.check(os.path.join(root, category, folder), man, icon, category, "%s/%s" % (category, folder))
        if shown is not None:
            rows[man["id"]] = shown
    return rows


def check_listings_top(root, rows):
    """the committed listings.json is the listings' own + none while no app has a listing"""
    path = os.path.join(root, listing.TOP)
    have = _read(path) if os.path.isfile(path) else None
    if (have or None) != (listing.top_bytes(rows) if rows else None):
        raise Refused("%s is not the listings' own: run python3 builder/build.py --listings and commit it" % listing.TOP)


def main(argv=None):
    sys.modules.setdefault("build", sys.modules[__name__])   # seasonal.py raises this module's Refused
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=os.path.join(root, "dist"))
    parser.add_argument("--key", help="the catalog's private key (PEM); signs index.json into index.sig")
    parser.add_argument("--generated", help="the index's time, YYYY-MM-DDTHH:MM:SSZ (default now)")
    parser.add_argument("--previous", help="the live catalog's index.json (default: the one in --out from the last build); "
                                           "the new stamp must be later than its own")
    parser.add_argument("--previous-cores", help="the live catalog's cores.json (default: the one beside the previous "
                                                 "index); its earlier core versions stay listed")
    parser.add_argument("--openssl", default="openssl")
    parser.add_argument("--listings", action="store_true", help="write listings.json at the repo's top and stop")
    args = parser.parse_args(argv)
    if args.listings:
        try:
            rows = listings_rows(root)
        except Refused as refused:
            print("refused: %s" % refused, file=sys.stderr)
            return 1
        with open(os.path.join(root, listing.TOP), "wb") as f:
            f.write(listing.top_bytes(rows))
        print("%s: %d apps" % (listing.TOP, len(rows)))
        return 0
    floor = args.previous or os.path.join(args.out, "index.json")
    previous = previous_generated(floor)
    if args.previous and previous is None:
        print("refused: %s holds no index generated stamp" % args.previous, file=sys.stderr)
        return 1
    cores_path = args.previous_cores or os.path.join(os.path.dirname(os.path.abspath(floor)), "cores.json")
    previous_cores = read_previous_cores(cores_path)
    if previous_cores is None and (args.previous_cores or os.path.exists(cores_path)):
        print("refused: %s is not a cores.json" % cores_path, file=sys.stderr)
        return 1
    try:
        build(root, args.out, args.generated, args.key, args.openssl, say=print, previous=previous,
              previous_cores=previous_cores)
    except Refused as refused:
        print("refused: %s" % refused, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
