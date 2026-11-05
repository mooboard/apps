import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder"))
import game
import build
from test_build import png


def manifest(**changes):
    return dict({"format": 2, "id": "test-game", "name": "Test Game", "version": "1.0.0", "by": "mooboard",
                 "description": "A test program.", "category": "Games", "uses": "game",
                 "minFirmware": "0.4.0-alpha.3"}, **changes)


def source():
    return {"abi": 1, "palette": ["#000000", "#75e8f0"], "step": [["load", 0, 0], ["const", 1, 1],
        ["add", 0, 0, 1], ["store", 0, 0]], "draw": [["const", 0, 0], ["clear", 0]]}


class GameCompiler(unittest.TestCase):
    def test_same_source_same_portable_binary(self):
        src = source(); a = game.compile_game(src)
        b = game.compile_game(json.dumps(src).encode())
        self.assertEqual(a, b); self.assertEqual(a[:4], b"MBG1")
        self.assertEqual(game.validate_binary(a), a)

    def test_a_game_package_carries_the_compiled_program_alone(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / "Games" / "Test Game"
            (base / "data").mkdir(parents=True)
            (base / "mooboard.json").write_text(json.dumps(manifest()))
            (base / "icon.png").write_bytes(png())
            (base / "data" / "game.json").write_text(json.dumps(source()))
            row = build.load_app(root, "Games", "Test Game")
            self.assertEqual(row[0]["uses"], "game")
            self.assertEqual(row[0]["minFirmware"], "0.4.0-alpha.3")
            self.assertIn(b"data/game.bin", row[2]); self.assertNotIn(b"data/game.json", row[2])
            (base / "mooboard.json").write_text(json.dumps(manifest(minFirmware="0.4.0")))
            with self.assertRaises(build.Refused): build.load_app(root, "Games", "Test Game")

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
        self.assertEqual(build.USES_FIRMWARE["game"], "0.4.0-alpha.3")


class GameCue(unittest.TestCase):
    """the lights api u757 c5365: cue is opcode 32 + imm's low 4 bits the look and its next 5 a palette color plus 1,
    0 the look's own + never from draw + a game that cues needs 0.4.2-alpha.1"""

    def imms(self, body):
        count = struct.unpack_from("<H", body, 8)[0]
        return [struct.unpack_from("<BBBBi", body, 80 + n * 8) for n in range(count)]

    def test_cue_encodes_its_look_and_palette_color(self):
        src = source(); src["step"] = [["cue", "hit"], ["cue", "levelClear", 1], ["cue", "gameOver"]]
        body = game.compile_game(src)
        self.assertEqual(game.OPS.index("cue"), 32)
        self.assertEqual(self.imms(body)[:3], [(32, 0, 0, 0, 1), (32, 0, 0, 0, 4 | 2 << 4), (32, 0, 0, 0, 6)])
        self.assertEqual(game.cues(body), 3)
        self.assertEqual(game.cues(game.compile_game(source())), 0)
        self.assertEqual([game.LOOKS.index(look) + 1 for look in ("hit", "powerUp", "explosion", "levelClear",
                                                                  "death", "gameOver")], [1, 2, 3, 4, 5, 6])

    def test_bad_cues_do_not_compile(self):
        for step in ([["cue"]], [["cue", "flash"]], [["cue", 1]], [["cue", "death", 0]], [["cue", "death", 2]],
                     [["cue", "death", True]], [["cue", "death", 1, 1]], [["cue", "Death"]]):
            src = source(); src["step"] = step
            with self.subTest(step=step), self.assertRaises(ValueError): game.compile_game(src)
        src = source(); src["draw"] = [["cue", "hit"]]   # the board faults a cue from draw
        with self.assertRaises(ValueError) as caught: game.compile_game(src)
        self.assertIn("draw", str(caught.exception))
        src = source(); src["init"] = [["cue", "hit"]]; src["auto"] = [["cue", "hit"]]
        game.compile_game(src)

    def test_a_bad_cue_binary_is_rejected(self):
        src = source(); src["step"] = [["cue", "hit"]]
        original = game.compile_game(src)
        for imm in (0, 7, 15, -1, 17 << 4 | 1, 1 << 20):
            b = bytearray(original); struct.pack_into("<i", b, 84, imm)
            with self.subTest(imm=imm), self.assertRaises(ValueError): game.validate_binary(b)
        for imm in (1, 6, 16 << 4 | 6):
            b = bytearray(original); struct.pack_into("<i", b, 84, imm)
            game.validate_binary(bytes(b))
        b = bytearray(original); b[80] = 33
        with self.assertRaises(ValueError): game.validate_binary(b)

    def test_a_game_that_cues_needs_0_4_2_alpha(self):
        src = source(); src["step"] = [["cue", "death"]]
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / "Games" / "Test Game"
            (base / "data").mkdir(parents=True)
            (base / "icon.png").write_bytes(png())
            (base / "data" / "game.json").write_text(json.dumps(src))
            for floor in ("0.4.0-alpha.3", "0.4.1", "0.4.1-alpha"):
                (base / "mooboard.json").write_text(json.dumps(manifest(minFirmware=floor)))
                with self.subTest(floor=floor), self.assertRaises(build.Refused) as caught:
                    build.load_app(root, "Games", "Test Game")
                self.assertIn("a game that cues needs minFirmware 0.4.2-alpha.1", str(caught.exception))
            (base / "mooboard.json").write_text(json.dumps(manifest(minFirmware="0.4.2-alpha.1")))
            self.assertEqual(build.load_app(root, "Games", "Test Game")[0]["minFirmware"], "0.4.2-alpha.1")
            for floor in ("0.4.2-alpha.3", "0.4.2-alpha", "0.4.2"):   # pw_ota's order
                (base / "mooboard.json").write_text(json.dumps(manifest(minFirmware=floor)))
                self.assertEqual(build.load_app(root, "Games", "Test Game")[0]["minFirmware"], floor)
            (base / "mooboard.json").write_text(json.dumps(manifest(lights={"crash": {"look": "hit"}},
                                                                    minFirmware="0.4.2-alpha.1")))
            with self.assertRaises(build.Refused): build.load_app(root, "Games", "Test Game")   # cue ops, not lights


if __name__ == "__main__": unittest.main()
