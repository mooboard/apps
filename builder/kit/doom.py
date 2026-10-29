#!/usr/bin/env python3
"""Fetch verified DOOM shareware data and prepare the store's compressed WAD chunks."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import urllib.request
import zlib

SHA256 = '1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771'
URL = 'https://raw.githubusercontent.com/Doom-Utils/shareware-collection/master/Doom%201.9/doom1.wad'

def prepare(raw, target):
    if len(raw) != 4196020 or hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Not the unmodified DOOM v1.9 shareware WAD')
    body = b'MBW1' + struct.pack('<II', len(raw), zlib.crc32(raw)) + zlib.compress(raw, 9)
    target.mkdir(parents=True, exist_ok=True)
    for i, at in enumerate(range(0, len(body), 512*1024)):
        (target / f'wad-{i}.bin').write_bytes(body[at:at+512*1024])
    return len(body)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wad', type=Path, help='Existing verified shareware WAD; otherwise downloads it')
    args = parser.parse_args()
    raw = args.wad.read_bytes() if args.wad else urllib.request.urlopen(URL, timeout=60).read(4196021)
    root = Path(__file__).resolve().parents[2]
    print('Prepared', prepare(raw, root/'Games/DOOM/data'), 'bytes of compressed, verified shareware data')

if __name__ == '__main__': main()
