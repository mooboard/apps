import struct

MAX_PIXELS = 1 << 24
SHORTEST_CS = 3
LONGEST_CS = 65535
INTERLACE = ((0, 8), (4, 8), (2, 4), (1, 2))

FRAME_SIZE = "A frame must be {w}×{h}"
NO_FRAMES = "No frames to save"


class Unreadable(Exception):
    pass


def _sub_blocks(data, p):
    out = bytearray()
    while p < len(data):
        n = data[p]
        p += 1
        if n == 0:
            break
        out += data[p:p + n]
        p += n
    return bytes(out), min(p, len(data))


def _lzw_decode(data, min_size, count):
    clear = 1 << min_size
    end = clear + 1
    prefix = [0] * 4096
    suffix = bytearray(4096)
    for i in range(clear):
        suffix[i] = i
    stack = bytearray(4097)
    out = bytearray(count)
    size, nxt, old, first, acc, bits, pos, n = min_size + 1, end + 1, -1, 0, 0, 0, 0, 0
    while n < count:
        while bits < size and pos < len(data):
            acc |= data[pos] << bits
            pos += 1
            bits += 8
        if bits < size:
            break
        code = acc & ((1 << size) - 1)
        acc >>= size
        bits -= size
        if code == clear:
            size, nxt, old = min_size + 1, end + 1, -1
            continue
        if code == end:
            break
        if old == -1:
            if code >= clear:
                break
            out[n] = code
            n += 1
            old = first = code
            continue
        in_code, sp = code, 0
        if code >= nxt:
            if code > nxt:
                break
            stack[sp] = first
            sp += 1
            code = old
        while code > end:
            stack[sp] = suffix[code]
            sp += 1
            code = prefix[code]
        first = code
        stack[sp] = code
        sp += 1
        if nxt < 4096:
            prefix[nxt] = old
            suffix[nxt] = first
            nxt += 1
            if nxt == 1 << size and size < 12:
                size += 1
        while sp > 0 and n < count:
            sp -= 1
            out[n] = stack[sp]
            n += 1
        old = in_code
    return out[:n]


def _rows(height, interlaced):
    if not interlaced:
        return list(range(height))
    return [y for start, step in INTERLACE for y in range(start, height, step)]


def decode(data, whole=False):
    data = bytes(data)
    if len(data) < 13 or data[:3] != b"GIF" or data[3:6] not in (b"87a", b"89a"):
        raise Unreadable()
    w, h, flags = struct.unpack("<HHB", data[6:11])
    if w < 1 or h < 1 or w * h > MAX_PIXELS:
        raise Unreadable()
    p, table = 13, None
    if flags & 0x80:
        n = 2 << (flags & 7)
        table = data[p:p + n * 3]
        p += n * 3
    canvas = bytearray(w * h * 4)
    frames, control, last, ended = [], None, None, False
    while p < len(data):
        tag = data[p]
        p += 1
        if tag == 0x3B:
            ended = True
            break
        if tag == 0x21:
            if p >= len(data):
                break
            label = data[p]
            p += 1
            if label == 0xF9 and p + 4 < len(data) and data[p] >= 4:
                packed = data[p + 1]
                control = ((packed >> 2) & 7, (data[p + 2] | data[p + 3] << 8) * 10,
                           data[p + 4] if packed & 1 else -1)
            p = _sub_blocks(data, p)[1]
            continue
        if tag != 0x2C:
            if frames:
                break
            raise Unreadable()
        if p + 10 > len(data):
            break
        fx, fy, fw, fh, fflags = struct.unpack("<HHHHB", data[p:p + 9])
        p += 9
        frame_table = table
        if fflags & 0x80:
            n = 2 << (fflags & 7)
            frame_table = data[p:p + n * 3]
            p += n * 3
        if frame_table is None:
            raise Unreadable()
        min_size = data[p] if p < len(data) else 0
        p += 1
        if min_size < 2 or min_size > 11 or (whole and (fx + fw > w or fy + fh > h)):
            raise Unreadable()
        if whole:
            _blocks_end(data, p)
        codes, p = _sub_blocks(data, p)
        if (len(frames) + 1) * w * h > MAX_PIXELS or fw * fh > MAX_PIXELS:
            raise Unreadable()
        if last is not None and last[0] == 2:
            _, lx, ly, lw, lh, _ = last
            for y in range(ly, min(h, ly + lh)):
                for x in range(lx, min(w, lx + lw)):
                    canvas[(y * w + x) * 4:(y * w + x) * 4 + 4] = b"\0\0\0\0"
        elif last is not None and last[0] == 3 and last[5] is not None:
            canvas = last[5]
        disposal, delay, transparent = control or (0, 0, -1)
        control = None
        saved = bytearray(canvas) if disposal == 3 else None
        indices = _lzw_decode(codes, min_size, fw * fh)
        if whole and len(indices) < fw * fh:
            raise Unreadable()
        rows = _rows(fh, fflags & 0x40)
        for i in range(fh):
            y = fy + rows[i]
            if y >= h:
                continue
            for x in range(fw):
                cx = fx + x
                k = i * fw + x
                if cx >= w or k >= len(indices):
                    break
                index = indices[k]
                if index == transparent or index * 3 + 2 >= len(frame_table):
                    continue
                o = (y * w + cx) * 4
                canvas[o:o + 4] = frame_table[index * 3:index * 3 + 3] + b"\xff"
        rgb = bytearray(w * h * 3)
        rgb[0::3] = canvas[0::4]
        rgb[1::3] = canvas[1::4]
        rgb[2::3] = canvas[2::4]
        frames.append((bytes(rgb), delay))
        last = (disposal, fx, fy, fw, fh, saved)
    if not frames or (whole and not ended):
        raise Unreadable()
    return w, h, frames


