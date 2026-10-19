#!/usr/bin/env python3
"""Builds every app in this repo into dist/: <id>-<version>.mooboard, index.json and, with --key, index.sig.

Usage: python3 builder/build.py [--out DIR] [--key PEM] [--generated YYYY-MM-DDTHH:MM:SSZ] [--openssl PATH]

Apps live in <Category>/<App>/: mooboard.json (package format 2), icon.png (32x32), README.md, LICENSE and
data/. A package is a ZIP of stored entries with fixed headers and times, in a fixed order (mooboard.json,
icon.png, then data/ sorted), so the same folder always builds the same bytes. index.sig is the base64 of the
DER ECDSA P-256 signature over index.json's exact bytes, as the firmware's OTA release statement is signed.
Python 3 standard library and the openssl command only.
"""
import argparse
import base64
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
import zlib

CATEGORIES = ("Lifestyle", "Games")
USES = ("prayer", "countdown", "sketch", "life", "plasma", "starfield", "fireplace")   # the firmware's renderers (pw::AppRenderer), in its order
BOARDS = ("s3", "p4")
BOARD_CAP = {"s3": 2 * 1024 * 1024, "p4": 8 * 1024 * 1024}
ENTRY_CAP = 512 * 1024
MAX_ENTRIES = 200
MAX_DEPTH = 3
MANIFEST_CAP = 8 * 1024
ICON_CAP = 8 * 1024
INDEX_CAP = 64 * 1024
ICON = 32
NAME_MAX = 24
DESCRIPTION_MAX = 80
KEYS = ("format", "id", "name", "version", "by", "description", "category", "uses", "minFirmware", "boards")
NEEDED_KEYS = ("format", "id", "name", "version", "by", "description", "category")
REPO_ONLY = ("README.md", "LICENSE")
NOT_APPS = ("builder", "dist", "Seasonal")

ID = re.compile(r"[a-z0-9-]{1,32}")
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
    return man


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


USES_CHECKS = {"prayer": check_prayer, "countdown": check_no_data("countdown"), "sketch": check_no_data("sketch")}
# the live renders u487 + their settings live on the board too
USES_CHECKS.update({uses: check_no_data(uses) for uses in ("life", "plasma", "starfield", "fireplace")})


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


def manifest_bytes(man):
    """the one way a manifest is laid out in a package + boards always written as the index row has them"""
    man = dict(man, boards=man.get("boards", list(BOARDS)))
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
        if name not in REPO_ONLY + ("mooboard.json", "icon.png", "data"):
            raise Refused("%s/%s is not part of an app (mooboard.json, icon.png, data/, README.md, LICENSE)"
                          % (where, name))
    for name in ("mooboard.json", "icon.png"):
        if not os.path.isfile(os.path.join(base, name)):
            raise Refused("%s/%s is missing" % (where, name))
    man = check_manifest(_read(os.path.join(base, "mooboard.json")), category, folder)
    icon = _read(os.path.join(base, "icon.png"))
    check_icon(icon, where + "/icon.png")
    data = read_data(os.path.join(base, "data"), where) if os.path.isdir(os.path.join(base, "data")) else {}
    if 2 + len(data) > MAX_ENTRIES:
        raise Refused("%s has more than %d entries" % (where, MAX_ENTRIES))
    USES_CHECKS[man["uses"]](data, where)
    entries = [("mooboard.json", manifest_bytes(man)), ("icon.png", icon)]
    entries += [("data/" + path, data[path]) for path in sorted(data)]
    package = write_zip(entries)
    boards = man.get("boards", list(BOARDS))
    check_size(man["id"], len(package), boards)
    return man, icon, package, boards, len(entries)


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


def build(root, out, generated=None, key=None, openssl="openssl", say=lambda line: None):
    generated = generated or default_generated()
    if not STAMP.fullmatch(generated):
        raise Refused("--generated must be YYYY-MM-DDTHH:MM:SSZ")
    rows, packages, seen = [], {}, set()
    for category, folder in find_apps(root):
        man, icon, package, boards, count = load_app(root, category, folder)
        if man["id"] in seen:
            raise Refused("two apps have the id %s" % man["id"])
        seen.add(man["id"])
        name = "%s-%s.mooboard" % (man["id"], man["version"])
        packages[name] = package
        row = {key_: man[key_] for key_ in ("id", "name", "category", "by", "description", "version", "uses",
                                             "minFirmware") if key_ in man}
        row.update(boards=boards, file=name, size=len(package), sha256=hashlib.sha256(package).hexdigest(),
                   icon=base64.b64encode(icon).decode("ascii"))
        rows.append(row)
        say("%s/%s: %s, %d bytes, %d entries" % (category, folder, name, len(package), count))
    import seasonal
    events, event_packages = seasonal.build_events(root, generated, say)
    for row in events:
        if row["id"] in seen:
            raise Refused("two apps have the id %s" % row["id"])
        seen.add(row["id"])
    packages.update(event_packages)
    index = index_bytes(rows, generated, events)
    if len(index) > INDEX_CAP:
        raise Refused("index.json is %d bytes, over 64 KB" % len(index))
    signature = sign(openssl, key, index) if key else None
    os.makedirs(out, exist_ok=True)
    for name in os.listdir(out):
        if name.endswith(".mooboard") or name in ("index.json", "index.sig"):
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
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args(argv)
    try:
        build(root, args.out, args.generated, args.key, args.openssl, say=print)
    except Refused as refused:
        print("refused: %s" % refused, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
