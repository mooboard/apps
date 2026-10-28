"""Compile portable mooboard game ABI 1 assembly. No game-specific code lives here."""
import json
import re
import struct

OPS = ("halt const mov add sub mul div mod and or xor shl shr eq lt jump jz jnz load store loadi storei input random "
       "setting clear pixel rect line sprite digits overlap").split()
REGISTERS, WORDS, INSTRUCTIONS, SPRITES, ABI = 32, 512, 2048, 16, 1
MAX_BYTES = 32 + 48 + INSTRUCTIONS * 8 + SPRITES * 64 + WORDS * 4
ARGS = {"clear": 1, "pixel": 3, "rect": 5, "line": 5, "sprite": 4, "digits": 4, "overlap": 8}


def integer(n, low, high, what):
    if type(n) is not int or not low <= n <= high:
        raise ValueError(f"{what} must be an integer from {low} to {high}")
    return n


def validate_binary(data):
    if len(data) < 80 or len(data) > MAX_BYTES or data[:4] != b"MBG1":
        raise ValueError("game size or magic")
    abi, header, count, sprites, reserved, init, step, draw, auto, words = struct.unpack_from("<HHHBBHHHHH", data, 4)
    if abi != ABI or header != 32:
        raise ValueError("game ABI")
    if not 1 <= count <= INSTRUCTIONS or sprites > SPRITES or words > WORDS:
        raise ValueError("game limits")
    if reserved or any(data[22:32]):
        raise ValueError("game reserved field")
    if len(data) != 80 + count * 8 + sprites * 64 + words * 4:
        raise ValueError("game length")
    if step >= count or draw >= count or any(pc != 65535 and pc >= count for pc in (init, auto)):
        raise ValueError("game entry")
    for n in range(count):
        op, a, b, c, imm = struct.unpack_from("<BBBBi", data, 80 + n * 8)
        if op >= len(OPS) or max(a, b, c) >= REGISTERS:
            raise ValueError("game opcode or register")
        name = OPS[op]
        if name in ("jump", "jz", "jnz") and not 0 <= imm < count:
            raise ValueError("game branch")
        if name in ("load", "store") and not 0 <= imm < WORDS:
            raise ValueError("game memory")
        if name == "input" and not 0 <= imm <= 3:
            raise ValueError("game input")
        if name == "setting" and not 0 <= imm < 8:
            raise ValueError("game setting")
        if a + ARGS.get(name, 0) > REGISTERS:
            raise ValueError("game drawing arguments")
    if any(value > 15 for value in data[80 + count * 8:80 + count * 8 + sprites * 64]):
        raise ValueError("game sprite palette")
    return data


def compile_game(source):
    if isinstance(source, bytes):
        source = json.loads(source.decode("utf-8"))
    if not isinstance(source, dict) or set(source) - {"abi", "palette", "sprites", "memory", "init", "step", "draw", "auto"}:
        raise ValueError("game source keys")
    if type(source.get("abi")) is not int or source["abi"] != ABI:
        raise ValueError("game ABI")
    palette = source.get("palette", [])
    if not isinstance(palette, list) or not 1 <= len(palette) <= 16 or palette[0] != "#000000":
        raise ValueError("palette needs black first and at most sixteen colors")
    if any(not isinstance(c, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in palette):
        raise ValueError("game palette colors")
    colors = b"".join(bytes.fromhex(c[1:]) for c in palette).ljust(48, b"\0")
    sprites = source.get("sprites", [])
    if not isinstance(sprites, list) or len(sprites) > SPRITES:
        raise ValueError("at most sixteen sprites")
    pixels = bytearray()
    for sprite in sprites:
        if not isinstance(sprite, list) or len(sprite) != 8 or any(not isinstance(row, str) or not re.fullmatch(r"[0-9a-fA-F]{8}", row) for row in sprite):
            raise ValueError("a sprite is eight rows of eight palette indices")
        pixels.extend(int(c, 16) for row in sprite for c in row)
    memory = source.get("memory", [])
    if not isinstance(memory, list) or len(memory) > WORDS:
        raise ValueError("at most 512 memory words")
    memory_bytes = b"".join(struct.pack("<i", integer(v, -2147483648, 2147483647, "memory")) for v in memory)
    code, labels, entries = [], {}, {}
    for section in ("init", "step", "draw", "auto"):
        lines = source.get(section)
        if lines is None:
            if section in ("step", "draw"):
                raise ValueError(f"game needs {section}")
            entries[section] = 65535
            continue
        if not isinstance(lines, list) or not lines:
            raise ValueError(f"{section} must hold instructions")
        entries[section] = len(code)
        for line in lines:
            if not isinstance(line, list) or not line or not isinstance(line[0], str):
                raise ValueError("game instruction")
            name, *args = line
            if name == "label":
                if len(args) != 1 or not isinstance(args[0], str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", args[0]):
                    raise ValueError("game label")
                label = section + ":" + args[0]
                if label in labels:
                    raise ValueError("duplicate game label")
                labels[label] = len(code)
                continue
            if name not in OPS:
                raise ValueError(f"unknown game instruction {name}")
            a = b = c = imm = 0
            if name in ("halt",):
                if args: raise ValueError("halt has no operands")
            elif name == "jump":
                if len(args) != 1: raise ValueError("jump needs a label")
                imm = args[0]
            elif name in ("const", "load", "store", "input", "setting", "jz", "jnz"):
                if len(args) != 2: raise ValueError(f"{name} needs two operands")
                a, imm = args
            elif name in ARGS:
                if len(args) != 1: raise ValueError(f"{name} needs an argument register")
                a = args[0]
            elif name in ("mov", "loadi", "storei", "random"):
                if len(args) != 2: raise ValueError(f"{name} needs two registers")
                a, b = args
            else:
                if len(args) != 3: raise ValueError(f"{name} needs three registers")
                a, b, c = args
            for reg in (a, b, c): integer(reg, 0, 31, "register")
            code.append((OPS.index(name), a, b, c, imm, section))
        if not code or code[-1][0] != OPS.index("halt"):
            code.append((0, 0, 0, 0, 0, section))
    if len(code) > INSTRUCTIONS:
        raise ValueError("too many game instructions")
    encoded = bytearray()
    for op, a, b, c, imm, section in code:
        if isinstance(imm, str):
            label = imm if ":" in imm else section + ":" + imm
            if label not in labels: raise ValueError(f"missing label {label}")
            imm = labels[label]
        encoded.extend(struct.pack("<BBBBi", op, a, b, c, integer(imm, -2147483648, 2147483647, "immediate")))
    header = b"MBG1" + struct.pack("<HHHBBHHHHH", ABI, 32, len(code), len(sprites), 0,
        entries["init"], entries["step"], entries["draw"], entries["auto"], len(memory)) + bytes(10)
    return validate_binary(header + colors + encoded + pixels + memory_bytes)
