"""The renamed apps rebuilt with drawings of their own (U570, first half of the list): Aurora Watch, Bonsai Life, Box
Breathing, Brew Companion, Desk Pet, Desk Sprout, Earthquake Seismograph, and Med Reminder. The store's rules and the
LED icons need only Python and Pillow. The apps run in the board's own Lua host (the dev kit's native runtime) + set
DEVKIT and STORE_APPS_HOST or those tests skip, as test_v044_apps.py does. Nothing here calls an API: the feeds are
builder/tests/renamed1/*.json, recorded from NOAA SWPC and USGS on Nov 24 and rewritten per test."""
import copy
import json
import math
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DEVKIT = os.environ.get("DEVKIT") or str(Path.home() / "mooboard/tmp-store-apps/devkit")
HOST = os.environ.get("STORE_APPS_HOST") or str(Path.home() / "mooboard/tmp-store-apps/tools")
HAVE = os.path.isdir(os.path.join(DEVKIT, "mooboard", "native")) and os.path.isfile(os.path.join(HOST, "host.py"))
if HAVE:
    sys.path.insert(0, HOST)
    import host

need = unittest.skipUnless(HAVE, "needs the dev kit's native runtime")
FIX = ROOT / "builder/tests/renamed1"
KP = json.loads((FIX / "noaa-kp.json").read_text(encoding="utf-8"))
SCALES = json.loads((FIX / "noaa-scales.json").read_text(encoding="utf-8"))
QUAKES = json.loads((FIX / "usgs-quakes.json").read_text(encoding="utf-8"))

AURORA, BONSAI, BOX = "Lifestyle/Aurora Watch", "Ambiance/Bonsai Life", "Lifestyle/Box Breathing"
BREW, PET, SPROUT = "Tools/Brew Companion", "Lifestyle/Desk Pet", "Lifestyle/Desk Sprout"
QUAKE, MEDS = "Tools/Earthquake Seismograph", "Lifestyle/Med Reminder"
APPS = (AURORA, BONSAI, BOX, BREW, PET, SPROUT, QUAKE, MEDS)
WITH_LED = tuple(a for a in APPS if not a.startswith("Ambiance/"))

BASE = 1795100000
DAY, HOUR = 86400, 3600
BOSTON, FAIRBANKS, MIAMI, HOBART = (42.35, -71.06), (64.84, -147.72), (25.76, -80.19), (-42.88, 147.33)


def app(folder, settings=None, data=None, state=None):
    return host.App(str(ROOT / folder), settings, state, data)


