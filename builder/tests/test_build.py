import base64
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
import zlib

BUILDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BUILDER)
sys.path.insert(0, BUILDER)
import build  # noqa: E402

GENERATED = "2026-10-19T08:00:00Z"


def png(width=32, height=32):
    rows = b"".join(b"\x00" + b"\x10\x20\x30" * width for _ in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def manifest(**changes):
    out = {"format": 2, "id": "prayer", "name": "Prayer", "version": "1.0.0", "by": "mooboard",
           "description": "Aarti words in time with the recording.", "category": "Lifestyle", "uses": "prayer",
           "minFirmware": "0.3.0"}
    out.update(changes)
    return {key: value for key, value in out.items() if value is not None}


def pack_files():
    files = {"aartis/om.json": b'{"slug":"om"}', "glyphs/om.bin": b"PWG1\x00\x00\x00\x00",
             "recordings/yt-AbC_12.json": b'{"aarti":"om"}'}
    index = {"format": 1, "files": {path: hashlib.sha256(body).hexdigest() for path, body in files.items()}}
    files["pack.json"] = json.dumps(index).encode()
    return files


class Tree:
    """a throwaway store repo with one app folder"""

    def __init__(self, test):
        self.root = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.root)
        self.app("Lifestyle", "Prayer", manifest(), pack_files())

    def write(self, path, body):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(body if isinstance(body, bytes) else body.encode())

    def app(self, category, folder, man, data, icon=None):
        base = "%s/%s/" % (category, folder)
        self.write(base + "mooboard.json", json.dumps(man, indent=2) if isinstance(man, dict) else man)
        self.write(base + "icon.png", png() if icon is None else icon)
        self.write(base + "README.md", "# %s\n" % folder)
        for path, body in data.items():
            self.write(base + "data/" + path, body)

    def build(self, **options):
        out = os.path.join(self.root, "dist")
        build.build(self.root, out, generated=GENERATED, **options)
        return out


def read(path):
    with open(path, "rb") as f:
        return f.read()


class Reproducible(unittest.TestCase):
    def test_same_tree_same_bytes(self):
        tree = Tree(self)
        first = tree.build()
        a = {name: read(os.path.join(first, name)) for name in os.listdir(first)}
        # newer times on every file and a fresh output folder change nothing
        for folder, _, names in os.walk(os.path.join(tree.root, "Lifestyle")):
            for name in names:
                os.utime(os.path.join(folder, name), (2000000000, 2000000000))
        shutil.rmtree(first)
        second = tree.build()
        b = {name: read(os.path.join(second, name)) for name in os.listdir(second)}
        self.assertEqual(sorted(a), ["index.json", "prayer-1.0.0.mooboard"])
        self.assertEqual(a, b)

    def test_files_written_in_another_order_same_bytes(self):
        one, two = Tree(self), Tree(self)
        shutil.rmtree(os.path.join(two.root, "Lifestyle"))
        data = pack_files()
        two.app("Lifestyle", "Prayer", manifest(), dict(reversed(list(data.items()))))
        self.assertEqual(read(os.path.join(one.build(), "prayer-1.0.0.mooboard")),
                         read(os.path.join(two.build(), "prayer-1.0.0.mooboard")))


