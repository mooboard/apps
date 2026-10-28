"""Two ordinary ABI 1 packages. Run this file to regenerate their assembly and icons."""
import json
from pathlib import Path

PALETTE = ["#000000", "#75e8f0", "#ff698b", "#ffda69", "#0d1d2d", "#e8f5ff", "#365cff", "#b179ed"]


class Assembly:
    def __init__(self): self.code = []
    def op(self, name, *args): self.code.append([name, *args]); return self
    def label(self, name): return self.op("label", name)
    def put(self, register, value):
        return self.op("load" if isinstance(value, tuple) and value[0] == "m" else
                       "mov" if isinstance(value, tuple) else "const", register,
                       value[1] if isinstance(value, tuple) else value)
    def set(self, slot, value): return self.put(20, value).op("store", 20, slot)
    def add(self, slot, value): return self.op("load", 20, slot).put(21, value).op("add", 20, 20, 21).op("store", 20, slot)
    def rect(self, *args):
        for reg, value in enumerate(args): self.put(reg, value)
        return self.op("rect", 0)
    def sprite(self, x, y, sprite):
        for reg, value in enumerate((x, y, sprite, 0)): self.put(reg, value)
        return self.op("sprite", 0)
    def digits(self, x, y, value, color=5):
        for reg, arg in enumerate((x, y, value, color)): self.put(reg, arg)
        return self.op("digits", 0)
    def branch(self, slot, comparison, value, label):
        return self.put(20, ("m", slot)).put(21, value).op(comparison, 22, 20, 21).op("jnz", 22, label)


def reset(a, memory):
    for i, value in enumerate(memory): a.set(i, value)


def pause_logic(a, memory, timer):
    a.branch(timer, "eq", 0, "play").add(timer, -1).branch(timer, "eq", 0, "restart").op("halt")
    a.label("restart").op("input", 20, 3).op("jnz", 20, "reset")
    a.op("input", 20, 1).put(21, 48).op("and", 20, 20, 21).op("jnz", 20, "reset").set(timer, 1).op("halt")
    a.label("reset"); reset(a, memory); a.op("halt").label("play")


def hud(a, score, lives):
    a.digits(3, 1, ("m", score))
    a.put(17, 0).label("hearts").put(18, ("m", lives)).op("lt", 19, 17, 18).op("jz", 19, "hearts_done")
    a.put(18, 5).op("mul", 18, 17, 18).put(19, 104).op("add", 18, 18, 19)
    a.rect(("r", 18), 2, 3, 3, 1).put(18, 1).op("add", 17, 17, 18).op("jump", "hearts")
    a.label("hearts_done")


