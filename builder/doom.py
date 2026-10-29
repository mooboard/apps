#!/usr/bin/env python3
"""DOOM's WAD as the store ships it, and the one way to make it.

The package's data is the DOOM v1.9 shareware DOOM1.WAD (id's doom19s.zip, SHA-256 below) in an envelope, "MBW1"
then the WAD's length and CRC-32 little endian then the WAD zlib compressed, cut into data/wad-0.bin to wad-3.bin of
512 KB at most, as the board's Doom.cpp and Package.cpp read it (firmware c3874). This repo is public, so the WAD and
its chunks never go in git (Games/DOOM/.gitignore). Make the chunks from a local copy:

    python3 builder/doom.py /path/to/DOOM1.WAD

It checks the file's size and SHA-256 first and writes Games/DOOM/data/. A build without them skips DOOM with a note.
"""
import argparse
import hashlib
import os
import struct
import sys
import zlib

WAD_SIZE = 4196020
WAD_SHA256 = "1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771"
MAGIC = b"MBW1"
CHUNKS = tuple("wad-%d.bin" % i for i in range(4))
CHUNK_MAX = 512 * 1024   # a package's data entry (build.ENTRY_CAP, the board's kDataEntryCap)
HOW = "make them with python3 builder/doom.py /path/to/DOOM1.WAD (Games/DOOM/README.md)"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "Games", "DOOM", "data")


def check_wad(raw):
    if len(raw) != WAD_SIZE or hashlib.sha256(raw).hexdigest() != WAD_SHA256:
        raise ValueError("not the DOOM v1.9 shareware DOOM1.WAD (%d bytes, sha256 %s...%s)"
                         % (WAD_SIZE, WAD_SHA256[:8], WAD_SHA256[-4:]))


def chunks(raw):
    """the WAD as its four chunks by name"""
    check_wad(raw)
    body = MAGIC + struct.pack("<II", len(raw), zlib.crc32(raw) & 0xFFFFFFFF) + zlib.compress(raw, 9)
    parts = [body[at:at + CHUNK_MAX] for at in range(0, len(body), CHUNK_MAX)]
    if len(parts) != len(CHUNKS):
        raise ValueError("the WAD packs into %d chunks, not %d" % (len(parts), len(CHUNKS)))
    return dict(zip(CHUNKS, parts))


def unpack(data):
    """the WAD back from data/'s files as the board reads them + ValueError naming what is wrong"""
    if tuple(sorted(data)) != CHUNKS:
        raise ValueError("data/ must hold wad-0.bin to wad-3.bin alone")
    if any(not data[name] or len(data[name]) > CHUNK_MAX for name in CHUNKS):
        raise ValueError("a WAD chunk is empty or over %d KB" % (CHUNK_MAX >> 10))
    body = b"".join(data[name] for name in CHUNKS)
    if len(body) < 12 or body[:4] != MAGIC:
        raise ValueError("wad-0.bin does not open with the MBW1 envelope")
    size, crc = struct.unpack_from("<II", body, 4)
    if size != WAD_SIZE:
        raise ValueError("the envelope's WAD is %d bytes, not %d" % (size, WAD_SIZE))
    inflate = zlib.decompressobj()
    try:
        raw = inflate.decompress(body[12:], size + 1)
    except zlib.error as e:
        raise ValueError("the WAD chunks do not inflate (%s)" % e) from e
    if not inflate.eof or inflate.unused_data or len(raw) != size or zlib.crc32(raw) & 0xFFFFFFFF != crc:
        raise ValueError("the WAD chunks are cut short or their CRC-32 is wrong")
    check_wad(raw)
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description="DOOM's four WAD chunks from a local DOOM1.WAD")
    parser.add_argument("wad", help="DOOM1.WAD from id's doom19s.zip (v1.9 shareware)")
    parser.add_argument("--out", default=OUT, help="where the chunks go (default Games/DOOM/data)")
    args = parser.parse_args(argv)
    with open(args.wad, "rb") as f:
        raw = f.read(WAD_SIZE + 1)
    try:
        parts = chunks(raw)
    except ValueError as e:
        print("refused: %s: %s" % (args.wad, e), file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)
    for name in os.listdir(args.out):
        if name.startswith("wad-") and name.endswith(".bin"):
            os.remove(os.path.join(args.out, name))
    for name, body in parts.items():
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(body)
    print("%s: %s, %d bytes" % (args.out, ", ".join(parts), sum(map(len, parts.values()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