class Package(unittest.TestCase):
    def setUp(self):
        self.tree = Tree(self)
        self.out = self.tree.build()
        self.data = read(os.path.join(self.out, "prayer-1.0.0.mooboard"))

    def test_stored_entries_in_the_fixed_order_with_fixed_times(self):
        z = zipfile.ZipFile(io.BytesIO(self.data))
        self.assertIsNone(z.testzip())
        self.assertEqual([i.filename for i in z.infolist()],
                         ["mooboard.json", "icon.png", "data/aartis/om.json", "data/glyphs/om.bin", "data/pack.json",
                          "data/recordings/yt-AbC_12.json"])
        for info in z.infolist():
            self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(info.external_attr, build.REGULAR << 16)
            self.assertEqual(info.extra, b"")
        for path, body in pack_files().items():
            self.assertEqual(z.read("data/" + path), body)

    def test_manifest_is_laid_out_one_way(self):
        body = zipfile.ZipFile(io.BytesIO(self.data)).read("mooboard.json")
        self.assertEqual(body, (json.dumps(manifest(boards=["s3", "p4"]), ensure_ascii=False, indent=2)
                                + "\n").encode())
        self.assertEqual(list(json.loads(body)), ["format", "id", "name", "version", "by", "description",
                                                  "category", "uses", "minFirmware", "boards"])

    def test_index_is_the_contract_shape(self):
        raw = read(os.path.join(self.out, "index.json"))
        index = json.loads(raw)
        self.assertEqual(list(index), ["format", "generated", "categories", "apps"])
        self.assertEqual((index["format"], index["generated"], index["categories"]),
                         (1, GENERATED, ["Lifestyle", "Ambiance", "Games", "Tools"]))
        row = index["apps"][0]
        self.assertEqual(list(row), ["id", "name", "category", "by", "description", "version", "uses", "minFirmware",
                                     "boards", "file", "size", "sha256", "icon"])
        self.assertEqual(row["boards"], ["s3", "p4"])
        self.assertEqual(row["file"], "prayer-1.0.0.mooboard")
        self.assertEqual(row["size"], len(self.data))
        self.assertEqual(row["sha256"], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(base64.b64decode(row["icon"]), png())
        self.assertFalse(os.path.exists(os.path.join(self.out, "index.sig")))

    def test_a_rebuild_drops_old_packages_only(self):
        keep = os.path.join(self.out, "notes.txt")
        stale = os.path.join(self.out, "prayer-0.9.0.mooboard")
        for path in (keep, stale):
            with open(path, "w") as f:
                f.write("x")
        self.tree.build()
        self.assertTrue(os.path.exists(keep))
        self.assertFalse(os.path.exists(stale))


class Rules(unittest.TestCase):
    def refused(self, edit, words):
        tree = Tree(self)
        edit(tree)
        out = os.path.join(tree.root, "dist")
        with self.assertRaises(build.Refused) as caught:
            build.build(tree.root, out, generated=GENERATED)
        self.assertIn(words, str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(out, "index.json")))

    def replace(self, tree, man=None, data=None, icon=None, folder="Prayer", category="Lifestyle"):
        shutil.rmtree(os.path.join(tree.root, "Lifestyle"))
        tree.app(category, folder, manifest() if man is None else man, pack_files() if data is None else data, icon)

    def test_folder_not_a_category(self):
        self.refused(lambda t: self.replace(t, category="Utilities"), "Utilities is not a category")

    def test_manifest_category_must_be_its_folder(self):
        self.refused(lambda t: self.replace(t, manifest(category="Games")), "category must be Lifestyle")

    def test_name_is_the_folder(self):
        self.refused(lambda t: self.replace(t, manifest(name="prayer")), "name must be the folder's name")

    def test_format(self):
        self.refused(lambda t: self.replace(t, manifest(format=1)), "format must be 2")

    def test_unknown_key(self):
        self.refused(lambda t: self.replace(t, manifest(author="x")), "unknown key author")

    def test_repeated_key(self):
        text = json.dumps(manifest(), indent=2)[:-2] + ',\n  "id": "other"\n}'
        self.refused(lambda t: self.replace(t, text), "not valid JSON")

    def test_id(self):
        self.refused(lambda t: self.replace(t, manifest(id="Prayer")), "id must be")

    def test_version(self):
        self.refused(lambda t: self.replace(t, manifest(version="1.0")), "version must be")

    def test_min_firmware(self):
        self.refused(lambda t: self.replace(t, manifest(minFirmware="0.3")), "minFirmware must be")

    def test_boards(self):
        self.refused(lambda t: self.replace(t, manifest(boards=["s3", "s3"])), "boards must be")
        self.refused(lambda t: self.replace(t, manifest(boards=["c6"])), "boards must be")

    def test_uses(self):
        self.refused(lambda t: self.replace(t, manifest(uses="doom")), "uses must be one of")

    def test_gif_apps_wait(self):
        self.refused(lambda t: self.replace(t, manifest(uses=None)), "GIF apps")

    def test_description(self):
        self.refused(lambda t: self.replace(t, manifest(description="")), "description must be")
        self.refused(lambda t: self.replace(t, manifest(description="a\nb")), "description must be")

    def test_icon(self):
        self.refused(lambda t: self.replace(t, icon=png(16, 16)), "icon.png must be a 32x32 PNG")
        self.refused(lambda t: self.replace(t, icon=b"GIF89a"), "icon.png must be a 32x32 PNG")

    def test_audio_is_refused(self):
        data = dict(pack_files(), **{"recordings/song.mp3": b"ID3"})
        self.refused(lambda t: self.replace(t, data=data), "data/recordings/song.mp3 is not an allowed name")

    def test_stray_file_in_the_app_folder(self):
        self.refused(lambda t: t.write("Lifestyle/Prayer/song.wav", b"RIFF"), "song.wav is not part of an app")

    def test_too_deep(self):
        data = dict(pack_files(), **{"a/b/c/d.json": b"{}"})
        self.refused(lambda t: self.replace(t, data=data), "data/a/b/c/d.json is not an allowed name")

    def test_entry_too_big(self):
        data = pack_files()
        data["glyphs/om.bin"] = b"\0" * (build.ENTRY_CAP + 1)
        self.refused(lambda t: self.replace(t, data=data), "data/glyphs/om.bin is over")

    def test_package_too_big_for_the_s3(self):
        files = {"glyphs/g%d.bin" % i: bytes([i]) * build.ENTRY_CAP for i in range(5)}
        files["pack.json"] = json.dumps({"files": {path: hashlib.sha256(body).hexdigest()
                                                   for path, body in files.items()}}).encode()
        self.refused(lambda t: self.replace(t, data=files), "over the s3's 2 MB")
        # a p4-only app may take 8 MB
        tree = Tree(self)
        self.replace(tree, manifest(boards=["p4"]), files)
        out = tree.build()
        self.assertGreater(os.path.getsize(os.path.join(out, "prayer-1.0.0.mooboard")), build.BOARD_CAP["s3"])

    def test_too_many_entries(self):
        data = {"g/%d.bin" % i: b"" for i in range(build.MAX_ENTRIES - 1)}
        self.refused(lambda t: self.replace(t, data=data), "more than 200 entries")

    def test_prayer_pack_sha256(self):
        data = pack_files()
        data["glyphs/om.bin"] = b"changed"
        self.refused(lambda t: self.replace(t, data=data), "glyphs/om.bin does not match pack.json")

    def test_prayer_pack_lists_every_file(self):
        data = dict(pack_files(), **{"aartis/extra.json": b"{}"})
        self.refused(lambda t: self.replace(t, data=data), "aartis/extra.json is not in pack.json")
        data = pack_files()
        del data["glyphs/om.bin"]
        self.refused(lambda t: self.replace(t, data=data), "glyphs/om.bin is missing")

    def test_settings_apps_carry_no_data(self):
        countdowns = manifest(id="countdowns", name="Countdowns", uses="countdown",
                              description="Days until the dates you care about.")
        self.refused(lambda t: self.replace(t, countdowns, {"items.json": b"[]"}, folder="Countdowns"),
                     "Lifestyle/Countdowns: a countdown app carries no data/")
        sketch = manifest(id="sketch", name="Sketch", uses="sketch", description="Draw on your phone.")
        self.refused(lambda t: self.replace(t, sketch, {"art/one.bin": b"x"}, folder="Sketch"),
                     "Lifestyle/Sketch: a sketch app carries no data/")

    def test_live_renders_carry_no_data(self):
        for uses, name in (("life", "Game of Life"), ("plasma", "Plasma"), ("starfield", "Starfield"),
                           ("fireplace", "Fireplace")):
            live = manifest(id=uses, name=name, uses=uses, description="A live render.")
            self.refused(lambda t: self.replace(t, live, {"seed.json": b"{}"}, folder=name),
                         "Lifestyle/%s: a %s app carries no data/" % (name, uses))

    def test_settings_apps_are_their_manifest_and_icon(self):
        tree = Tree(self)
        tree.app("Lifestyle", "Countdowns", manifest(id="countdowns", name="Countdowns", uses="countdown",
                                                     description="Days until the dates you care about."), {})
        out = tree.build()
        names = zipfile.ZipFile(os.path.join(out, "countdowns-1.0.0.mooboard")).namelist()
        self.assertEqual(names, ["mooboard.json", "icon.png"])
        index = json.loads(read(os.path.join(out, "index.json")))
        self.assertEqual([(a["id"], a["uses"]) for a in index["apps"]], [("countdowns", "countdown"), ("prayer", "prayer")])

    def test_two_apps_with_one_id(self):
        def edit(tree):
            tree.app("Games", "Prayer", manifest(category="Games"), pack_files())
        self.refused(edit, "two apps have the id prayer")