def rally():
    memory = [1, 1160, 0, 0, 3, 0, 0, 1, 0, 0, 0, 0]
    init = Assembly(); reset(init, memory)
    s = Assembly(); pause_logic(s, memory, 8)
    s.add(10, 1).branch(6, "eq", 0, "flash_done").add(6, -1).label("flash_done")
    s.branch(5, "eq", 0, "steer").add(5, -1).op("jump", "traffic")
    s.label("steer").op("input", 0, 0).op("input", 1, 1).op("or", 0, 0, 1)
    s.put(1, 1).op("and", 2, 0, 1).op("jz", 2, "down").branch(0, "eq", 0, "traffic").add(0, -1).set(5, 9).op("jump", "traffic")
    s.label("down").put(1, 2).op("and", 2, 0, 1).op("jz", 2, "traffic").branch(0, "eq", 2, "traffic").add(0, 1).set(5, 9)
    s.label("traffic").op("setting", 0, 0).put(1, 2).op("mul", 0, 0, 1).put(1, 6).op("add", 0, 0, 1)
    s.op("load", 1, 1).op("sub", 1, 1, 0).op("store", 1, 1)
    s.op("input", 0, 0).put(1, 16).op("and", 0, 0, 1).op("jz", 0, "hitcheck").add(1, -4)
    s.label("hitcheck").branch(1, "lt", -80, "pass").branch(1, "lt", 100, "done").branch(1, "lt", 260, "lanecheck").op("jump", "done")
    s.label("lanecheck").op("load", 0, 0).op("load", 1, 2).op("eq", 0, 0, 1).op("jz", 0, "done")
    s.add(4, -1).set(6, 18).branch(4, "eq", 0, "gameover").op("jump", "spawn")
    s.label("pass").add(3, 10).label("spawn")
    s.put(0, 350).op("random", 0, 0).put(1, 1280).op("add", 0, 0, 1).op("store", 0, 1)
    s.put(0, 3).op("random", 0, 0).op("store", 0, 2).op("jump", "done")
    s.label("gameover").set(8, 100).label("done").op("halt")
    d = Assembly().put(0, 0).op("clear", 0).rect(1, 7, 126, 24, 4)
    d.put(17, 0).label("dashes").put(18, 10).op("lt", 19, 17, 18).op("jz", 19, "dashes_done")
    d.put(18, 14).op("mul", 18, 17, 18).put(19, ("m", 10)).put(16, 14).op("mod", 19, 19, 16).op("sub", 18, 18, 19)
    d.rect(("r", 18), 15, 5, 1, 6).rect(("r", 18), 23, 5, 1, 6)
    d.put(18, 1).op("add", 17, 17, 18).op("jump", "dashes").label("dashes_done")
    d.put(16, ("m", 1)).put(17, 10).op("div", 16, 16, 17)
    d.put(18, ("m", 2)).put(17, 8).op("mul", 18, 18, 17).op("add", 18, 18, 17).sprite(("r", 16), ("r", 18), 1)
    d.put(18, ("m", 0)).put(17, 8).op("mul", 18, 18, 17).op("add", 18, 18, 17).sprite(16, ("r", 18), 0)
    hud(d, 3, 4)
    d.branch(8, "eq", 0, "done").rect(54, 2, 20, 3, 2).label("done").op("halt")
    auto = Assembly().put(0, 0)
    auto.branch(1, "lt", 600, "near").op("halt").label("near")
    auto.put(1, ("m", 0)).put(2, ("m", 2)).op("eq", 1, 1, 2).op("jz", 1, "done")
    auto.branch(0, "eq", 0, "down").put(0, 1).op("halt").label("down").put(0, 2).label("done").op("halt")
    sprites = [["00111100","01155110","11111111","10111101","10111101","11111111","01155110","00111100"],
               ["00222200","02255220","22222222","20222202","20222202","22222222","02255220","00222200"]]
    return {"abi": 1, "palette": PALETTE, "sprites": sprites, "memory": memory,
            "init": init.code, "step": s.code, "draw": d.code, "auto": auto.code}


