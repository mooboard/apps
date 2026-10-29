import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

BUILDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BUILDER)
sys.path.insert(0, BUILDER)
import build  # noqa: E402
import listing  # noqa: E402


def png(rows, filt=0):
    """an rgb png of these rows of (r, g, b)"""
    width = len(rows[0])
    raw, prior = b"", bytes(width * 3)
    for row in rows:
        line = bytes(v for px in row for v in px)
        out = bytearray()
        for i, x in enumerate(line):
            a, up, c = (line[i - 3] if i >= 3 else 0), prior[i], (prior[i - 3] if i >= 3 else 0)
            p = a + up - c
            paeth = a if abs(p - a) <= abs(p - up) and abs(p - a) <= abs(p - c) else up if abs(p - up) <= abs(p - c) else c
            out.append((x - (0, a, up, (a + up) // 2, paeth)[filt]) & 255)
        raw += bytes([filt]) + bytes(out)
        prior = line

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, len(rows), 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def tile(colour, w=32, h=32):
    return [[colour] * w for _ in range(h)]


def webp(width=1024, height=256, frames=40, ms=100, codec=b"VP8L", animated=True):
    """the chunks a clip's check reads + its frames' bitstreams are not real"""
    def chunk(kind, body):
        return kind + struct.pack("<I", len(body)) + body + (b"\x00" if len(body) & 1 else b"")
    vp8x = bytes([0x02 if animated else 0, 0, 0, 0]) + (width - 1).to_bytes(3, "little") + \
        (height - 1).to_bytes(3, "little")
    body = chunk(b"VP8X", vp8x) + chunk(b"ANIM", b"\x00" * 6)
    for _ in range(frames):
        head = b"\x00" * 6 + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little") + \
            ms.to_bytes(3, "little") + b"\x00"
        body += chunk(b"ANMF", head + chunk(codec, b"\x2f" + b"\x00" * 8))
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


HISTORY = [{"version": "1.1", "date": "2026-10-29", "notes": "Smoother sand."},
           {"version": "1.0", "date": "2026-10-21", "notes": "First release."}]
ICON = png(tile((10, 20, 30)))


class ListingTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.base = os.path.join(self.root, "Tools", "Timer")
        os.makedirs(os.path.join(self.base, "listing"))
        self.man = {"id": "timer", "version": "1.1.0"}
        self.write("icon-loop.png", png(tile((10, 20, 30)) + tile((40, 50, 60))))
        self.write("clip.webp", webp())
        self.write("shot-1.png", png(tile((1, 2, 3), 1024, 256)))
        self.write("shot-2.png", png(tile((4, 5, 6), 1024, 256)))
        self.write("history.json", json.dumps(HISTORY).encode())

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, name, body):
        with open(os.path.join(self.base, "listing", name), "wb") as f:
            f.write(body)

    def check(self, category="Tools"):
        return listing.check(self.base, self.man, ICON, category, "Tools/Timer")

    def refused(self, words, category="Tools"):
        with self.assertRaises(listing.Refused) as caught:
            self.check(category)
        self.assertIn(words, str(caught.exception))

    def test_a_whole_listing_is_its_row(self):
        self.assertEqual(self.check(), {"path": "Tools/Timer/listing/", "loop": 2, "shots": 2, "history": HISTORY})

    def test_no_listing_folder_is_none(self):
        shutil.rmtree(os.path.join(self.base, "listing"))
        self.assertIsNone(self.check())

    def test_the_loop_is_optional(self):
        os.remove(os.path.join(self.base, "listing", "icon-loop.png"))
        self.assertNotIn("loop", self.check())

    def test_the_loops_first_frame_is_the_icon(self):
        self.write("icon-loop.png", png(tile((99, 20, 30)) + tile((40, 50, 60))))
        self.refused("first frame is not icon.png")

    def test_filtered_rows_decode_as_the_icon(self):
        for filt in (1, 2, 3, 4):
            self.write("icon-loop.png", png(tile((10, 20, 30)) + tile((40, 50, 60)), filt))
            self.assertEqual(self.check()["loop"], 2)

    def test_the_loop_is_2_to_8_whole_frames(self):
        for rows in (tile((10, 20, 30)), tile((10, 20, 30)) * 9, tile((10, 20, 30), 32, 48)):
            self.write("icon-loop.png", png(rows))
            self.refused("2 to 8 frames")

    def test_no_loop_for_apps_with_no_home_tile(self):
        for category in ("Ambiance", "Clock"):
            self.refused("no Home tile", category)

    def test_the_clip_is_lossless_animated_1024_by_256_for_3_to_10_s(self):
        for body, words in ((webp(codec=b"VP8 "), "lossless"), (webp(animated=False), "not animated"),
                            (webp(width=512, height=128), "1024 x 256"), (webp(frames=101), "3 to 10 s"),
                            (webp(frames=29), "3 to 10 s"), (b"RIFF0000WEBP", "not a webp")):
            self.write("clip.webp", body)
            self.refused(words)

    def test_two_or_three_stills_in_order(self):
        os.remove(os.path.join(self.base, "listing", "shot-2.png"))
        self.refused("shot-1.png to")
        self.write("shot-3.png", png(tile((4, 5, 6), 1024, 256)))
        self.refused("shot-1.png to")

    def test_stills_are_1024_by_256(self):
        self.write("shot-2.png", png(tile((4, 5, 6), 512, 128)))
        self.refused("1024 x 256 png")

    def test_history_starts_at_the_apps_two_number_version(self):
        self.man["version"] = "1.2.0"
        self.refused("starts at 1.1 but the app is 1.2")
        self.man["version"] = "1.1.3"
        self.assertEqual(self.check()["history"], HISTORY)

    def test_history_rows(self):
        for rows, words in (([dict(HISTORY[0], version="1.1.0")], "two numbers"),
                            (list(reversed(HISTORY)), "newest first"),
                            ([dict(HISTORY[0], notes="x" * 501)], "notes of 1 to 500"),
                            ([dict(HISTORY[0], notes=" padded")], "notes of 1 to 500"),
                            ([dict(HISTORY[0], extra=1)], "version, date, and notes alone"),
                            ([dict(HISTORY[0], date="2026-13-01")], "YYYY-MM-DD"), ([], "1 to 50")):
            self.write("history.json", json.dumps(rows).encode())
            self.refused(words)

    def test_a_led_icon_is_two_12_by_12_frames(self):
        self.write("icon-led.png", png(tile((0, 0, 0), 12, 12) + tile((255, 184, 28), 12, 12)))
        self.assertTrue(self.check()["led"])
        for rows, words in ((tile((1, 2, 3), 12, 12), "12 wide and 24 tall"), (tile((1, 2, 3), 32, 64), "12 wide"),
                            (tile((9, 9, 9), 12, 24), "idle frame is the rest frame")):
            self.write("icon-led.png", png(rows))
            self.refused(words)

    def test_no_led_icon_for_apps_with_no_home_tile(self):
        os.remove(os.path.join(self.base, "listing", "icon-loop.png"))
        self.write("icon-led.png", png(tile((0, 0, 0), 12, 12) + tile((255, 184, 28), 12, 12)))
        self.refused("no Home tile", "Ambiance")

    def test_other_files_are_refused(self):
        self.write("notes.txt", b"hi")
        self.refused("notes.txt is not part of a listing")

    def test_clip_and_history_are_needed(self):
        os.remove(os.path.join(self.base, "listing", "history.json"))
        self.refused("history.json is missing")


class RepoListingsTest(unittest.TestCase):
    def test_the_committed_listings_json_is_the_listings_own(self):
        rows = build.listings_rows(REPO)
        path = os.path.join(REPO, listing.TOP)
        have = open(path, "rb").read() if os.path.exists(path) else None
        self.assertEqual(have, listing.top_bytes(rows) if rows else None)

    def test_a_stale_listings_json_is_refused(self):
        with self.assertRaises(build.Refused):
            build.check_listings_top(REPO, {"nope": {"path": "x/"}})

    def test_listing_files_never_go_in_a_package(self):
        for category, folder in build.find_apps(REPO):
            if not os.path.isdir(os.path.join(REPO, category, folder, listing.FOLDER)):
                continue
            package = build.load_app(REPO, category, folder)[2]
            names = zipfile.ZipFile(io.BytesIO(package)).namelist()
            self.assertFalse([n for n in names if n.startswith("listing")], (category, folder))


if __name__ == "__main__":
    unittest.main()
