#!/usr/bin/env python3
"""Draw the October icon refresh at its native 32 LED pixels.

Run with the workspace's Pillow environment. No resampling, gradients, or
antialiasing: the shapes and small palette remain legible in the phone store.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BG = "#08111c"
INK = "#20334a"
MUTED = "#526b85"
WHITE = "#e8f5ff"
CYAN = "#4eecd5"
BLUE = "#38a8f8"
PINK = "#ff427e"
GOLD = "#ffd45c"
ORANGE = "#f68b3c"
GREEN = "#75d66e"


def canvas():
    im = Image.new("RGB", (32, 32), BG)
    return im, ImageDraw.Draw(im)


def sprite(d, x, y, rows, colors):
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch in colors:
                d.point((x + xx, y + yy), fill=colors[ch])


def sprout():
    im, d = canvas()
    d.line((16, 18, 16, 9), fill=GREEN, width=2)
    d.polygon([(15, 13), (8, 12), (5, 7), (11, 7), (15, 10)], fill=GREEN)
    d.polygon([(17, 10), (20, 5), (27, 4), (25, 10), (18, 13)], fill=CYAN)
    d.line((9, 9, 14, 12), fill="#35945d")
    d.rectangle((7, 18, 25, 21), fill=ORANGE)
    d.polygon([(9, 22), (23, 22), (21, 28), (11, 28)], fill="#bc563c")
    d.line((10, 22, 12, 26), fill="#efad6a", width=2)
    d.line((9, 29, 24, 29), fill=INK)
    return im


def cyber_city():
    im, d = canvas()
    d.rectangle((3, 10, 10, 25), fill=INK)
    d.rectangle((12, 4, 21, 25), fill="#342648")
    d.rectangle((23, 13, 29, 25), fill=INK)
    d.line((16, 1, 16, 3), fill=CYAN)
    for x, y, c in [(5, 13, BLUE), (5, 20, BLUE), (14, 7, CYAN), (18, 7, CYAN),
                    (14, 11, CYAN), (18, 11, CYAN), (25, 16, GOLD), (25, 21, GOLD)]:
        d.rectangle((x, y, x + 1, y + 2), fill=c)
    d.rectangle((9, 15, 15, 23), fill=PINK)
    d.line((11, 17, 13, 17), fill=WHITE)
    d.line((11, 20, 13, 20), fill=WHITE)
    d.line((2, 26, 29, 26), fill=PINK)
    d.line((9, 29, 15, 29), fill="#82354e")
    d.line((20, 28, 24, 28), fill="#246c7e")
    return im


def waterfall():
    im, d = canvas()
    d.polygon([(2, 5), (12, 5), (12, 24), (4, 27), (2, 22)], fill=INK)
    d.polygon([(22, 5), (29, 5), (29, 25), (23, 25)], fill=INK)
    d.rectangle((11, 5, 22, 22), fill=BLUE)
    d.rectangle((14, 5, 16, 23), fill=WHITE)
    d.line((20, 6, 20, 19), fill=CYAN, width=2)
    d.line((3, 5, 10, 5), fill=GREEN, width=2)
    d.line((23, 5, 29, 5), fill=GREEN, width=2)
    d.ellipse((7, 22, 26, 29), fill="#236196")
    d.line((10, 25, 23, 25), fill=CYAN)
    d.line((13, 28, 20, 28), fill=BLUE)
    for pt in [(9, 21), (24, 21), (6, 24), (27, 24), (12, 22), (22, 23)]:
        d.point(pt, fill=WHITE)
    return im


def cassette():
    im, d = canvas()
    d.rectangle((3, 6, 28, 26), fill=MUTED)
    d.rectangle((5, 8, 26, 16), fill=GOLD)
    d.rectangle((7, 10, 24, 11), fill="#ad743c")
    d.rectangle((6, 14, 25, 21), fill=INK)
    for x in [10, 21]:
        d.ellipse((x - 3, 14, x + 3, 20), fill=WHITE)
        d.rectangle((x - 1, 16, x + 1, 18), fill=INK)
    d.line((13, 18, 18, 18), fill=WHITE)
    d.polygon([(9, 25), (11, 22), (21, 22), (23, 25)], fill=BG)
    for pt in [(5, 24), (26, 24)]:
        d.point(pt, fill=WHITE)
    return im


DINO = [".......WWWWW", "......WWKWWW", "......WWWWWW", "......WWW...",
        "W....WWWWWW.", "WW..WWWWW...", "WWWWWWWWW...", ".WWWWWWWW...",
        "..WWWWWW....", "...WW.WW....", "...W...W....", "...WW..WW..."]


def dino():
    im, d = canvas()
    sprite(d, 4, 11, DINO, {"W": WHITE, "K": BG})
    d.rectangle((23, 15, 25, 25), fill=GREEN)
    d.line([(20, 19), (20, 22), (23, 22)], fill=GREEN, width=2)
    d.line([(28, 17), (28, 20), (25, 20)], fill=GREEN, width=2)
    d.line((2, 26, 29, 26), fill=MUTED)
    d.point((6, 29), fill=MUTED)
    d.line((18, 29, 21, 29), fill=INK)
    d.rectangle((23, 4, 26, 7), fill=GOLD)
    return im


def racer():
    im, d = canvas()
    d.polygon([(8, 2), (23, 2), (30, 30), (1, 30)], fill=INK)
    d.line((8, 2, 1, 30), fill=CYAN)
    d.line((23, 2, 30, 30), fill=PINK)
    for y in [3, 10, 26]:
        d.rectangle((15, y, 16, y + 3), fill=WHITE)
    d.rectangle((11, 14, 20, 23), fill=PINK)
    d.rectangle((12, 11, 19, 22), fill=PINK)
    d.rectangle((13, 13, 18, 16), fill=CYAN)
    d.line((13, 19, 18, 19), fill="#b62457")
    for x in [10, 21]:
        d.rectangle((x, 15, x, 18), fill=BG)
        d.rectangle((x, 21, x, 23), fill=BG)
    d.point((12, 23), fill=GOLD)
    d.point((19, 23), fill=GOLD)
    d.line((11, 26, 10, 29), fill=ORANGE)
    d.line((20, 26, 21, 29), fill=GOLD)
    return im


def lander(asteroid=False):
    im, d = canvas()
    for pt in [(4, 4), (25, 3), (28, 11), (6, 15)]:
        d.point(pt, fill=MUTED)
    if asteroid:
        d.polygon([(1, 25), (7, 21), (12, 27), (20, 25), (25, 19), (30, 24), (30, 30), (1, 30)], fill=MUTED)
        d.polygon([(1, 2), (8, 2), (5, 7), (2, 10)], fill=INK)
        d.rectangle((5, 24, 13, 25), fill=CYAN)
        d.polygon([(16, 5), (21, 9), (21, 16), (12, 16), (12, 9)], fill=WHITE)
        d.rectangle((14, 10, 19, 13), fill=BLUE)
        d.polygon([(14, 17), (19, 17), (17, 23)], fill=ORANGE)
        d.point((17, 19), fill=GOLD)
    else:
        d.ellipse((3, 21, 28, 39), fill=INK)
        d.rectangle((7, 26, 24, 27), fill=CYAN)
        d.rectangle((11, 8, 21, 15), fill=GOLD)
        d.rectangle((13, 6, 19, 8), fill=GOLD)
        d.rectangle((14, 9, 18, 12), fill=BG)
        d.line([(12, 16), (8, 22), (5, 22)], fill=WHITE)
        d.line([(20, 16), (24, 22), (27, 22)], fill=WHITE)
        d.rectangle((14, 16, 18, 17), fill=MUTED)
        d.polygon([(15, 18), (17, 18), (16, 22)], fill=ORANGE)
    return im


def pinball():
    im, d = canvas()
    d.line([(4, 28), (4, 7), (8, 3), (24, 3), (28, 7), (28, 28)], fill=BLUE, width=2)
    d.line([(25, 26), (25, 9), (22, 6)], fill=CYAN)
    for x, y, c in [(10, 10, PINK), (19, 15, GOLD), (10, 19, CYAN)]:
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=c)
        d.point((x - 1, y - 1), fill=WHITE)
    d.line((8, 25, 13, 28), fill=PINK, width=2)
    d.line((23, 25, 18, 28), fill=PINK, width=2)
    d.rectangle((19, 7, 21, 9), fill=WHITE)
    return im


def dungeon():
    im, d = canvas()
    d.rectangle((4, 4, 27, 28), fill=INK)
    for y in [4, 9, 14, 19, 24, 28]:
        d.line((4, y, 27, y), fill=MUTED)
    for y in [5, 15, 25]:
        d.line((9, y, 9, y + 3), fill=MUTED)
        d.line((22, y, 22, y + 3), fill=MUTED)
    d.rectangle((11, 9, 22, 28), fill=BG)
    d.rectangle((14, 6, 19, 9), fill=BG)
    d.rectangle((13, 16, 17, 20), fill=GOLD)
    d.rectangle((12, 21, 18, 25), fill=BLUE)
    d.line((13, 26, 13, 28), fill=WHITE)
    d.line((17, 26, 17, 28), fill=WHITE)
    d.line((21, 18, 21, 25), fill=WHITE)
    d.line((19, 23, 23, 23), fill=CYAN)
    d.rectangle((5, 15, 7, 18), fill=ORANGE)
    d.point((6, 13), fill=GOLD)
    return im


def mines():
    im, d = canvas()
    for row in range(3):
        for col in range(3):
            x, y = 4 + col * 8, 4 + row * 8
            d.rectangle((x, y, x + 6, y + 6), fill=INK)
            d.line((x, y, x + 6, y), fill=MUTED)
            d.line((x, y, x, y + 6), fill=MUTED)
    d.line((16, 5, 16, 10), fill=WHITE)
    d.polygon([(16, 5), (21, 7), (16, 8)], fill=PINK)
    d.rectangle((12, 12, 18, 18), fill="#b9d4e8")
    d.line((15, 13, 15, 17), fill="#236196")
    d.line((14, 14, 15, 13), fill="#236196")
    d.line((14, 17, 16, 17), fill="#236196")
    d.ellipse((21, 21, 25, 25), fill=BG)
    d.line((23, 19, 23, 27), fill=BG)
    d.line((19, 23, 27, 23), fill=BG)
    d.point((22, 22), fill=WHITE)
    return im


def missile():
    im, d = canvas()
    d.line((4, 3, 13, 15), fill=PINK)
    d.line((28, 3, 22, 11), fill=PINK)
    d.ellipse((15, 8, 28, 21), outline=ORANGE, width=2)
    d.ellipse((19, 12, 24, 17), fill=GOLD)
    d.line((15, 27, 21, 18), fill=CYAN)
    d.polygon([(10, 29), (15, 24), (20, 29)], fill=CYAN)
    for x, h in [(3, 5), (7, 8), (24, 6), (28, 4)]:
        d.rectangle((x, 29 - h, x + 2, 29), fill=MUTED)
        d.point((x + 1, 30 - h), fill=GOLD)
    return im


def word_guess():
    im, d = canvas()
    colors = [[MUTED, GOLD, MUTED], [GOLD, GREEN, MUTED], [GREEN, GREEN, GREEN]]
    letters = [["W", "O", "R"], ["R", "O", "W"], ["R", "O", "W"]]
    glyphs = {"W": ["101", "101", "111", "111", "101"],
              "O": ["111", "101", "101", "101", "111"],
              "R": ["110", "101", "110", "101", "101"]}
    for r in range(3):
        for c in range(3):
            x, y = 4 + c * 8, 4 + r * 8
            d.rectangle((x, y, x + 6, y + 6), fill=colors[r][c])
            sprite(d, x + 2, y + 1, glyphs[letters[r][c]], {"1": BG})
    return im


def binary():
    im, d = canvas()
    for col, bits in enumerate([1, 2, 4, 8]):
        for row in range(4):
            x, y = 5 + col * 6, 5 + row * 6
            d.rectangle((x, y, x + 3, y + 3), fill=CYAN if bits & (8 >> row) else INK)
    d.line((4, 29, 12, 29), fill=BLUE)
    d.line((18, 29, 26, 29), fill=PINK)
    return im


def world_clock():
    im, d = canvas()
    d.ellipse((6, 3, 26, 23), outline=BLUE)
    d.ellipse((12, 3, 20, 23), outline=BLUE)
    d.line((6, 13, 26, 13), fill=BLUE)
    for x, y, c, hand in [(3, 18, GOLD, (7, 21)), (13, 20, WHITE, (16, 24)), (23, 18, CYAN, (26, 23))]:
        d.ellipse((x - 2, y - 2, x + 8, y + 8), fill=BG, outline=c)
        d.line((x + 3, y + 3, x + 3, y), fill=c)
        d.line((x + 3, y + 3, hand[0], hand[1]), fill=c)
    return im


def briefing():
    im, d = canvas()
    d.rectangle((5, 4, 25, 28), fill=WHITE)
    d.rectangle((8, 8, 22, 12), fill=BLUE)
    for y, end in [(16, 21), (20, 19), (24, 15)]:
        d.line((8, y, end, y), fill=MUTED)
    d.rectangle((20, 18, 28, 26), fill=BG)
    d.line((24, 17, 24, 27), fill=GOLD)
    d.line((19, 22, 29, 22), fill=GOLD)
    d.rectangle((23, 21, 25, 23), fill=GOLD)
    return im


ICONS = {
    "Lifestyle/Desk Sprout": sprout,
    "Ambiance/Cyber City": cyber_city,
    "Ambiance/Pixel Waterfall": waterfall,
    "Ambiance/Vintage Cassette Deck": cassette,
    "Games/Chrome Dino Runner": dino,
    "Games/Micro Racer": racer,
    "Games/Asteroid Lander": lambda: lander(True),
    "Games/Lunar Lander": lander,
    "Games/Pixel Pinball": pinball,
    "Games/Tiny Dungeon Crawler": dungeon,
    "Games/Minesweeper": mines,
    "Games/Missile Defense": missile,
    "Games/Word Guess": word_guess,
    "Clock/Binary Clock": binary,
    "Clock/World Clock": world_clock,
    "AI/AI Briefing": briefing,
}


def main():
    for folder, draw in ICONS.items():
        # Lossless palette encoding, with only the PNG chunks accepted by the store.
        im = draw().convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
        im.save(ROOT / folder / "icon.png", optimize=True)
        print(folder)


if __name__ == "__main__":
    main()
