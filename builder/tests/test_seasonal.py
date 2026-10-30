import hashlib
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile

BUILDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BUILDER)
sys.path.insert(0, BUILDER)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402
import seasonal  # noqa: E402
from kit import gif, png  # noqa: E402
from test_build import GENERATED, Tree, read  # noqa: E402

W, H = 128, 32


def frame(color=(200, 120, 20), box=(40, 8, 48, 16)):
    """a black frame with one lit box well inside the panel"""
    rgb = bytearray(W * H * 3)
    x0, y0, bw, bh = box
    for y in range(y0, y0 + bh):
        for x in range(x0, x0 + bw):
            rgb[(y * W + x) * 3:(y * W + x) * 3 + 3] = bytes(color)
    return bytes(rgb)


def face(**changes):
    out = {"id": "diwali", "name": "Diwali", "start": "10-25", "end": "11-10",
           "clock": {"x": 64, "y": 4, "align": "center", "font": "clock", "size": 14, "color": "#ffd27a"}}
    out.update(changes)
    return {key: value for key, value in out.items() if value is not None}


def gif_of(frames):
    return gif.encode(frames)


def unpack_background(body):
    """the background.bin layout read back as frames of rgb and their delays"""
    magic, version, _, w, h, count, colors = struct.unpack("<4sBBHHHH", body[:14])
    assert (magic, version, w, h) == (b"PWSB", 1, W, H)
    at = 14
    palette = body[at:at + colors * 3]
    at += colors * 3
    delays = list(struct.unpack("<%dH" % count, body[at:at + 2 * count]))
    at += 2 * count
    frames = []
    for i in range(count):
        indices = body[at + i * W * H:at + (i + 1) * W * H]
        frames.append(b"".join(palette[k * 3:k * 3 + 3] for k in indices))
    assert at + count * W * H == len(body)
    return frames, delays, colors


class SeasonalTree(Tree):
    """a store repo with prayer and one seasonal event"""

    def __init__(self, test, folder="Diwali", man=None, background=None, kind="gif"):
        super().__init__(test)
        self.event(folder, face() if man is None else man,
                   gif_of([(frame(), 500), (frame((255, 60, 0)), 500)]) if background is None else background, kind)

    def event(self, folder, man, background, kind="gif"):
        base = "Seasonal/%s/" % folder
        self.write(base + "face.json", json.dumps(man, indent=2) if isinstance(man, dict) else man)
        if background is not None:
            self.write(base + "background." + kind, background)


def built(tree):
    out = tree.build()
    index = json.loads(read(os.path.join(out, "index.json")))
    return out, index