def _blocks_end(data, p):
    while True:
        if p >= len(data):
            raise Unreadable()
        if data[p] == 0:
            return p + 1
        p += data[p] + 1


def strip(data):
    data = bytes(data)
    if len(data) < 13 or data[:3] != b"GIF":
        raise Unreadable()
    p = 13 + (3 * (2 << (data[10] & 7)) if data[10] & 0x80 else 0)
    out, control, looped = bytearray(data[:p]), b"", False
    while p < len(data):
        tag = data[p]
        if tag == 0x3B:
            return bytes(out + b"\x3b")
        if tag == 0x21 and p + 1 < len(data):
            end = _blocks_end(data, p + 2)
            if data[p + 1] == 0xF9 and data[p + 2] >= 4:
                control = b"\x21\xf9\x04" + data[p + 3:p + 7] + b"\x00"
            elif data[p + 1:p + 16] == b"\xff\x0bNETSCAPE2.0\x03\x01" and not looped:
                out += data[p:p + 18] + b"\x00"
                looped = True
        elif tag == 0x2C and p + 10 < len(data):
            table = 3 * (2 << (data[p + 9] & 7)) if data[p + 9] & 0x80 else 0
            end = _blocks_end(data, p + 11 + table)
            out += control + data[p:end]
            control = b""
        else:
            raise Unreadable()
        p = end
    raise Unreadable()


def _hundredths(ms):
    cs = int(ms / 10.0 + 0.5)
    return max(SHORTEST_CS, min(LONGEST_CS, cs))


def _pixels(rgb):
    return [rgb[i:i + 3] for i in range(0, len(rgb), 3)]


def _changed(shown, rgb, w, h):
    x0, y0, x1, y1 = w, h, -1, -1
    row = w * 3
    for y in range(h):
        a, b = shown[y * row:(y + 1) * row], rgb[y * row:(y + 1) * row]
        if a == b:
            continue
        y0, y1 = min(y0, y), y
        left = next(x for x in range(w) if a[x * 3:x * 3 + 3] != b[x * 3:x * 3 + 3])
        right = next(x for x in range(w - 1, -1, -1) if a[x * 3:x * 3 + 3] != b[x * 3:x * 3 + 3])
        x0, x1 = min(x0, left), max(x1, right)
    if y1 < 0:
        return 0, 0, 1, 1
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def _crop(rgb, w, box):
    x, y, bw, bh = box
    return b"".join(rgb[((y + r) * w + x) * 3:((y + r) * w + x + bw) * 3] for r in range(bh))


def _paste(shown, w, box, part):
    x, y, bw, bh = box
    out = bytearray(shown)
    for r in range(bh):
        out[((y + r) * w + x) * 3:((y + r) * w + x + bw) * 3] = part[r * bw * 3:(r + 1) * bw * 3]
    return bytes(out)


def _box(items):
    spans = [max(c[k] for c, _ in items) - min(c[k] for c, _ in items) for k in range(3)]
    return (max(spans), sum(n for _, n in items)), spans, items