def scoreboard(**changes):
    """a catalog tool app with settings and controls u517 + written in an order the board does not keep"""
    out = manifest(id="scoreboard", name="Scoreboard", uses="scoreboard", category="Tools", minFirmware="0.3.2",
                   description="Two scores you keep from your phone.")
    out["settings"] = [{"type": "text", "key": "left", "label": "Left name", "max": 8, "default": "Home"},
                       {"key": "right", "type": "text", "label": "Right name", "default": "Guest", "max": 8},
                       {"key": "left_color", "type": "color", "label": "Left color", "default": "#3C9DFF"}]
    out["controls"] = [{"label": "{left}", "key": "left", "type": "stepper", "max": 999, "min": 0},
                       {"key": "right", "type": "stepper", "label": "{right}", "min": 0, "max": 999},
                       {"key": "reset", "type": "button", "label": "Reset"}]
    out.update(changes)
    return {key: value for key, value in out.items() if value is not None}


class Catalog(unittest.TestCase):
    """the catalog apps u517: settings and controls checked as the board reads them and held to the renderers' key
    table, laid out in the board's key order, and word and quotes' list c2910 c2911 c2914"""

    def tree(self, man, data=None, category="Tools", folder="Scoreboard"):
        tree = Tree(self)
        tree.app(category, folder, man, data or {})
        return tree

    def refused(self, man, words, data=None, category="Tools", folder="Scoreboard"):
        tree = self.tree(man, data, category, folder)
        with self.assertRaises(build.Refused) as caught:
            tree.build()
        self.assertIn(words, str(caught.exception))

    def test_a_tool_app_builds_in_the_boards_key_order(self):
        out = self.tree(scoreboard()).build()
        body = zipfile.ZipFile(os.path.join(out, "scoreboard-1.0.0.mooboard")).read("mooboard.json").decode()
        man = json.loads(body)
        self.assertEqual(list(man)[-2:], ["settings", "controls"])
        self.assertEqual(list(man["settings"][0]), ["key", "type", "label", "default", "max"])
        self.assertEqual(list(man["controls"][0]), ["key", "type", "label", "min", "max"])
        self.assertEqual(body, json.dumps(man, ensure_ascii=False, indent=2) + "\n")
        row = [a for a in json.loads(read(os.path.join(out, "index.json")))["apps"] if a["id"] == "scoreboard"][0]
        self.assertNotIn("settings", row)   # the index stays the catalog's rows
        self.assertEqual(row["uses"], "scoreboard")

    def test_every_catalog_renderer_is_known(self):
        # both waves u517 u523 + a card takes its turn a hold holds the panel and ok to wake does both e6
        self.assertEqual(len(build.CATALOG_USES), 32)
        self.assertEqual(list(build.RENDERER_KEYS), list(build.CATALOG_USES))
        self.assertEqual(build.USES[7:], build.CATALOG_USES)
        kinds = {uses: row["kind"] for uses, row in build.RENDERER_KEYS.items()}
        self.assertEqual(sorted(u for u, k in kinds.items() if k == "hold"),
                         ["chessclock", "dice", "intervals", "pomodoro", "scoreboard", "tally", "timer", "wheel"])
        self.assertEqual([u for u, k in kinds.items() if k == "night"], ["oktowake"])
        self.assertEqual(set(kinds.values()), {"card", "hold", "night"})

    def test_keys_the_renderer_does_not_take(self):
        self.refused(scoreboard(controls=[{"key": "undo", "type": "button", "label": "Undo"}]),
                     "scoreboard takes no button control undo")
        self.refused(scoreboard(controls=[{"key": "reset", "type": "readout", "label": "Reset"}]),
                     "scoreboard takes no readout control reset")
        self.refused(scoreboard(settings=[{"key": "tint", "type": "color", "label": "Tint", "default": "#FFFFFF"}],
                                controls=[]), "scoreboard takes no color setting tint")
        self.refused(scoreboard(settings=[{"key": "left", "type": "text", "label": "Left", "default": "Home",
                                           "max": 9}], controls=[]), "setting left is 8 characters at most")
        pong = manifest(id="pong-clock", name="Pong Clock", uses="pong", category="Games", minFirmware="0.3.2",
                        description="Two paddles play, and the score is the time.",
                        settings=[{"key": "speed", "type": "choice", "label": "Speed", "default": "Slow",
                                   "options": ["Slow", "Fast"]}])
        self.refused(pong, "setting speed needs 3 options", category="Games", folder="Pong Clock")
        habits = manifest(id="habit-streaks", name="Habit Streaks", uses="habits", minFirmware="0.3.2",
                          description="Tap a habit on your phone and watch the streak grow.",
                          controls=[{"key": "habits", "type": "list", "label": "Habits", "max": 7, "chars": 12,
                                     "add": "Add habit"}])
        self.refused(habits, "list habits is 6 items at most", category="Lifestyle", folder="Habit Streaks")
        # a renderer from before the catalog takes none
        self.refused(manifest(id="countdowns", name="Countdowns", uses="countdown", description="Days.",
                              settings=[]), "a countdown app takes no settings or controls",
                     category="Lifestyle", folder="Countdowns")

    def test_controls_out_of_their_rules(self):
        presets = [{"key": "start", "type": "button", "label": "Go", "arg": i} for i in range(17)]
        timer = manifest(id="timer", name="Timer", uses="timer", minFirmware="0.3.2", category="Tools",
                         description="A countdown or a stopwatch you run from your phone.")
        self.refused(dict(timer, controls=presets), "controls must be a list of at most 16", folder="Timer")
        self.tree(dict(timer, controls=presets[:16]), folder="Timer").build()
        self.refused(scoreboard(controls=[{"key": "reset", "type": "button", "label": "R" * 25}]),
                     "label must be 1 to 24 characters")
        # a format character the board's label rule refuses
        self.refused(scoreboard(controls=[{"key": "reset", "type": "button", "label": "Re\u200bset"}]),
                     "label must be 1 to 24 characters")
        self.refused(scoreboard(controls=[{"key": "left", "type": "stepper", "label": "{left_color}", "min": 0,
                                           "max": 9}]), "a {word} in its label must be a text setting")
        self.refused(scoreboard(controls=[{"key": "left", "type": "stepper", "label": "Left", "min": 5, "max": 5}]),
                     "min and max must be whole numbers with min under max")
        self.refused(scoreboard(controls=[{"key": "reset", "type": "button", "label": "Reset", "min": 0}]),
                     "with only its own fields")
        self.refused(scoreboard(controls=[{"key": "reset", "type": "button", "label": "Reset"},
                                          {"key": "reset", "type": "button", "label": "Again"}]), "is there twice")
        self.refused(dict(timer, controls=[{"key": "start", "type": "button", "label": "Go", "arg": 86401}]),
                     "arg must be 0 to 86400", folder="Timer")

    def test_a_catalog_app_needs_the_firmware_that_reads_it(self):
        # the firmware with the renderers is 0.3.2 u523
        self.refused(scoreboard(minFirmware="0.3.1"), "a scoreboard app needs minFirmware 0.3.2 or later")
        self.refused(scoreboard(minFirmware=None), "needs minFirmware 0.3.2")
        self.tree(scoreboard(minFirmware="0.3.2")).build()

    def test_settings_out_of_their_rules(self):
        self.refused(scoreboard(settings=[{"key": "left", "type": "text", "label": "Left", "default": "Home"}],
                                controls=[]), "max must be 1 to 32")
        self.refused(scoreboard(settings=[{"key": "left_color", "type": "color", "label": "Left",
                                           "default": "blue"}], controls=[]), "default must be a color")

    def test_word_and_quotes_carry_their_list(self):
        word = manifest(id="word-of-the-day", name="Word of the Day", uses="word", minFirmware="0.3.2",
                        description="A new word and what it means, every day.")
        good = {"list.json": json.dumps({"format": 1, "items": [["petrichor", "noun", "the smell of rain"]]}).encode()}
        out = self.tree(word, good, "Lifestyle", "Word of the Day").build()
        names = zipfile.ZipFile(os.path.join(out, "word-of-the-day-1.0.0.mooboard")).namelist()
        self.assertEqual(names, ["mooboard.json", "icon.png", "data/list.json"])
        self.refused(word, "its data/ is list.json alone", {"words.json": good["list.json"]}, "Lifestyle",
                     "Word of the Day")
        self.refused(word, "its data/ is list.json alone", {}, "Lifestyle", "Word of the Day")
        self.refused(word, "must be format 1", {"list.json": b'{"items": [["a"]]}'}, "Lifestyle", "Word of the Day")
        self.refused(word, "needs items", {"list.json": b'{"format": 1, "items": [[1]]}'}, "Lifestyle",
                     "Word of the Day")
        big = {"list.json": json.dumps({"format": 1, "items": [["x" * 100]] * 700}).encode()}
        self.refused(word, "over 64 KB", big, "Lifestyle", "Word of the Day")
        self.refused(scoreboard(), "a scoreboard app carries no data/", {"seed.json": b"{}"})

    def word_list(self, items):
        return {"list.json": json.dumps({"format": 1, "items": items}).encode()}

    def test_the_words_are_checked(self):
        # u517 c2948 + a word of 12 letters at most, one of four kinds, a meaning of 44 characters, each once
        word = manifest(id="word-of-the-day", name="Word of the Day", uses="word", minFirmware="0.3.2",
                        description="A new word and what it means, every day.")
        good = [["petrichor", "noun", "the smell of rain on dry ground"], ["jaunt", "noun", "a short trip for fun"]]
        self.tree(word, self.word_list(good), "Lifestyle", "Word of the Day").build()
        for items, words in (([["petrichor", "noun"]], "is word, kind, and meaning"),
                             ([["serendipitous", "adjective", "found by luck"]], "word is 1 to 12 characters"),
                             ([["jaunt", "pronoun", "a short trip"]], "kind is noun, verb, adjective, or adverb"),
                             ([["jaunt", "noun", "x" * 45]], "meaning is 1 to 44 characters"),
                             ([["jaunt", "noun", "a trip"], ["Jaunt", "noun", "a walk"]], "jaunt is in the list twice"),
                             ([["jaunt", "noun", "a short trip \u2014 for fun"]], "has an em dash"),
                             ([["jaunt", "noun", "a short\ttrip"]], "has a character the board cannot draw")):
            with self.subTest(words=words):
                self.refused(word, words, self.word_list(items), "Lifestyle", "Word of the Day")

    def test_the_quotes_are_checked_and_carry_text_and_who(self):
        # u517 c2948 + public domain by its year, text of 72 characters and who of 24, each once + the package keeps
        # the text and who the board shows and the repo keeps the work and year that show it is free to use
        quotes = manifest(id="quotes", name="Quotes", uses="quotes", minFirmware="0.3.2",
                          description="A new quote every hour.")
        good = [["Confine thyself to the present.", "Marcus Aurelius", "Meditations", 180],
                ["A friend in need is a friend indeed.", "Proverb", "Traditional", 0]]
        out = self.tree(quotes, self.word_list(good), "Lifestyle", "Quotes").build()
        body = zipfile.ZipFile(os.path.join(out, "quotes-1.0.0.mooboard")).read("data/list.json")
        self.assertEqual(json.loads(body), {"format": 1, "items": [["Confine thyself to the present.",
                                                                    "Marcus Aurelius"],
                                                                   ["A friend in need is a friend indeed.",
                                                                    "Proverb"]]})
        for items, words in (([["Know thyself.", "Proverb", "Traditional"]], "is text, who, work, and year"),
                             ([["x" * 73, "Proverb", "Traditional", 0]], "text is 1 to 72 characters"),
                             ([["Know thyself.", "x" * 25, "Traditional", 0]], "who is 1 to 24 characters"),
                             ([["Know thyself.", "Proverb", "", 0]], "work is 1 to 64 characters"),
                             ([["Know thyself.", "Proverb", "Traditional", "0"]], "year is a whole number"),
                             ([["Know thyself.", "Proverb", "Traditional", True]], "year is a whole number"),
                             ([["Know thyself.", "Someone", "A Book", 1931]], "published after 1930"),
                             ([["Know thyself.", "Proverb", "Traditional", 0], ["Know thyself.", "Thales", "Sayings",
                                                                             -600]], "is in the list twice"),
                             ([["Know \u2014 thyself.", "Proverb", "Traditional", 0]], "has an em dash")):
            with self.subTest(words=words):
                self.refused(quotes, words, self.word_list(items), "Lifestyle", "Quotes")

    def test_facts_and_jokes_carry_their_list_too(self):
        # u523 e7 + their own checks of the words are the second lifestyle batch's
        for app_id, name, uses, folder in (("fun-facts", "Fun Facts", "facts", "Fun Facts"),
                                           ("joke-of-the-day", "Joke of the Day", "jokes", "Joke of the Day")):
            with self.subTest(uses=uses):
                man = manifest(id=app_id, name=name, uses=uses, minFirmware="0.3.2", description="One a day.")
                good = {"list.json": json.dumps({"format": 1, "items": [["a", "b"]]}).encode()}
                out = self.tree(man, good, "Lifestyle", folder).build()
                names = zipfile.ZipFile(os.path.join(out, "%s-1.0.0.mooboard" % app_id)).namelist()
                self.assertEqual(names, ["mooboard.json", "icon.png", "data/list.json"])
                self.refused(man, "its data/ is list.json alone", {}, "Lifestyle", folder)

    def test_the_second_waves_keys(self):
        cycles = manifest(id="light-cycles", name="Light Cycles", uses="cycles", category="Games",
                          minFirmware="0.3.2", description="Light trails race to box each other in.",
                          settings=[{"key": "riders", "type": "choice", "label": "Riders", "default": "Four",
                                     "options": ["Two", "Three", "Four"]}])
        self.tree(cycles, category="Games", folder="Light Cycles").build()
        wake = manifest(id="ok-to-wake", name="OK to Wake", uses="oktowake", category="Lifestyle",
                        minFirmware="0.3.2", description="A sleep light.",
                        settings=[{"key": "clock", "type": "toggle", "label": "Show clock", "default": False}])
        self.tree(wake, category="Lifestyle", folder="OK to Wake").build()
        wheel = manifest(id="spin-the-wheel", name="Spin the Wheel", uses="wheel", category="Tools",
                         minFirmware="0.3.2", description="Can't decide? Spin the wheel.",
                         controls=[{"key": "items", "type": "list", "label": "Choices", "max": 9, "chars": 14,
                                    "add": "Add choice"}])
        self.refused(wheel, "max must be 1 to 8", category="Tools", folder="Spin the Wheel")
        wheel["controls"][0]["max"] = 8
        self.tree(wheel, category="Tools", folder="Spin the Wheel").build()
        chores = manifest(id="chore-chart", name="Chore Chart", uses="chores", category="Lifestyle",
                          minFirmware="0.3.2", description="Whose turn it is.",
                          settings=[{"key": "people", "type": "text", "label": "People", "default": "Ana, Ben",
                                     "max": 32}])
        self.tree(chores, category="Lifestyle", folder="Chore Chart").build()
        # the spec's hyphenated keys are not the board's c2911
        self.refused(dict(wake, uses="ok-to-wake"), "uses must be one of", category="Lifestyle", folder="OK to Wake")


