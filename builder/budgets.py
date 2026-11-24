"""An app's estimated draw (firmware C9264): the panel's current from its listing shots' LEDs, the memory it takes
running, and its storage, as index2.json's "draw" carries them for the store's app page and the board's
memory check before Get. The build refuses an app past 90% of a budget.

The power model is pw_core/PanelPower.h's: the two panels' idle draw plus each channel's full-field current, scaled
by how much of full each LED's value lights (the driver's CIE 1931 table) at full brightness (level 255)."""
import io
import os
import zipfile

import listing

W, H = 128, 32
SCALE = 8   # a listing shot is the panel at 8 x (listing.py)
IDLE_MA = 200   # PanelPower.h kIdleMa
FULL_FIELD_MA = 1760   # PanelPower.h kFullFieldMa, one channel at 255 on every pixel, level 255
PANEL_BUDGET_MA = 2400   # PanelPower.h kPanelBudgetMa, the panels' cap on a USB-C supply
RAM_BUDGET = 512 * 1024   # pw_runtime Runtime::memoryLimit, the most a Lua app's heap may hold while it runs
STORAGE_BUDGET = {"s3": 2 * 1024 * 1024, "p4": 8 * 1024 * 1024}   # pw_apps BoardInfo::packageCap per board
RAM_BASE = {"lua54": 64 * 1024, "game": 32 * 1024}   # the runtime's own state before the app's files
RAM_BASE_RENDERER = 8 * 1024   # a firmware renderer's settings and state
LIMIT = 0.9   # the share of a budget an app may take


def lit(value):
    """the share of full light a channel value gives (CIE 1931 lightness to luminance, as the driver's table)"""
    lightness = value * 100.0 / 255.0
    return ((lightness + 16.0) / 116.0) ** 3 if lightness > 8.0 else lightness / 903.3


LIT = [lit(v) for v in range(256)]


def frame_ma(rows):
    """a shot's draw in mA at full brightness + each LED read at its 8 x 8 cell's middle"""
    total = 0.0
    for y in range(H):
        row = rows[y * SCALE + SCALE // 2]
        for x in range(W):
            r, g, b = row[x * SCALE + SCALE // 2][:3]
            total += LIT[r] + LIT[g] + LIT[b]
    return IDLE_MA + int(round(total * FULL_FIELD_MA / (W * H)))


def shots_ma(folder, where):
    """the mean of its listing shots' draw + None for an app with no listing yet"""
    shots = sorted(n for n in os.listdir(os.path.join(folder, listing.FOLDER))
                   if n.startswith("shot-") and n.endswith(".png")) \
        if os.path.isdir(os.path.join(folder, listing.FOLDER)) else []
    if not shots:
        return None
    draws = []
    for name in shots:
        with open(os.path.join(folder, listing.FOLDER, name), "rb") as f:
            draws.append(frame_ma(listing.png_pixels(f.read(), "%s/%s" % (where, name))))
    return int(round(sum(draws) / len(draws)))


def largest_file(package):
    """the most of a package the board reads in at once + an app opens one file at a time (Prayer's recordings, a
    Lua app's script, a word list)"""
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        return max([info.file_size for info in z.infolist()] or [0])


def ram_bytes(man, package):
    return RAM_BASE.get(man.get("uses"), RAM_BASE_RENDERER) + largest_file(package)


def estimate(folder, man, package, where):
    """the row's draw + 0 mA for an app with no listing shots yet, which the store's page leaves out"""
    return {"ma": shots_ma(folder, where) or 0, "ram": ram_bytes(man, package)}


def check(draw, size, boards, where, uses=None, board_cap=None):
    """the build's refusal for an app past 90% of a budget + the reason in the builder's words + memory is held to the
    Lua heap's cap, the one memory cap an app has (a firmware renderer's files may each be the 512 KB an entry takes)"""
    board_cap = board_cap or STORAGE_BUDGET
    over = []
    if draw.get("ma", 0) > LIMIT * PANEL_BUDGET_MA:
        over.append("power %d mA of %d" % (draw["ma"], PANEL_BUDGET_MA))
    if uses == "lua54" and draw["ram"] > LIMIT * RAM_BUDGET:
        over.append("memory %d of %d bytes" % (draw["ram"], RAM_BUDGET))
    for board in boards:
        if size > LIMIT * board_cap[board]:
            over.append("storage %d of %d bytes on %s" % (size, board_cap[board], board))
    if over:
        return "%s is past 90%% of its budget (%s)" % (where, ", ".join(over))
    return None