def _median_cut(counts, budget):
    boxes = [_box(sorted(counts.items()))]
    while len(boxes) < budget:
        best = None
        for i, (key, _, items) in enumerate(boxes):
            if len(items) > 1 and (best is None or key > boxes[best][0]):
                best = i
        if best is None:
            break
        _, spans, items = boxes.pop(best)
        axis = spans.index(max(spans))
        items = sorted(items, key=lambda item: (item[0][axis], item[0]))
        total, run, cut = sum(n for _, n in items), 0, 1
        for j, (_, n) in enumerate(items[:-1]):
            run += n
            cut = j + 1
            if run * 2 >= total:
                break
        boxes[best:best] = [_box(items[:cut]), _box(items[cut:])]
    return [items for _, _, items in boxes]


def _quantize(pixels):
    counts = {}
    for c in pixels:
        counts[c] = counts.get(c, 0) + 1
    black = b"\0\0\0"
    has_black = counts.pop(black, 0) > 0
    mapping = {black: black} if has_black else {}
    for box in _median_cut(counts, 256 - (1 if has_black else 0)):
        total = sum(n for _, n in box)
        mean = bytes(int(sum(c[k] * n for c, n in box) / total + 0.5) for k in range(3))
        if mean == black:
            mean = max(box, key=lambda item: (item[1], item[0]))[0]
        for c, _ in box:
            mapping[c] = mean
    return mapping


def _table(colors):
    bits = 1
    while (1 << bits) < len(colors):
        bits += 1
    return bits, b"".join(colors) + b"\0\0\0" * ((1 << bits) - len(colors))


def _lzw_encode(indices, min_size):
    clear = 1 << min_size
    end = clear + 1
    size, nxt = min_size + 1, end + 1
    table = {}
    out = bytearray()
    acc = bits = 0

    def put(code, width):
        nonlocal acc, bits
        acc |= code << bits
        bits += width
        while bits >= 8:
            out.append(acc & 255)
            acc >>= 8
            bits -= 8

    put(clear, size)
    prefix = indices[0]
    for k in indices[1:]:
        key = prefix << 8 | k
        code = table.get(key)
        if code is not None:
            prefix = code
            continue
        put(prefix, size)
        if nxt < 4096:
            table[key] = nxt
            nxt += 1
            if nxt > 1 << size and size < 12:
                size += 1
        else:
            put(clear, size)
            table.clear()
            size, nxt = min_size + 1, end + 1
        prefix = k
    put(prefix, size)
    if nxt < 4096 and nxt + 1 > 1 << size and size < 12:
        size += 1
    put(end, size)
    if bits:
        out.append(acc & 255)
    return bytes(out)


def _blocks(data):
    return b"".join(bytes([len(data[i:i + 255])]) + data[i:i + 255] for i in range(0, len(data), 255)) + b"\0"


def encode(frames, width=128, height=32):
    merged = []
    for rgb, ms in frames:
        rgb = bytes(rgb)
        if len(rgb) != width * height * 3:
            raise ValueError(FRAME_SIZE.format(w=width, h=height))
        if merged and merged[-1][0] == rgb:
            merged[-1][1] += ms
        else:
            merged.append([rgb, ms])
    if not merged:
        raise ValueError(NO_FRAMES)
    every = set()
    for rgb, _ in merged:
        every.update(_pixels(rgb))
    shared = sorted(every) if len(every) <= 256 else None
    out = bytearray(b"GIF89a")
    if shared is not None:
        bits, table = _table(shared)
        out += struct.pack("<HHBBB", width, height, 0xF0 | (bits - 1), 0, 0) + table
        index = {c: i for i, c in enumerate(shared)}
    else:
        out += struct.pack("<HHBBB", width, height, 0x70, 0, 0)
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    shown = None
    for rgb, ms in merged:
        box = (0, 0, width, height) if shown is None else _changed(shown, rgb, width, height)
        part = _pixels(_crop(rgb, width, box))
        local = b""
        if shared is None:
            colors = sorted(set(part))
            if len(colors) > 256:
                mapping = _quantize(part)
                part = [mapping[c] for c in part]
                colors = sorted(set(part))
            bits, table = _table(colors)
            index = {c: i for i, c in enumerate(colors)}
            local = table
        out += b"\x21\xf9\x04" + bytes([1 << 2]) + struct.pack("<H", _hundredths(ms)) + b"\0\0"
        x, y, bw, bh = box
        out += b"\x2c" + struct.pack("<HHHHB", x, y, bw, bh, (0x80 | (bits - 1)) if local else 0) + local
        min_size = max(2, bits)
        out += bytes([min_size]) + _blocks(_lzw_encode([index[c] for c in part], min_size))
        shown = _paste(shown or bytes(width * height * 3), width, box, b"".join(part))
    out += b"\x3b"
    return bytes(out)