def frame(a, at=BASE, ms=0, place=None, **kw):
    c = host.ctx(ms=ms, epoch=at - ms // 1000, **kw)
    if place:
        c |= {"lat": place[0], "lon": place[1]}
    return a.rt.frame(c)


def lit_in(rgb, x0, y0, x1, y1, test=None):
    """lit dots in the box x0..x1, y0..y1 inclusive (and passing test, given one)"""
    n = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            p = host.at(rgb, x, y)
            if p != (0, 0, 0) and (test is None or test(p)):
                n += 1
    return n


def brightest(rgb):
    return max(max(p) for p in host.lit(rgb))


def touching_edges(rgb):
    return [(x, y) for y in range(32) for x in range(128)
            if (x in (0, 127) or y in (0, 31)) and host.at(rgb, x, y) != (0, 0, 0)]


def green(p):
    return p[1] > 110 and p[1] > p[0] + 30 and p[1] > p[2] + 20


def pink(p):
    return p[0] > 180 and p[2] > 120 and p[1] < p[0] - 30


def orange(p):
    return p[0] > 180 and 50 < p[1] < 170 and p[2] < 80


def white(p):
    return min(p) > 200


def feed(key, value):
    return {key: {"status": "ok", "value": value}}


# ---------------------------------------------------------------------------------------------------------- rules
class RenamedStoreRules(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "builder"))
        import build
        self.build = build

    def man(self, folder):
        return json.loads((ROOT / folder / "mooboard.json").read_text(encoding="utf-8"))

    def test_each_app_has_its_lua_icon_readme_and_history(self):
        for folder in APPS:
            names = ["mooboard.json", "app.lua", "icon.png", "README.md", "listing/history.json"]
            names += ["listing/icon-led.png"] if folder in WITH_LED else []
            for name in names:
                self.assertTrue((ROOT / folder / name).exists(), "%s/%s" % (folder, name))
        self.assertFalse((ROOT / BONSAI / "listing/icon-led.png").exists(), "Ambiance apps have no Home tile")

    def test_each_app_passes_the_stores_live_app_checks(self):
        for folder in APPS:
            category, name = folder.split("/")
            man = self.build.load_app(str(ROOT), category, name)[0]
            self.assertEqual((man["format"], man["runtime"], man["category"]), (3, "lua54", category), folder)
            self.assertEqual((man["version"], man["by"], man["boards"]), ("1.0.0", "mooboard", ["s3", "p4"]), folder)

    def test_ids_are_new_to_the_store(self):
        ids = {}
        for path in ROOT.glob("*/*/mooboard.json"):
            ids.setdefault(json.loads(path.read_text(encoding="utf-8"))["id"], []).append(path.parent.name)
        for folder in APPS:
            self.assertEqual(ids[self.man(folder)["id"]], [folder.split("/")[1]], folder)

    def test_apps_that_use_the_boards_place_need_0_4_4(self):
        for folder in APPS:
            lua = (ROOT / folder / "app.lua").read_text(encoding="utf-8")
            want = "0.4.4" if "ctx.lat" in lua and folder != BONSAI else "0.4.1"
            self.assertEqual(self.man(folder)["minFirmware"], want, folder)

    def test_every_option_and_control_the_lua_reads_is_in_the_manifest(self):
        for folder in APPS:
            man = self.man(folder)
            lua = (ROOT / folder / "app.lua").read_text(encoding="utf-8")
            for s in man.get("settings", []):
                if s["type"] == "choice" and "settings.%s" % s["key"] in lua:
                    for option in s["options"]:
                        self.assertIn('"%s"' % option, lua, (folder, option))
            for key in re.findall(r"settings\.([a-z_]+)", lua):
                self.assertIn(key, [s["key"] for s in man.get("settings", [])], folder)
            buttons = {c["key"] for c in man.get("controls", []) if c["type"] == "button"}
            self.assertEqual(set(re.findall(r'input\.control == "([a-z_]+)"', lua)), buttons, folder)
            for key in [c["key"] for c in man.get("controls", []) if c["type"] == "readout"]:
                self.assertTrue(re.search(r"\bstate\.%s\s*[,=]" % key, lua), (folder, key))

    def test_public_text_has_no_em_dash_capital_mooboard_colon_or_semicolon_in_a_sentence(self):
        for folder in APPS:
            for name in ("mooboard.json", "README.md", "listing/history.json", "app.lua"):
                text = (ROOT / folder / name).read_text(encoding="utf-8")
                self.assertNotIn("—", text, folder)
                self.assertNotIn("Mooboard", text, folder)
            readme = (ROOT / folder / "README.md").read_text(encoding="utf-8")
            prose = [line for line in readme.splitlines() if line and not line.startswith("#")]
            self.assertFalse([line for line in prose if ": " in line or ";" in line], folder)
            man = self.man(folder)
            words = [man["description"]] + [s["label"] for s in man.get("settings", [])] + \
                [c["label"] for c in man.get("controls", [])]
            self.assertFalse([w for w in words if ":" in w or ";" in w], folder)
            for word in ("colour", "favourite", "grey", "centre", "metre"):
                self.assertNotIn(word, readme.lower() + json.dumps(man).lower(), folder)

    def test_history_starts_at_one_point_oh(self):
        for folder in APPS:
            rows = json.loads((ROOT / folder / "listing/history.json").read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1, folder)
            self.assertEqual((rows[0]["version"], rows[0]["date"]), ("1.0", "2026-11-24"), folder)
            self.assertTrue(rows[0]["notes"].startswith("First release."), folder)

    def test_the_feeds_are_keyless_https_and_small(self):
        aurora = {s["key"]: s for s in self.man(AURORA)["sources"]}
        self.assertEqual(aurora["kp"]["url"], "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")
        self.assertEqual(aurora["scales"]["url"], "https://services.swpc.noaa.gov/products/noaa-scales.json")
        [quakes] = self.man(QUAKE)["sources"]
        self.assertEqual(quakes["url"], "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=4"
                                        "&orderby=time&minmagnitude={settings.min}")
        for source in list(aurora.values()) + [quakes]:
            self.assertGreaterEqual(source["refresh"], 300)
            self.assertNotIn("headers", source)
        # each recorded response sits under the board's 7.5 KB a feed keeps
        for name in ("noaa-kp.json", "noaa-scales.json", "usgs-quakes.json"):
            self.assertLess((FIX / name).stat().st_size, 7 * 1024, name)

    def test_brew_presets_are_a_button_each(self):
        brews = [(c["key"], c["label"]) for c in self.man(BREW)["controls"] if c["type"] == "button"]
        self.assertEqual(brews, [("green", "Green tea"), ("black", "Black tea"), ("oolong", "Oolong"),
                                 ("herbal", "Herbal tea"), ("press", "French press"), ("stop", "Stop")])


