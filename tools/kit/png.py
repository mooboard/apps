import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
MAX_PIXELS = 1 << 24
ONCE = (b"IHDR", b"PLTE", b"tRNS")


class Unreadable(Exception):
    pass


def size(data):
    data = bytes(data[:33])
    if data[:8] != SIGNATURE or data[12:16] != b"IHDR" or len(data) < 24:
        raise Unreadable()
    return struct.unpack(">II", data[16:24])


def _chunks(data):
    if data[:8] != SIGNATURE:
        raise Unreadable()
    pos, info, palette, trns, idat, seen, ended = 8, None, None, None, [], set(), False
    while pos + 12 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        start, end = pos + 8, pos + 8 + length
        if end + 4 > len(data) or data[end:end + 4] != struct.pack(">I", zlib.crc32(data[pos + 4:end]) & 0xFFFFFFFF):
            raise Unreadable()
        if (pos == 8) != (kind == b"IHDR") or kind in seen:
            raise Unreadable()
        if kind in ONCE:
            seen.add(kind)
        body = data[start:end]
        if kind == b"IHDR":
            if length != 13:
                raise Unreadable()
            info = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            if length:
                raise Unreadable()
            ended = True
            break
        pos = end + 4
    if info is None or not idat or not ended:
        raise Unreadable()
    return info, palette, trns, b"".join(idat)


def _passes(width, height, interlace):
    if not interlace:
        return [(0, 0, 1, 1, width, height)]
    out = []
    for x0, y0, dx, dy in ADAM7:
        pw, ph = -(-(width - x0) // dx), -(-(height - y0) // dy)
        if pw > 0 and ph > 0:
            out.append((x0, y0, dx, dy, pw, ph))
    return out


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _unfilter(raw, at, row_bytes, rows, bpp):
    prev = None
    out = []
    for _ in range(rows):
        if at + 1 + row_bytes > len(raw):
            raise Unreadable()
        kind = raw[at]
        line = bytearray(raw[at + 1:at + 1 + row_bytes])
        if kind == 1:
            for i in range(bpp, row_bytes):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif kind == 2 and prev is not None:
            for i in range(row_bytes):
                line[i] = (line[i] + prev[i]) & 255
        elif kind == 3:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                up = prev[i] if prev is not None else 0
                line[i] = (line[i] + ((left + up) >> 1)) & 255
        elif kind == 4:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                up = prev[i] if prev is not None else 0
                corner = prev[i - bpp] if prev is not None and i >= bpp else 0
                line[i] = (line[i] + _paeth(left, up, corner)) & 255
        elif kind > 4:
            raise Unreadable()
        out.append(line)
        prev = line
        at += 1 + row_bytes
    return out, at


def _samples(line, count, depth):
    if depth == 8:
        return line[:count]
    if depth == 16:
        return [(line[2 * i] << 8) | line[2 * i + 1] for i in range(count)]
    mask, out = (1 << depth) - 1, []
    for i in range(count):
        bit = i * depth
        out.append((line[bit >> 3] >> (8 - depth - (bit & 7))) & mask)
    return out


def decode(data):
    (width, height, depth, kind, _, _, interlace), palette, trns, idat = _chunks(bytes(data))
    if kind not in DEPTHS or depth not in DEPTHS[kind] or interlace > 1:
        raise Unreadable()
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise Unreadable()
    if kind == 3 and palette is None:
        raise Unreadable()
    channels = CHANNELS[kind]
    bits = channels * depth
    bpp = max(1, bits >> 3)
    passes = _passes(width, height, interlace)
    need = sum(ph * (1 + -(-pw * bits // 8)) for _, _, _, _, pw, ph in passes)
    try:
        raw = zlib.decompressobj().decompress(idat, need + 1)
    except zlib.error:
        raise Unreadable()
    top = (1 << depth) - 1
    if depth == 16:
        def to8(v):
            return v >> 8
    elif depth == 8:
        def to8(v):
            return v
    else:
        def to8(v):
            return v * 255 // top
    key = None
    if trns is not None and kind == 0 and len(trns) >= 2:
        key = (struct.unpack(">H", trns[:2])[0],)
    if trns is not None and kind == 2 and len(trns) >= 6:
        key = struct.unpack(">HHH", trns[:6])
    rgba = bytearray(width * height * 4)
    at = 0
    for x0, y0, dx, dy, pw, ph in passes:
        lines, at = _unfilter(raw, at, -(-pw * bits // 8), ph, bpp)
        for y, line in enumerate(lines):
            s = _samples(line, pw * channels, depth)
            for x in range(pw):
                px = s[x * channels:(x + 1) * channels]
                a = 255
                if kind == 3:
                    i = px[0] * 3
                    r, g, b = (palette[i], palette[i + 1], palette[i + 2]) if i + 2 < len(palette) else (0, 0, 0)
                    if trns is not None and px[0] < len(trns):
                        a = trns[px[0]]
                elif kind in (0, 4):
                    r = g = b = to8(px[0])
                    if kind == 4:
                        a = to8(px[1])
                    elif key is not None and px[0] == key[0]:
                        a = 0
                else:
                    r, g, b = to8(px[0]), to8(px[1]), to8(px[2])
                    if kind == 6:
                        a = to8(px[3])
                    elif key is not None and tuple(px[:3]) == key:
                        a = 0
                o = ((y0 + y * dy) * width + x0 + x * dx) * 4
                rgba[o:o + 4] = bytes((r, g, b, a))
    return width, height, bytes(rgba)


def over_black(rgba):
    out = bytearray(len(rgba) // 4 * 3)
    for i in range(len(rgba) // 4):
        r, g, b, a = rgba[i * 4:i * 4 + 4]
        if a != 255:
            r, g, b = (r * a + 127) // 255, (g * a + 127) // 255, (b * a + 127) // 255
        out[i * 3:i * 3 + 3] = bytes((r, g, b))
    return bytes(out)


KEEP = (b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND")


def strip(data):
    data = bytes(data)
    if data[:8] != SIGNATURE:
        raise Unreadable()
    out, p = bytearray(SIGNATURE), 8
    while p + 12 <= len(data):
        length, kind = struct.unpack(">I4s", data[p:p + 8])
        end = p + 12 + length
        if end > len(data):
            break
        if kind in KEEP:
            out += data[p:end]
        if kind == b"IEND":
            return bytes(out)
        p = end
    raise Unreadable()


def _chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def encode(width, height, rgb, squeeze=False):
    raw = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    stream = bytearray(b"\x78\x01")
    for at in range(0, len(raw), 65535):
        part = raw[at:at + 65535]
        stream += bytes([1 if at + 65535 >= len(raw) else 0]) + struct.pack("<HH", len(part), len(part) ^ 0xFFFF)
        stream += part
    stream += struct.pack(">I", zlib.adler32(raw) & 0xFFFFFFFF)
    if squeeze:
        stream = zlib.compress(raw, 9)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", bytes(stream)) + _chunk(b"IEND", b"")