def target():
    memory = [640, 300, 1, 0, -1, 0, 3, 0, 1, 0, 0, 0]
    init = Assembly(); reset(init, memory)
    s = Assembly(); pause_logic(s, memory, 9)
    s.add(10, 1).op("input", 0, 0).op("input", 1, 1).op("or", 0, 0, 1)
    s.put(1, 4).op("and", 2, 0, 1).op("jz", 2, "right").add(0, -8)
    s.label("right").put(1, 8).op("and", 2, 0, 1).op("jz", 2, "bounds").add(0, 8)
    s.label("bounds").branch(0, "lt", 30, "leftedge").branch(0, "lt", 1240, "target").set(0, 1240).op("jump", "target")
    s.label("leftedge").set(0, 30)
    s.label("target").op("setting", 0, 0).put(1, 2).op("mul", 0, 0, 1).put(1, 5).op("add", 0, 0, 1)
    s.put(1, ("m", 2)).op("mul", 0, 0, 1).put(1, ("m", 1)).op("add", 0, 0, 1).op("store", 0, 1)
    s.branch(1, "lt", 80, "bounce_right").branch(1, "lt", 1170, "cooldown").set(2, -1).op("jump", "cooldown")
    s.label("bounce_right").set(2, 1)
    s.label("cooldown").branch(7, "eq", 0, "fire").add(7, -1).op("jump", "bullet")
    s.label("fire").branch(4, "eq", -1, "trigger").op("jump", "bullet")
    s.label("trigger").op("input", 0, 0).op("input", 1, 1).op("or", 0, 0, 1).put(1, 16).op("and", 0, 0, 1).op("jz", 0, "bullet")
    s.set(3, ("m", 0)).set(4, 250).set(7, 10).add(11, 1)
    s.label("bullet").branch(4, "eq", -1, "done").add(4, -16)
    s.branch(4, "lt", 70, "miss").branch(4, "lt", 135, "collision").op("jump", "done")
    s.label("collision").put(0, ("m", 3)).put(1, ("m", 1)).op("sub", 0, 0, 1)
    s.put(1, -65).op("lt", 2, 0, 1).op("jnz", 2, "done").put(1, 65).op("lt", 2, 0, 1).op("jz", 2, "done")
    s.add(5, 100).set(4, -1).put(0, 800).op("random", 0, 0).put(1, 200).op("add", 0, 0, 1).op("store", 0, 1).op("jump", "done")
    s.label("miss").set(4, -1).add(6, -1).branch(6, "eq", 0, "gameover").op("jump", "done")
    s.label("gameover").set(9, 100).label("done").op("halt")
    d = Assembly().put(0, 0).op("clear", 0).rect(1, 23, 126, 8, 4)
    d.put(16, ("m", 1)).put(17, 10).op("div", 16, 16, 17).put(17, 3).op("sub", 16, 16, 17).sprite(("r", 16), 7, 0)
    d.put(16, ("m", 0)).put(17, 10).op("div", 16, 16, 17).put(17, 3).op("sub", 16, 16, 17).sprite(("r", 16), 23, 1)
    d.branch(4, "eq", -1, "hud")
    d.put(16, ("m", 3)).put(17, 10).op("div", 16, 16, 17).put(18, ("m", 4)).op("div", 18, 18, 17).rect(("r", 16), ("r", 18), 1, 3, 3)
    d.label("hud"); hud(d, 5, 6)
    d.branch(9, "eq", 0, "done").rect(54, 2, 20, 3, 2).label("done").op("halt")
    auto = Assembly().put(0, 0).put(1, ("m", 2)).put(2, 90).op("mul", 1, 1, 2).put(2, ("m", 1)).op("add", 1, 1, 2)
    auto.put(2, ("m", 0)).op("sub", 1, 1, 2).put(2, -8).op("lt", 3, 1, 2).op("jz", 3, "right").put(0, 4).op("jump", "fire")
    auto.label("right").put(2, 8).op("lt", 3, 2, 1).op("jz", 3, "fire").put(0, 8)
    auto.label("fire").put(2, -40).op("lt", 3, 1, 2).op("jnz", 3, "done").put(2, 40).op("lt", 3, 1, 2).op("jz", 3, "done")
    auto.put(2, 16).op("or", 0, 0, 2).label("done").op("halt")
    sprites = [["00777700","07755770","77533577","77533577","07755770","00777700","00000000","00000000"],
               ["00011000","00111100","01111110","11155111","01111110","00000000","00000000","00000000"]]
    return {"abi": 1, "palette": PALETTE, "sprites": sprites, "memory": memory,
            "init": init.code, "step": s.code, "draw": d.code, "auto": auto.code}


def main():
    from PIL import Image, ImageDraw
    root = Path(__file__).resolve().parents[2]
    for name, key, description, source in (
        ("Pixel Rally", "pixel-rally", "Dodge traffic, change lanes, and hold A for turbo.", rally()),
        ("Target Practice", "target-practice", "Track a moving target and time your shots before three misses.", target()),
    ):
        path = root / "Games" / name; (path / "data").mkdir(parents=True, exist_ok=True)
        manifest = {"format": 2, "id": key, "name": name, "version": "1.0.0", "by": "mooboard", "description": description,
                    "category": "Games", "uses": "game", "minFirmware": "0.4.1", "settings": [
                    {"key": "speed", "type": "choice", "label": "Game speed", "default": "Normal", "options": ["Slow", "Normal", "Fast"]}]}
        (path / "mooboard.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (path / "data/game.json").write_text(json.dumps(source, indent=2) + "\n")
        (path / "README.md").write_text(f"# {name}\n\n{description}\n\nRuns on the universal game ABI 1 runtime: its rules, graphics, automatic player and controls are all in this package. No game-specific firmware renderer. Three lives; A/B restarts after game over. Automatic play restarts itself. Requires firmware 0.4.1 with the game runtime.\n")
        image = Image.new("RGB", (32, 32), "#08111c"); d = ImageDraw.Draw(image)
        if key == "pixel-rally":
            d.line((2, 9, 29, 9), fill="#365cff"); d.line((2, 23, 29, 23), fill="#365cff")
            d.rectangle((5, 12, 19, 20), fill="#75e8f0"); d.rectangle((10, 13, 14, 15), fill="#e8f5ff")
            d.rectangle((23, 4, 29, 10), fill="#ff698b")
        else:
            d.ellipse((8, 3, 25, 20), outline="#b179ed", width=3); d.ellipse((13, 8, 20, 15), fill="#ffda69")
            d.line((9, 25, 16, 15), fill="#75e8f0", width=2); d.polygon(((6, 24), (12, 29), (2, 29)), fill="#75e8f0")
        image.save(path / "icon.png")


if __name__ == "__main__": main()