def openssl(*args, data=None):
    return subprocess.run(["openssl"] + list(args), input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


class Signature(unittest.TestCase):
    def setUp(self):
        self.tree = Tree(self)
        self.key = os.path.join(self.tree.root, "throwaway.pem")
        with open(self.key, "wb") as f:
            f.write(openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout"))
        self.public = os.path.join(self.tree.root, "throwaway.pub")
        with open(self.public, "wb") as f:
            f.write(openssl("ec", "-in", self.key, "-pubout"))

    def verifies(self, index, sig):
        der = os.path.join(self.tree.root, "sig.der")
        with open(der, "wb") as f:
            f.write(sig)
        result = subprocess.run(["openssl", "dgst", "-sha256", "-verify", self.public, "-signature", der],
                                input=index, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0

    def test_index_sig_is_base64_der_over_the_index_bytes(self):
        out = self.tree.build(key=self.key)
        index, text = read(os.path.join(out, "index.json")), read(os.path.join(out, "index.sig"))
        # strict base64 with no whitespace as pw_ota decodeBase64 takes it
        self.assertRegex(text.decode("ascii"), r"\A[A-Za-z0-9+/]+={0,2}\Z")
        sig = base64.b64decode(text, validate=True)
        self.assertEqual(sig[0], 0x30)
        self.assertTrue(self.verifies(index, sig))
        self.assertFalse(self.verifies(index[:-2] + bytes([index[-2] ^ 1]) + index[-1:], sig))

    def test_wrong_key_fails(self):
        out = self.tree.build(key=self.key)
        with open(self.public, "wb") as f:
            f.write(openssl("ec", "-pubout", data=openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout")))
        sig = base64.b64decode(read(os.path.join(out, "index.sig")))
        self.assertFalse(self.verifies(read(os.path.join(out, "index.json")), sig))

    def test_not_a_p256_key_is_refused(self):
        other = os.path.join(self.tree.root, "other.pem")
        with open(other, "wb") as f:
            f.write(openssl("ecparam", "-name", "secp384r1", "-genkey", "-noout"))
        with self.assertRaises(build.Refused):
            self.tree.build(key=other)


class TheRepo(unittest.TestCase):
    def test_this_repo_builds_and_fits_the_s3(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        build.build(REPO, out, generated=GENERATED)
        index = json.loads(read(os.path.join(out, "index.json")))
        # every app folder in the repo in categories.txt's order and a to z by folder + read from the folders so a branch
        # that adds an app adds nothing here
        want = []
        for category in build.CATEGORIES:
            top = os.path.join(REPO, category)
            for folder in sorted(f for f in os.listdir(top) if not f.startswith(".")) if os.path.isdir(top) else []:
                path = os.path.join(top, folder, "mooboard.json")
                if os.path.isfile(path):
                    man = json.loads(read(path))
                    want.append((man["id"], man["name"], category, man["uses"]))
        got = [(a["id"], a["name"], a["category"], a["uses"]) for a in index["apps"]]
        self.assertEqual(got, want)
        # the store's own first apps stay in it
        for row in (("prayer", "Prayer", "Lifestyle", "prayer"), ("fireplace", "Fireplace", "Ambiance", "fireplace"),
                    ("plasma", "Plasma", "Ambiance", "plasma"), ("starfield", "Starfield", "Ambiance", "starfield"),
                    ("life", "Game of Life", "Games", "life"), ("countdowns", "Countdowns", "Tools", "countdown"),
                    ("sketch", "Pixel Sketch", "Tools", "sketch")):
            self.assertIn(row, got)
        self.assertTrue(all(a["size"] <= build.BOARD_CAP["s3"] for a in index["apps"]))
        prayer = [a for a in index["apps"] if a["id"] == "prayer"][0]
        names = zipfile.ZipFile(os.path.join(out, prayer["file"])).namelist()
        self.assertTrue(all(n.endswith((".json", ".bin", ".png")) for n in names))
        # the prayer calendar face reads these two + without them it shows only the time and date
        self.assertIn("data/calendar.json", names)
        self.assertIn("data/glyphs/calendar.bin", names)


if __name__ == "__main__":
    unittest.main()


class Generated(unittest.TestCase):
    """boards refuse an index older than the one they hold and never lower that floor (board review n1) + so the
    builder refuses a stamp that is not later than the live catalog's or is more than a day ahead"""

    NOW = 1792396800   # 2026-10-19T08:00:00Z

    def test_a_stamp_more_than_a_day_ahead_is_refused(self):
        build.check_generated("2026-10-20T08:00:00Z", now=self.NOW)   # a day ahead is still fine
        with self.assertRaises(build.Refused):
            build.check_generated("2026-10-20T08:00:01Z", now=self.NOW)
        with self.assertRaises(build.Refused):
            build.check_generated("2062-10-19T08:00:00Z", now=self.NOW)

    def test_a_stamp_not_later_than_the_live_one_is_refused(self):
        build.check_generated("2026-10-19T08:00:00Z", previous="2026-10-19T07:59:59Z", now=self.NOW)
        for previous in ("2026-10-19T08:00:00Z", "2026-10-19T08:00:01Z"):
            with self.assertRaises(build.Refused):
                build.check_generated("2026-10-19T08:00:00Z", previous=previous, now=self.NOW)

    def test_build_takes_the_floor_and_writes_nothing_when_refused(self):
        tree = Tree(self)
        out = os.path.join(tree.root, "dist")
        with self.assertRaises(build.Refused):
            build.build(tree.root, out, generated=GENERATED, previous=GENERATED)
        self.assertFalse(os.path.exists(os.path.join(out, "index.json")))
        build.build(tree.root, out, generated=GENERATED, previous="2026-10-18T08:00:00Z")
        self.assertEqual(build.previous_generated(os.path.join(out, "index.json")), GENERATED)

    def test_the_command_reads_the_floor_from_the_last_build_or_the_live_index(self):
        tree = Tree(self)
        out = os.path.join(tree.root, "dist")
        build.build(tree.root, out, generated=GENERATED)
        stderr = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", stderr), unittest.mock.patch.object(build, "build") as called:
            called.side_effect = build.Refused("x")
            self.assertEqual(build.main(["--out", out, "--generated", GENERATED]), 1)
        self.assertEqual(called.call_args.kwargs["previous"], GENERATED)
        live = os.path.join(tree.root, "live.json")
        with open(live, "w") as f:
            json.dump({"format": 1, "generated": "2026-10-19T09:00:00Z"}, f)
        with unittest.mock.patch.object(build, "build") as called:
            build.main(["--out", out, "--previous", live])
        self.assertEqual(called.call_args.kwargs["previous"], "2026-10-19T09:00:00Z")
        with open(live, "w") as f:
            f.write("not json")
        with unittest.mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(build.main(["--out", out, "--previous", live]), 1)
