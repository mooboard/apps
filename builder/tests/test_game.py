import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder"))
import game
import build


def source():
    return {"abi": 1, "palette": ["#000000", "#75e8f0"], "step": [["load", 0, 0], ["const", 1, 1],
        ["add", 0, 0, 1], ["store", 0, 0]], "draw": [["const", 0, 0], ["clear", 0]]}


class GameCompiler(unittest.TestCase):
    def test_same_source_same_portable_binary(self):
        src = source(); a = game.compile_game(src)
        b = game.compile_game(json.dumps(src).encode())
        self.assertEqual(a, b); self.assertEqual(a[:4], b"MBG1")
        self.assertEqual(game.validate_binary(a), a)

    def test_examples_use_exactly_the_same_renderer(self):
        for name in ("Pixel Rally", "Target Practice", "Jetpack Run"):
            row = build.load_app(str(ROOT), "Games", name)
            self.assertEqual(row[0]["uses"], "game")
            self.assertEqual(row[0]["minFirmware"], "0.4.1")
            self.assertIn(b"data/game.bin", row[2]); self.assertNotIn(b"data/game.json", row[2])

    def test_labels_resolve_to_instruction_numbers(self):
        src = source(); src["step"] = [["label", "again"], ["const", 0, 1], ["jnz", 0, "again"], ["halt"]]
        body = game.compile_game(src)
        self.assertEqual(struct.unpack_from("<i", body, 80 + 8 + 4)[0], 0)

    def test_invalid_source_does_not_compile(self):
        mutations = [lambda s:s.update(abi=2), lambda s:s.update(abi=True), lambda s:s.update(palette=["bad"]),
            lambda s:s.update(memory=[True]), lambda s:s.update(memory=[0] * 513),
            lambda s:s.update(step=[["syscall", 0]]), lambda s:s.update(step=[["load", 0, 512]]),
            lambda s:s.update(step=[["jz", 0, "missing"]]), lambda s:s.update(step=[["const", 32, 0]]),
            lambda s:s.update(draw=[["rect", 30]]), lambda s:s.update(sprites=[["0"] * 8]),
            lambda s:s.update(step=[["const", 0, 0]] * 2049), lambda s:s.update(extra=True)]
        for mutation in mutations:
            src = source(); mutation(src)
            with self.subTest(src=str(src)[:100]), self.assertRaises(ValueError): game.compile_game(src)

    def test_bad_binary_is_rejected(self):
        original = game.compile_game(source())
        for offset in (0, 4, 6, 10, 11, 22, 28, 80, 81):
            b = bytearray(original); b[offset] = 255
            with self.subTest(offset=offset), self.assertRaises(ValueError): game.validate_binary(b)
        for b in (original[:-1], original + b"\0"):
            with self.assertRaises(ValueError): game.validate_binary(b)

    def test_package_requires_only_program_data_and_checks_firmware(self):
        with self.assertRaises(build.Refused): build.check_game({}, "test")
        with self.assertRaises(build.Refused): build.check_game({"game.json":b"{}", "extra.bin":b""}, "test")
        with self.assertRaises(build.Refused): build.check_game({"game.bin":b"bad"}, "test")
        data = {"game.json":json.dumps(source()).encode()}
        build.check_game(data, "test")
        self.assertEqual(set(build.package_data("game", data)), {"game.bin"})
        self.assertEqual(build.USES_FIRMWARE["game"], (0, 4, 1))


if __name__ == "__main__": unittest.main()