class RenamedLedIcons(unittest.TestCase):
    """Home's icon for each non-Ambiance app: 12 wide, 2 to 32 frames, 4 KB at most, a loop that moves, and icon.png
    its first frame at 2x. Bonsai Life (Ambiance) has only its 32 x 32 icon.png."""

    def setUp(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("needs Pillow")
        self.Image = Image

    def frames(self, folder):
        path = ROOT / folder / "listing/icon-led.png"
        img = self.Image.open(path).convert("RGB")
        self.assertEqual((img.width, img.height % 12), (12, 0), folder)
        self.assertTrue(2 <= img.height // 12 <= 32, (folder, img.height // 12))
        self.assertLessEqual(path.stat().st_size, 4096, folder)
        return [tuple(img.getpixel((x, f * 12 + y)) for y in range(12) for x in range(12))
                for f in range(img.height // 12)]

    def test_the_loops_move(self):
        for folder in WITH_LED:
            self.assertGreaterEqual(len(set(self.frames(folder))), 4, folder)

    def test_the_still_icon_is_the_loops_first_frame(self):
        for folder in WITH_LED:
            icon = self.Image.open(ROOT / folder / "icon.png").convert("RGB")
            self.assertEqual(icon.size, (32, 32), folder)
            got = tuple(icon.getpixel((4 + x * 2, 4 + y * 2)) for y in range(12) for x in range(12))
            self.assertEqual(got, self.frames(folder)[0], folder)

    def test_the_icons_are_not_each_others(self):
        firsts = [self.frames(folder)[0] for folder in WITH_LED]
        self.assertEqual(len(set(firsts)), len(firsts))

    def test_the_bonsai_icon_is_a_tree_in_a_pot(self):
        icon = self.Image.open(ROOT / BONSAI / "icon.png").convert("RGB")
        self.assertEqual(icon.size, (32, 32))
        dots = [icon.getpixel((x, y)) for y in range(32) for x in range(32)]
        self.assertGreater(sum(1 for p in dots if green(p)), 40)
        self.assertGreater(sum(1 for p in dots if p != (0, 0, 0)), 120)


# ----------------------------------------------------------------------------------------------------- box breathing
@need
class BoxBreathingApp(unittest.TestCase):
    def run_at(self, a, ms, **kw):
        frame(a, ms=ms, **kw)
        return a.state()

    def test_box_is_in_hold_out_hold_four_seconds_each(self):
        a = app(BOX)
        got = [self.run_at(a, ms)["phase"] for ms in (0, 4500, 8500, 12500, 16500)]
        self.assertEqual(got, ["in", "hold", "out", "rest", "in"])
        self.assertEqual(a.state()["rounds"], 1)

    def test_relax_is_four_seven_eight(self):
        a = app(BOX, {"pattern": "Relax 4-7-8"})
        got = [self.run_at(a, ms)["phase"] for ms in (0, 4500, 11500, 19500)]
        self.assertEqual(got, ["in", "hold", "out", "in"])

    def test_even_is_five_in_and_five_out(self):
        a = app(BOX, {"pattern": "Even 5-5"})
        got = [self.run_at(a, ms)["phase"] for ms in (0, 5500, 10500)]
        self.assertEqual(got, ["in", "out", "in"])

    def test_the_count_is_the_seconds_left_in_the_phase(self):
        a = app(BOX)
        self.assertEqual([self.run_at(a, ms)["left"] for ms in (0, 1000, 3500, 4000)], [4, 3, 1, 4])

    def test_start_over_counts_from_zero(self):
        a = app(BOX)
        self.run_at(a, 0)
        self.run_at(a, 20000)
        self.assertEqual(a.state()["rounds"], 1)
        a.press("restart")
        s = self.run_at(a, 21000)
        self.assertEqual((s["rounds"], s["phase"], s["left"]), (0, "in", 3))

    def test_the_square_fills_as_you_breathe_in_and_empties_as_you_breathe_out(self):
        a = app(BOX)
        inside = lambda rgb: lit_in(rgb, 8, 7, 23, 24)
        early, full, out = inside(frame(a, ms=600)), inside(frame(a, ms=3900)), inside(frame(a, ms=11500))
        self.assertLess(early, full)
        self.assertLess(out, full)

    def test_the_color_is_the_one_picked_and_night_is_dim(self):
        a, b = app(BOX), app(BOX, {"color": "#FF7A21"})
        self.assertNotEqual(frame(a, ms=2000), frame(b, ms=2000))
        self.assertLess(brightest(frame(app(BOX), ms=2000, night=True)), 130)

    def test_nothing_touches_the_edges(self):
        a = app(BOX)
        for ms in range(0, 16000, 700):
            self.assertEqual(touching_edges(frame(a, ms=ms)), [], ms)


@need
class KitCheckFrame(unittest.TestCase):
    """the dev kit's build draws one frame with no date and no clock (live.py) + every app draws it without an error"""
    CTX = {"monoMs": 0, "elapsedMs": 0, "epochSec": 0, "hour": 12, "minute": 0, "second": 0, "timeValid": False,
           "clock24": False, "seconds": True, "night": False, "online": False}

    def test_every_app_draws_the_kits_check_frame(self):
        for folder in APPS:
            a = app(folder)
            a.rt.frame(dict(self.CTX))
            a.rt.frame(dict(self.CTX, monoMs=500, elapsedMs=500))

    def test_med_reminder_counts_doses_before_the_clock_is_set(self):
        a = app(MEDS)
        a.rt.frame(dict(self.CTX, hour=9))
        self.assertEqual((a.state()["next"], a.state()["today"]), ("now", "0 of 1"))


# ------------------------------------------------------------------------------------------------------ desk sprout
@need
class DeskSproutApp(unittest.TestCase):
    def test_a_new_plant_waits_its_interval_and_then_asks(self):
        a = app(SPROUT)
        frame(a)
        self.assertEqual((a.state()["next"], a.state()["mood"]), ("in 7 days", "happy"))
        frame(a, at=BASE + 6 * DAY)
        self.assertEqual((a.state()["next"], a.state()["mood"]), ("in 1 day", "thirsty"))
        frame(a, at=BASE + 7 * DAY - 3 * HOUR)
        self.assertEqual(a.state()["next"], "in 3 h")
        frame(a, at=BASE + 7 * DAY)
        self.assertEqual((a.state()["next"], a.state()["mood"]), ("now", "wilting"))

    def test_watering_starts_the_interval_over(self):
        a = app(SPROUT)
        frame(a)
        frame(a, at=BASE + 8 * DAY)
        a.press("watered")
        frame(a, at=BASE + 8 * DAY + 60)
        self.assertEqual((a.state()["next"], a.state()["mood"]), ("in 7 days", "happy"))

    def test_the_interval_is_the_one_picked(self):
        a = app(SPROUT, {"every": "2 days"})
        frame(a)
        frame(a, at=BASE + 2 * DAY)
        self.assertEqual(a.state()["next"], "now")

    def test_the_plant_grows_with_the_weeks(self):
        young = frame(app(SPROUT, state={"born": BASE, "watered": BASE}))
        old = frame(app(SPROUT, state={"born": BASE - 40 * DAY, "watered": BASE}))
        self.assertGreater(lit_in(old, 1, 1, 40, 30, green), lit_in(young, 1, 1, 40, 30, green))

    def test_a_thirsty_plant_loses_its_green(self):
        st = {"born": BASE - 40 * DAY, "watered": BASE}
        happy = frame(app(SPROUT, state=dict(st)), at=BASE + DAY)
        wilting = frame(app(SPROUT, state=dict(st)), at=BASE + 9 * DAY)
        self.assertLess(lit_in(wilting, 1, 1, 40, 30, green), lit_in(happy, 1, 1, 40, 30, green) // 2)

    def test_nothing_touches_the_edges(self):
        a = app(SPROUT, state={"born": BASE - 60 * DAY, "watered": BASE})
        for k, ms in enumerate(range(0, 6000, 400)):
            self.assertEqual(touching_edges(frame(a, at=BASE + k * DAY, ms=ms)), [], k)


# ----------------------------------------------------------------------------------------------------- med reminder
@need
class MedReminderApp(unittest.TestCase):
    def at(self, a, hour, day=19, minute=0):
        frame(a, at=BASE + (day - 19) * DAY + hour * HOUR + minute * 60, hour=hour, minute=minute, day=day)
        return a.state()

    def test_once_a_day_waits_for_its_time_then_asks(self):
        a = app(MEDS)
        s = self.at(a, 7)
        self.assertEqual((s["next"], s["today"], s["due"]), ("8 am", "0 of 1", 0))
        s = self.at(a, 9)
        self.assertEqual((s["next"], s["due"]), ("now", 1))

    def test_i_took_it_counts_and_the_next_day_starts_over(self):
        a = app(MEDS)
        self.at(a, 9)
        a.press("took")
        s = self.at(a, 9, minute=5)
        self.assertEqual((s["next"], s["today"], s["due"]), ("tomorrow", "1 of 1", 0))
        a.press("took")
        self.assertEqual(self.at(a, 10)["today"], "1 of 1")   # never more than the doses
        s = self.at(a, 7, day=20)
        self.assertEqual((s["next"], s["today"]), ("8 am", "0 of 1"))

    def test_twice_and_three_times_a_day(self):
        a = app(MEDS, {"doses": "Twice a day"})
        self.at(a, 9)
        a.press("took")
        self.assertEqual(self.at(a, 10)["next"], "8 pm")
        self.assertEqual(self.at(a, 21)["next"], "now")
        b = app(MEDS, {"doses": "Three times"})
        self.at(b, 9)
        b.press("took")
        self.assertEqual(self.at(b, 10)["next"], "2 pm")

    def test_missed_doses_add_up(self):
        a = app(MEDS, {"doses": "Twice a day"})
        s = self.at(a, 21)
        self.assertEqual((s["today"], s["due"], s["next"]), ("0 of 2", 2, "now"))

    def test_the_first_dose_is_the_one_picked(self):
        a = app(MEDS, {"first": "6 am"})
        self.assertEqual(self.at(a, 5)["next"], "6 am")
        self.assertEqual(self.at(a, 6)["next"], "now")

    def test_a_due_dose_moves_and_a_quiet_one_rests(self):
        a = app(MEDS)
        frame(a, at=BASE + 7 * HOUR, hour=7)
        self.assertEqual(frame(a, at=BASE + 7 * HOUR, ms=0, hour=7), frame(a, at=BASE + 7 * HOUR, ms=600, hour=7))
        b = app(MEDS)
        due = [frame(b, at=BASE + 9 * HOUR, ms=ms, hour=9) for ms in (0, 300, 600, 900)]
        self.assertGreater(len(set(map(bytes, due))), 1)

    def test_night_is_dim_but_still_asks(self):
        a = app(MEDS, {"first": "9 am", "doses": "Twice a day"})
        rgb = frame(a, at=BASE + 22 * HOUR, hour=22, night=True)
        self.assertLess(brightest(rgb), 150)
        self.assertEqual(a.state()["next"], "now")

    def test_nothing_touches_the_edges(self):
        a = app(MEDS)
        for hour in (7, 9):
            for ms in range(0, 3000, 300):
                self.assertEqual(touching_edges(frame(a, at=BASE + hour * HOUR, ms=ms, hour=hour)), [])


# --------------------------------------------------------------------------------------------------------- desk pet
@need
class DeskPetApp(unittest.TestCase):
    def test_a_new_pet_is_happy_and_gets_hungry(self):
        a = app(PET)
        frame(a)
        self.assertEqual(a.state()["mood"], "happy")
        frame(a, at=BASE + 7 * HOUR)
        self.assertEqual(a.state()["mood"], "hungry")
        frame(a, at=BASE + 13 * HOUR)
        self.assertEqual(a.state()["mood"], "very hungry")

    def test_feeding_makes_it_happy(self):
        a = app(PET)
        frame(a)
        frame(a, at=BASE + 13 * HOUR)
        a.press("feed")
        frame(a, at=BASE + 13 * HOUR + 5)
        self.assertEqual(a.state()["mood"], "happy")

    def test_it_sleeps_at_night_unless_told_not_to(self):
        a = app(PET)
        frame(a, night=True)
        self.assertEqual(a.state()["mood"], "sleeping")
        b = app(PET, {"sleep": False})
        frame(b, night=True)
        self.assertEqual(b.state()["mood"], "happy")

    def test_it_wanders(self):
        a = app(PET)
        spots = set()
        for ms in range(0, 30000, 3000):
            rgb = frame(a, ms=ms)
            xs = [x for y in range(32) for x in range(128) if host.at(rgb, x, y) == (0xFF, 0xB7, 0xC9)]
            spots.add(min(xs) if xs else None)
        self.assertGreaterEqual(len(spots - {None}), 3)

    def test_petting_shows_hearts(self):
        a = app(PET)
        before = lit_in(frame(a, ms=100), 1, 1, 126, 30, lambda p: p[0] > 200 and p[1] < 90)
        a.press("pet")
        after = lit_in(frame(a, ms=600), 1, 1, 126, 30, lambda p: p[0] > 200 and p[1] < 90)
        self.assertGreater(after, before)

    def test_the_color_is_the_one_picked(self):
        rgb = frame(app(PET, {"color": "#77EDD7"}))
        self.assertGreater(lit_in(rgb, 1, 1, 126, 30, lambda p: p == (0x77, 0xED, 0xD7)), 10)

    def test_nothing_touches_the_edges(self):
        a = app(PET)
        for ms in range(0, 60000, 1500):
            self.assertEqual(touching_edges(frame(a, ms=ms)), [], ms)


# --------------------------------------------------------------------------------------------------- brew companion
@need
class BrewCompanionApp(unittest.TestCase):
    def test_a_brew_counts_down_and_is_ready(self):
        a = app(BREW)
        frame(a)
        self.assertEqual(a.state()["left"], "off")
        a.press("black")
        frame(a)
        self.assertEqual((a.state()["left"], a.state()["brew"]), ("4:00", "Black tea"))
        frame(a, at=BASE + 61)
        self.assertEqual(a.state()["left"], "2:59")
        frame(a, at=BASE + 240)
        self.assertEqual(a.state()["left"], "ready")
        frame(a, at=BASE + 240 + 11 * 60)
        self.assertEqual(a.state()["left"], "off")

    def test_each_preset_has_its_own_time(self):
        for arg, left in (("green", "2:30"), ("oolong", "3:00"), ("herbal", "5:00"), ("press", "4:00")):
            a = app(BREW)
            frame(a)
            a.press(arg)
            frame(a)
            self.assertEqual(a.state()["left"], left, arg)

    def test_stop_ends_it(self):
        a = app(BREW)
        frame(a)
        a.press("green")
        frame(a, at=BASE + 30)
        a.press("stop")
        frame(a, at=BASE + 31)
        self.assertEqual(a.state()["left"], "off")

    def test_a_french_press_is_not_a_mug(self):
        tea, press = app(BREW), app(BREW)
        for a, arg in ((tea, "black"), (press, "press")):
            frame(a)
            a.press(arg)
        self.assertNotEqual(lit_in(frame(tea, at=BASE + 30), 1, 1, 40, 30), lit_in(frame(press, at=BASE + 30), 1, 1, 40, 30))

    def test_the_tea_darkens_as_it_steeps(self):
        a = app(BREW)
        frame(a)
        a.press("black")
        glow = lambda rgb: sum(sum(host.at(rgb, x, y)) for y in range(18, 29) for x in range(8, 24))
        self.assertGreater(glow(frame(a, at=BASE + 5)), glow(frame(a, at=BASE + 230)) * 1.2)

    def test_nothing_touches_the_edges(self):
        for arg in ("green", "press"):
            a = app(BREW)
            frame(a)
            a.press(arg)
            for t in range(0, 400, 23):
                self.assertEqual(touching_edges(frame(a, at=BASE + t, ms=t * 37 % 1000)), [], (arg, t))


# ----------------------------------------------------------------------------------------------------- aurora watch
def kp_feed(kp=None, g=None):
    rows, scales = copy.deepcopy(KP), copy.deepcopy(SCALES)
    if kp is not None:
        rows[-1]["Kp"] = kp
    if g is not None:
        scales["1"]["G"]["Scale"] = str(g)
    return {"kp": {"status": "ok", "value": rows}, "scales": {"status": "ok", "value": scales}}


@need
class AuroraWatchApp(unittest.TestCase):
    def test_kp_now_is_the_last_reading(self):
        a = app(AURORA, data=kp_feed())
        frame(a, place=BOSTON)
        self.assertEqual(a.state()["kp"], "0.3")
        a = app(AURORA, data=kp_feed(kp=6.67))
        frame(a, place=BOSTON)
        self.assertEqual(a.state()["kp"], "6.7")

    def test_tonight_takes_the_storm_watch_when_it_is_higher(self):
        a = app(AURORA, data=kp_feed(kp=2.0, g=0))
        frame(a, place=BOSTON)
        self.assertEqual(a.state()["tonight"], "2")
        a = app(AURORA, data=kp_feed(kp=2.0, g=2))
        frame(a, place=BOSTON)
        self.assertEqual(a.state()["tonight"], "6")

    def test_the_kp_you_need_follows_your_magnetic_latitude(self):
        got = {}
        for name, place in (("boston", BOSTON), ("fairbanks", FAIRBANKS), ("miami", MIAMI), ("hobart", HOBART)):
            a = app(AURORA, data=kp_feed())
            frame(a, place=place)
            got[name] = a.state()["need"]
        self.assertEqual(got, {"boston": "6", "fairbanks": "0", "miami": "9+", "hobart": "7"})

    def test_look_north_or_south_when_tonight_is_enough(self):
        a = app(AURORA, data=kp_feed(kp=1, g=3))
        frame(a, place=BOSTON)
        self.assertEqual(a.state()["look"], "north")
        a = app(AURORA, data=kp_feed(kp=1, g=3))
        frame(a, place=HOBART)
        self.assertEqual(a.state()["look"], "south")
        a = app(AURORA, data=kp_feed(kp=1, g=0))
        frame(a, place=BOSTON)
        self.assertEqual(a.state()["look"], "none")

    def test_a_stronger_storm_draws_a_taller_aurora(self):
        quiet = frame(app(AURORA, data=kp_feed(kp=1, g=0)), place=BOSTON, ms=1000)
        storm = frame(app(AURORA, data=kp_feed(kp=7, g=3)), place=BOSTON, ms=1000)
        self.assertGreater(lit_in(storm, 1, 1, 44, 30, green), lit_in(quiet, 1, 1, 44, 30, green) + 30)

    def test_without_a_place_it_shows_the_kp_only(self):
        a = app(AURORA, data=kp_feed(kp=3))
        frame(a)
        self.assertEqual((a.state()["kp"], a.state().get("need")), ("3", None))

    def test_waiting_for_data_draws_a_title(self):
        a = app(AURORA)
        rgb = frame(a, place=BOSTON)
        self.assertGreater(len([p for p in host.lit(rgb) if p != (0, 0, 0)]), 20)
        self.assertIsNone(a.state().get("kp"))

    def test_nothing_touches_the_edges(self):
        a = app(AURORA, data=kp_feed(kp=8, g=4))
        for ms in range(0, 8000, 500):
            self.assertEqual(touching_edges(frame(a, place=BOSTON, ms=ms)), [], ms)


# ------------------------------------------------------------------------------------------- earthquake seismograph
NOW_Q = QUAKES["features"][0]["properties"]["time"] // 1000 + 300   # 5 min after the newest


def quakes(order=None, mags=None):
    v = copy.deepcopy(QUAKES)
    if mags:
        for f, m in zip(v["features"], mags):
            f["properties"]["mag"] = m
    if order:
        v["features"] = [v["features"][i] for i in order]
    return feed("quakes", v)


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


@need
class EarthquakeSeismographApp(unittest.TestCase):
    def test_the_newest_is_shown_whatever_the_order(self):
        a = app(QUAKE, data=quakes(order=[2, 3, 0, 1]))
        frame(a, at=NOW_Q, place=BOSTON)
        s = a.state()
        self.assertEqual((s["mag"], s["place"], s["ago"]), ("4.5", "La Tronosa, Panama", "5 min ago"))
        self.assertEqual(s["latest"], "M4.5 La Tronosa, Panama")

    def test_a_place_without_a_distance_stays_whole(self):
        a = app(QUAKE, data=quakes(order=[3]))
        frame(a, at=NOW_Q, place=BOSTON)
        self.assertEqual(a.state()["place"], "South Sandwich Islands region")

    def test_how_long_ago(self):
        t = QUAKES["features"][0]["properties"]["time"] // 1000
        for later, words in ((40, "now"), (59 * 60, "59 min ago"), (3 * HOUR + 60, "3 h ago"), (2 * DAY + 5, "2 days ago")):
            a = app(QUAKE, data=quakes())
            frame(a, at=t + later)
            self.assertEqual(a.state()["ago"], words, later)

    def test_the_distance_from_the_board_in_miles_or_kilometers(self):
        lon, lat = QUAKES["features"][0]["geometry"]["coordinates"][:2]
        want = miles(BOSTON, (lat, lon))
        a = app(QUAKE, data=quakes())
        frame(a, at=NOW_Q, place=BOSTON)
        self.assertEqual(a.state()["away"], "{:,} mi".format(int(round(want, -1))))
        a = app(QUAKE, {"units": "Kilometers"}, data=quakes())
        frame(a, at=NOW_Q, place=BOSTON)
        self.assertEqual(a.state()["away"], "{:,} km".format(int(round(want * 1.609344, -1))))
        a = app(QUAKE, data=quakes())
        frame(a, at=NOW_Q)
        self.assertIsNone(a.state().get("away"))

    def test_levels_by_magnitude(self):
        for mag, level in ((3.2, "minor"), (4.5, "light"), (5.3, "moderate"), (6.1, "strong"), (7.4, "major"),
                           (8.2, "great")):
            a = app(QUAKE, data=quakes(mags=[mag]))
            frame(a, at=NOW_Q)
            self.assertEqual(a.state()["level"], level, mag)

    def test_a_bigger_quake_shakes_the_trace_harder(self):
        def rows(mag):
            a = app(QUAKE, data=quakes(mags=[mag]))
            seen = set()
            for ms in range(0, 8000, 100):
                rgb = frame(a, at=NOW_Q, ms=ms)
                seen |= {y for y in range(11, 24) for x in range(1, 127) if host.at(rgb, x, y) != (0, 0, 0)}
            return len(seen)
        self.assertGreater(rows(7.6), rows(2.6))

    def test_waiting_and_a_quiet_day(self):
        a = app(QUAKE)
        rgb = frame(a, at=NOW_Q)
        self.assertGreater(len([p for p in host.lit(rgb) if p != (0, 0, 0)]), 20)
        v = copy.deepcopy(QUAKES)
        v["features"] = []
        a = app(QUAKE, data=feed("quakes", v))
        frame(a, at=NOW_Q)
        self.assertEqual(a.state()["latest"], "none")

    def test_nothing_touches_the_edges(self):
        a = app(QUAKE, data=quakes(mags=[7.9]))
        for ms in range(0, 12000, 400):
            self.assertEqual(touching_edges(frame(a, at=NOW_Q, ms=ms, place=BOSTON)), [], ms)


# ------------------------------------------------------------------------------------------------------ bonsai life
@need
class BonsaiLifeApp(unittest.TestCase):
    def season(self, month, place=None, settings=None):
        a = app(BONSAI, settings)
        frame(a, month=month, place=place)
        return a.state()["season"]

    def test_the_season_follows_the_date(self):
        got = [self.season(m) for m in (1, 4, 7, 11, 12)]
        self.assertEqual(got, ["winter", "spring", "summer", "fall", "winter"])

    def test_south_of_the_equator_the_seasons_flip(self):
        self.assertEqual(self.season(11, place=HOBART), "spring")
        self.assertEqual(self.season(7, place=HOBART), "winter")

    def test_a_picked_season_stays(self):
        self.assertEqual(self.season(11, settings={"season": "Spring"}), "spring")

    def test_each_season_has_its_colors(self):
        def count(season, test):
            a = app(BONSAI, {"season": season})
            return sum(lit_in(frame(a, ms=ms), 1, 1, 126, 30, test) for ms in (0, 900, 1800))
        self.assertGreater(count("Spring", pink), 30)
        self.assertGreater(count("Fall", orange), 60)
        self.assertGreater(count("Winter", white), 30)
        self.assertGreater(count("Summer", green), count("Winter", green) + 60)

    def test_it_moves(self):
        a = app(BONSAI)
        self.assertNotEqual(frame(a, ms=0, month=11), frame(a, ms=1500, month=11))

    def test_the_pot_is_the_color_picked(self):
        rgb = frame(app(BONSAI, {"pot": "#3C6E8C"}), month=7)
        self.assertGreater(lit_in(rgb, 1, 20, 126, 30, lambda p: p == (0x3C, 0x6E, 0x8C)), 20)

    def test_nothing_touches_the_edges(self):
        for season in ("Spring", "Summer", "Fall", "Winter"):
            a = app(BONSAI, {"season": season})
            for ms in range(0, 10000, 700):
                self.assertEqual(touching_edges(frame(a, ms=ms)), [], (season, ms))


if __name__ == "__main__":
    unittest.main()