class Publishing(unittest.TestCase):
    def test_the_index_lists_each_event(self):
        out, index = built(SeasonalTree(self))
        self.assertEqual(list(index), ["format", "generated", "categories", "apps", "seasonal"])
        self.assertEqual([a["id"] for a in index["apps"]], ["prayer"])
        row = index["seasonal"][0]
        self.assertEqual(list(row), ["id", "name", "start", "end", "file", "sha256", "size"])
        self.assertEqual((row["id"], row["name"], row["start"], row["end"], row["file"]),
                         ("diwali", "Diwali", "10-25", "11-10", "diwali-1.0.0.mooboard"))
        body = read(os.path.join(out, row["file"]))
        self.assertEqual(row["size"], len(body))
        self.assertEqual(row["sha256"], hashlib.sha256(body).hexdigest())
        # the store sheet never lists an event among the apps
        self.assertNotIn("Seasonal", index["categories"])

    def test_the_package_is_format_2_with_uses_seasonal(self):
        out, _ = built(SeasonalTree(self))
        z = zipfile.ZipFile(io.BytesIO(read(os.path.join(out, "diwali-1.0.0.mooboard"))))
        self.assertIsNone(z.testzip())
        self.assertEqual([i.filename for i in z.infolist()],
                         ["mooboard.json", "icon.png", "data/background.bin", "data/face.json"])
        for info in z.infolist():
            self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
        man = json.loads(z.read("mooboard.json"))
        self.assertEqual(man, {"format": 2, "id": "diwali", "name": "Diwali", "version": "1.0.0", "by": "mooboard",
                               "description": "A seasonal clock face.", "category": "Seasonal",
                               "uses": "seasonal", "minFirmware": "0.3.0", "boards": ["s3", "p4"]})
        self.assertEqual(z.read("mooboard.json"), build.manifest_bytes(man))
        build.check_icon(z.read("icon.png"), "icon.png")

    def test_face_json_is_laid_out_one_way(self):
        out, _ = built(SeasonalTree(self))
        z = zipfile.ZipFile(os.path.join(out, "diwali-1.0.0.mooboard"))
        body = z.read("data/face.json")
        want = {"format": 1, "id": "diwali", "name": "Diwali", "start": "10-25", "end": "11-10",
                "clock": {"x": 64, "y": 4, "align": "center", "font": "clock", "size": 14, "color": "#ffd27a"}}
        self.assertEqual(body, (json.dumps(want, separators=(",", ":")) + "\n").encode())

    def test_the_clock_takes_defaults(self):
        out, _ = built(SeasonalTree(self, man=face(clock={})))
        z = zipfile.ZipFile(os.path.join(out, "diwali-1.0.0.mooboard"))
        self.assertEqual(json.loads(z.read("data/face.json"))["clock"],
                         {"x": 64, "y": 9, "align": "center", "font": "clock", "size": 14, "color": "#ffffff"})

    def test_a_gif_background_keeps_its_frames_and_delays(self):
        frames = [(frame(), 500), (frame((255, 60, 0)), 250), (frame((0, 90, 255), (10, 10, 20, 10)), 1000)]
        out, _ = built(SeasonalTree(self, background=gif_of(frames)))
        z = zipfile.ZipFile(os.path.join(out, "diwali-1.0.0.mooboard"))
        got, delays, colors = unpack_background(z.read("data/background.bin"))
        self.assertEqual(got, [rgb for rgb, _ in frames])
        self.assertEqual(delays, [500, 250, 1000])
        self.assertEqual(colors, 4)

    def test_a_png_background_is_one_still_frame(self):
        still = png.encode(W, H, frame())
        out, _ = built(SeasonalTree(self, background=still, kind="png"))
        z = zipfile.ZipFile(os.path.join(out, "diwali-1.0.0.mooboard"))
        got, delays, _ = unpack_background(z.read("data/background.bin"))
        self.assertEqual((got, delays), ([frame()], [0]))

    def test_more_than_256_colors_share_one_palette(self):
        rgb = bytearray(W * H * 3)
        for i in range(600):
            x, y = 2 + i % 120, 2 + i // 120
            rgb[(y * W + x) * 3:(y * W + x) * 3 + 3] = bytes((40 + i % 200, (i * 7) % 256, 255 - i % 200))
        out, _ = built(SeasonalTree(self, background=png.encode(W, H, bytes(rgb)), kind="png"))
        z = zipfile.ZipFile(os.path.join(out, "diwali-1.0.0.mooboard"))
        _, _, colors = unpack_background(z.read("data/background.bin"))
        self.assertLessEqual(colors, 256)

    def test_a_specific_year_and_a_version(self):
        man = face(start="2026-10-25", end="2026-11-10", version="1.2.0")
        _, index = built(SeasonalTree(self, man=man))
        self.assertEqual((index["seasonal"][0]["start"], index["seasonal"][0]["end"], index["seasonal"][0]["file"]),
                         ("2026-10-25", "2026-11-10", "diwali-1.2.0.mooboard"))

    def test_events_sorted_by_folder_and_a_year_end_wrap(self):
        tree = SeasonalTree(self)
        tree.event("New Year", face(id="new-year", name="New Year", start="12-31", end="01-01"),
                   gif_of([(frame(), 100)]))
        _, index = built(tree)
        self.assertEqual([r["id"] for r in index["seasonal"]], ["diwali", "new-year"])

    def test_same_tree_same_bytes(self):
        tree = SeasonalTree(self)
        first = tree.build()
        a = {n: read(os.path.join(first, n)) for n in os.listdir(first)}
        shutil.rmtree(first)
        second = tree.build()
        self.assertEqual(a, {n: read(os.path.join(second, n)) for n in os.listdir(second)})

    def test_no_events_no_seasonal_key(self):
        tree = Tree(self)
        os.makedirs(os.path.join(tree.root, "Seasonal"))
        _, index = built(tree)
        self.assertEqual(list(index), ["format", "generated", "categories", "apps"])


