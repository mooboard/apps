"""Each app's estimated draw (firmware C9264): power from its listing shots' LEDs, memory from its runtime and its
largest file, and storage, written to index2.json's rows + the build refuses an app past 90% of a
budget."""
import hashlib
import json
import os
import random
import shutil
import struct
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import budgets  # noqa: E402
import build  # noqa: E402
from test_build import Tree, manifest, pack_files, read  # noqa: E402


def shot(color):
    """a 1024 x 256 listing shot of one color"""
    rows = b"".join(b"\x00" + bytes(color) * 1024 for _ in range(256))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1024, 256, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def frame(color):
    return [[tuple(color) + (255,)] * 1024 for _ in range(256)]


class Estimate(unittest.TestCase):
    def test_black_draws_the_panels_idle_and_white_every_channel(self):
        self.assertEqual(budgets.frame_ma(frame((0, 0, 0))), budgets.IDLE_MA)
        self.assertEqual(budgets.frame_ma(frame((255, 255, 255))), budgets.IDLE_MA + 3 * budgets.FULL_FIELD_MA)
        # the driver's table lights half a value far less than half
        half = budgets.frame_ma(frame((128, 0, 0))) - budgets.IDLE_MA
        self.assertLess(half, budgets.FULL_FIELD_MA * 0.25)
        self.assertGreater(half, budgets.FULL_FIELD_MA * 0.15)

    def test_past_90_percent_of_a_budget_is_refused_and_below_is_not(self):
        caps = {"s3": 1000, "p4": 4000}
        self.assertIsNone(budgets.check({"ma": 2160, "ram": 471859}, 900, ["s3"], "x", "lua54", caps))
        said = budgets.check({"ma": 2161, "ram": 471860}, 901, ["s3"], "Tools/X", "lua54", caps)
        self.assertIn("Tools/X is past 90% of its budget", said)
        for words in ("power 2161 mA of 2400", "memory 471860 of 524288 bytes", "storage 901 of 1000 bytes on s3"):
            self.assertIn(words, said)
        self.assertIsNone(budgets.check({"ma": 0, "ram": 0}, 3600, ["p4"], "x", None, caps))
        # a firmware renderer's files are held to the entry cap, not the lua heap
        self.assertIsNone(budgets.check({"ma": 0, "ram": 600000}, 0, ["s3"], "x", "prayer", caps))


class Rows(unittest.TestCase):
    def test_the_shots_mean_is_the_apps_power(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        os.makedirs(os.path.join(folder, "listing"))
        for i, color in ((1, (255, 0, 0)), (2, (0, 0, 0))):
            with open(os.path.join(folder, "listing", "shot-%d.png" % i), "wb") as f:
                f.write(shot(color))
        self.assertEqual(budgets.shots_ma(folder, "x"), budgets.IDLE_MA + budgets.FULL_FIELD_MA // 2)
        self.assertIsNone(budgets.shots_ma(tempfile.gettempdir() + "/no-such-app", "x"))

    def test_index2s_rows_carry_the_draw_and_index_json_keeps_its_shape(self):
        out = Tree(self).build()
        row = json.loads(read(os.path.join(out, "index2.json")))["apps"][0]
        self.assertEqual(sorted(row["draw"]), ["ma", "ram"])
        self.assertEqual(row["draw"]["ma"], 0)   # no listing shots yet
        self.assertGreater(row["draw"]["ram"], budgets.RAM_BASE_RENDERER)
        self.assertNotIn("draw", json.loads(read(os.path.join(out, "index.json")))["apps"][0])

    def test_the_build_refuses_an_app_past_90_percent(self):
        rnd = random.Random(7)
        files = {path: body for path, body in pack_files().items() if path != "pack.json"}
        files.update({"glyphs/g%d.bin" % i: rnd.randbytes(480 * 1024) for i in range(4)})
        files["pack.json"] = json.dumps({"files": {path: hashlib.sha256(body).hexdigest()
                                                   for path, body in files.items()}}).encode()
        tree = Tree(self)
        tree.app("Lifestyle", "Prayer", manifest(), files)
        with self.assertRaises(build.Refused) as caught:
            tree.build()
        self.assertIn("Lifestyle/Prayer is past 90% of its budget (storage", str(caught.exception))
        self.assertIn("on s3", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