class Rules(unittest.TestCase):
    def refused(self, words, **options):
        tree = SeasonalTree(self, **options)
        return self.refused_tree(tree, words)

    def refused_tree(self, tree, words):
        out = os.path.join(tree.root, "dist")
        with self.assertRaises(build.Refused) as caught:
            build.build(tree.root, out, generated=GENERATED)
        self.assertIn(words, str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(out, "index.json")))

    def test_name_is_the_folder(self):
        self.refused("name must be the folder's name", man=face(name="diwali"))

    def test_id(self):
        self.refused("id must be", man=face(id="Diwali"))

    def test_unknown_key(self):
        self.refused("unknown key colour", man=face(colour="red"))

    def test_repeated_key(self):
        self.refused("not valid JSON", man=json.dumps(face())[:-1] + ',"id":"x"}')

    def test_needs_dates(self):
        self.refused("needs start", man=face(start=None))

    def test_dates(self):
        self.refused("start must be MM-DD or YYYY-MM-DD", man=face(start="13-01"))
        self.refused("end must be MM-DD or YYYY-MM-DD", man=face(end="02-30"))
        self.refused("start must be MM-DD or YYYY-MM-DD", man=face(start="2026-1-05"))
        # a yearly feb 29 would skip three years in four
        self.refused("start must be MM-DD or YYYY-MM-DD", man=face(start="02-29"))

    def test_both_dates_one_form(self):
        self.refused("start and end must both be MM-DD or both YYYY-MM-DD", man=face(end="2026-11-10"))

    def test_a_year_ends_after_it_starts(self):
        self.refused("end must not be before start", man=face(start="2026-11-10", end="2026-10-25"))

    def test_clock(self):
        self.refused("clock x must be 0 to 127", man=face(clock={"x": 128}))
        self.refused("clock y must be 0 to 31", man=face(clock={"y": -1}))
        self.refused("clock align must be", man=face(clock={"align": "middle"}))
        self.refused("clock font must be", man=face(clock={"font": "comic"}))
        self.refused("clock size must be 6 to 28", man=face(clock={"size": 30}))
        self.refused("clock color must be", man=face(clock={"color": "red"}))
        self.refused("clock color is too dim", man=face(clock={"color": "#030303"}))
        self.refused("unknown clock key shadow", man=face(clock={"shadow": True}))
        self.refused("clock must be an object", man=face(clock=[1]))

    def test_one_background(self):
        tree = SeasonalTree(self)
        tree.write("Seasonal/Diwali/background.png", png.encode(W, H, frame()))
        self.refused_tree(tree, "Seasonal/Diwali needs one background")
        tree = SeasonalTree(self)
        os.remove(os.path.join(tree.root, "Seasonal/Diwali/background.gif"))
        self.refused_tree(tree, "Seasonal/Diwali needs one background")

    def test_stray_file(self):
        tree = SeasonalTree(self)
        tree.write("Seasonal/Diwali/song.mp3", b"ID3")
        self.refused_tree(tree, "song.mp3 is not part of a seasonal face")

    def test_needs_face_json(self):
        tree = SeasonalTree(self)
        os.remove(os.path.join(tree.root, "Seasonal/Diwali/face.json"))
        self.refused_tree(tree, "Seasonal/Diwali/face.json is missing")

    def test_background_size(self):
        self.refused("background must be 128x32", background=png.encode(64, 32, bytes(64 * 32 * 3)), kind="png")
        self.refused("can't be read", background=b"GIF89a nonsense")

    def test_frames(self):
        many = [(frame((10 + i, 100, 100)), 40) for i in range(seasonal.MAX_FRAMES + 1)]
        self.refused("more than 100 frames", background=gif_of(many))
        fast = bytearray(gif_of([(frame(), 100), (frame((0, 0, 255)), 100)]))
        at = fast.find(b"\x21\xf9\x04")
        while at >= 0:
            fast[at + 4:at + 6] = struct.pack("<H", 2)   # 20 ms which the kit's writer never makes
            at = fast.find(b"\x21\xf9\x04", at + 1)
        self.refused("frames shorter than 30 ms", background=bytes(fast))

    def test_a_background_may_light_every_edge(self):
        # every led of the panel the background's to light, its corners and edges too
        frames = [(frame(box=(0, 0, W, H)), 100), (frame((0, 90, 255), (0, 0, 10, 10)), 100)]
        out, _ = built(SeasonalTree(self, background=gif_of(frames)))
        z = zipfile.ZipFile(os.path.join(out, "diwali-1.0.0.mooboard"))
        got, _, _ = unpack_background(z.read("data/background.bin"))
        self.assertEqual(got, [rgb for rgb, _ in frames])

    def test_gif_cap(self):
        body = gif_of([(frame(), 100), (frame((0, 0, 255)), 100)])
        cap = seasonal.GIF_CAP
        seasonal.GIF_CAP = len(body) - 1
        self.addCleanup(setattr, seasonal, "GIF_CAP", cap)
        self.refused("background.gif is over", background=body)

    def test_events_must_not_overlap(self):
        tree = SeasonalTree(self)
        tree.event("Lights", face(id="lights", name="Lights", start="2027-11-01", end="2027-11-02"),
                   gif_of([(frame(), 100)]))
        self.refused_tree(tree, "Diwali and Lights overlap")

    def test_an_event_and_an_app_share_no_id(self):
        self.refused("two apps have the id prayer", man=face(id="prayer"))

    def test_a_folder_that_is_no_event(self):
        tree = SeasonalTree(self)
        tree.write("Seasonal/notes.txt", "x")
        built(tree)   # a loose file beside the events is passed over as a readme would be


class TheRepo(unittest.TestCase):
    def test_diwali_2026_builds(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        build.build(REPO, out, generated=GENERATED)
        index = json.loads(read(os.path.join(out, "index.json")))
        rows = {r["id"]: r for r in index["seasonal"]}
        # lakshmi puja falls on 2026-11-08 + dhanteras the 6th + bhai dooj the 10th
        self.assertEqual((rows["diwali"]["name"], rows["diwali"]["start"], rows["diwali"]["end"]),
                         ("Diwali", "2026-10-25", "2026-11-10"))
        self.assertLessEqual(rows["diwali"]["size"], build.BOARD_CAP["s3"])


if __name__ == "__main__":
    unittest.main()
