"""Water Reminder and Sit Stand (0.4.5): the store's rules and their LED icons need nothing but Pillow, and the apps
themselves run in the board's own Lua host (the dev kit's native runtime) + set DEVKIT and STORE_APPS_HOST or those
tests skip, as test_v044_apps.py does."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DEVKIT = os.environ.get("DEVKIT") or str(Path.home() / "mooboard/tmp-store-apps/devkit")
HOST = os.environ.get("STORE_APPS_HOST") or str(Path.home() / "mooboard/tmp-store-apps/tools")
HAVE = os.path.isdir(os.path.join(DEVKIT, "mooboard", "native")) and os.path.isfile(os.path.join(HOST, "host.py"))
if HAVE:
    sys.path.insert(0, HOST)
    import host

BASE = 1795100000
WATER, SIT = "Lifestyle/Water Reminder", "Lifestyle/Sit Stand"
need = unittest.skipUnless(HAVE, "needs the dev kit's native runtime")


def app(folder, settings=None, state=None):
    return host.App(str(ROOT / folder), settings, state, None)


def frame(a, minutes, hour=14, night=False, ms=1000):
    """a frame `minutes` after BASE, in the afternoon unless said"""
    return a.rt.frame(host.ctx(ms=ms, epoch=BASE + int(minutes * 60), hour=hour, night=night))


def start(folder, settings=None, hour=14):
    a = app(folder, settings)
    frame(a, 0, hour=hour, ms=0)
    return a


def touching_edges(rgb):
    return [(x, y) for y in range(32) for x in range(128)
            if (x in (0, 127) or y in (0, 31)) and host.at(rgb, x, y) != (0, 0, 0)]


def brightest(rgb):
    return max((sum(p) for p in host.lit(rgb)), default=0)


class Reminder:
    """what both apps do: a reminder every N minutes inside the active hours, a done button, a snooze, skipped at
    night, and a gentle or bold look"""
    F, DONE, EVERY = None, None, None

    def test_not_due_at_first_and_due_after_the_interval(self):
        a = start(self.F)
        frame(a, self.EVERY - 2)
        self.assertNotEqual(a.state()["next"], "now")
        frame(a, self.EVERY + 1)
        self.assertEqual(a.state()["next"], "now")

    def test_done_starts_the_interval_over(self):
        a = start(self.F)
        frame(a, self.EVERY + 1)
        a.press(self.DONE)
        frame(a, self.EVERY + 2)
        self.assertNotEqual(a.state()["next"], "now")
        frame(a, 2 * self.EVERY + 2)
        self.assertEqual(a.state()["next"], "now")

    def test_the_interval_is_the_one_picked(self):
        a = start(self.F, {"every": "20 min"})
        frame(a, 21)
        self.assertEqual(a.state()["next"], "now")

    def test_snooze_holds_the_reminder_ten_minutes(self):
        a = start(self.F)
        frame(a, self.EVERY + 1)
        a.press("snooze")
        frame(a, self.EVERY + 2)
        self.assertEqual(a.state()["next"], "snoozed")
        frame(a, self.EVERY + 10)
        self.assertEqual(a.state()["next"], "snoozed")
        frame(a, self.EVERY + 12)
        self.assertEqual(a.state()["next"], "now")

    def test_outside_the_active_hours_it_waits_and_starts_fresh_after(self):
        a = start(self.F, {"hours": "9 am to 5 pm"}, hour=7)
        frame(a, 3 * self.EVERY, hour=7)
        self.assertEqual(a.state()["next"], "off hours")
        frame(a, 3 * self.EVERY + 1, hour=9)
        self.assertNotEqual(a.state()["next"], "now")   # a full interval after the hours begin, not at once
        frame(a, 4 * self.EVERY + 2, hour=9)
        self.assertEqual(a.state()["next"], "now")

    def test_all_day_is_never_off_hours(self):
        a = start(self.F, {"hours": "All day", "night": False}, hour=3)
        frame(a, self.EVERY + 1, hour=3)
        self.assertEqual(a.state()["next"], "now")

    def test_the_boards_night_holds_it_unless_turned_off(self):
        a = start(self.F, {"hours": "All day"})
        frame(a, self.EVERY + 1, night=True)
        self.assertEqual(a.state()["next"], "night")
        b = start(self.F, {"hours": "All day", "night": False})
        frame(b, self.EVERY + 1, night=True)
        self.assertEqual(b.state()["next"], "now")

    def test_resting_dims_the_screen(self):
        a = start(self.F, {"hours": "All day"})
        quiet = frame(a, 5, night=True)
        self.assertGreater(host.count_lit(quiet), 0)
        self.assertTrue(all(max(p) < 120 for p in host.lit(quiet)))

    def test_bold_is_brighter_than_gentle_when_due(self):
        gentle, bold = start(self.F, {"style": "Gentle"}), start(self.F, {"style": "Bold"})
        g, b = frame(gentle, self.EVERY + 1), frame(bold, self.EVERY + 1)
        self.assertGreater(brightest(b), brightest(g))
        self.assertGreater(host.count_lit(b), 0)

    def test_gentle_stays_calm(self):
        a = start(self.F, {"style": "Gentle"})
        for ms in range(0, 4000, 250):
            rgb = frame(a, self.EVERY + 1, ms=ms)
            self.assertTrue(all(max(p) < 230 for p in host.lit(rgb)), ms)

    def test_nothing_touches_the_edges(self):
        for style in ("Gentle", "Bold"):
            a = start(self.F, {"style": style})
            for minutes, ms in ((5, 0), (self.EVERY + 1, 0), (self.EVERY + 1, 900), (self.EVERY + 1, 2400)):
                self.assertEqual(touching_edges(frame(a, minutes, ms=ms)), [], (style, minutes, ms))

    def test_the_readout_counts_down_in_minutes(self):
        a = start(self.F, {"every": "45 min"})
        frame(a, 30)
        self.assertEqual(a.state()["next"], "15 min")


@need
class WaterReminderApp(Reminder, unittest.TestCase):
    F, DONE, EVERY = WATER, "drank", 60

    def test_the_glass_fills_while_the_reminder_shows(self):
        a = start(self.F, {"style": "Bold"})
        blue = lambda rgb: sum(1 for p in host.lit(rgb) if p[2] > p[0] + 40)
        early = blue(frame(a, self.EVERY + 1, ms=200))
        late = blue(frame(a, self.EVERY + 1, ms=2600))
        self.assertGreater(late, early)


@need
class SitStandApp(Reminder, unittest.TestCase):
    F, DONE, EVERY = SIT, "switched", 45

    def test_i_switched_flips_sitting_and_standing(self):
        a = start(self.F)
        self.assertEqual(a.state()["posture"], "sitting")
        a.press("switched")
        frame(a, 1)
        self.assertEqual(a.state()["posture"], "standing")
        a.press("switched")
        frame(a, 2)
        self.assertEqual(a.state()["posture"], "sitting")

    def test_the_figure_stands_up_while_the_reminder_shows(self):
        a = start(self.F, {"style": "Bold"})
        top = lambda rgb: min(y for y in range(32) for x in range(2, 34) if host.at(rgb, x, y) != (0, 0, 0))
        self.assertLess(top(frame(a, self.EVERY + 1, ms=2200)), top(frame(a, self.EVERY + 1, ms=0)))


class ReminderStoreRules(unittest.TestCase):
    APPS = {WATER: "drank", SIT: "switched"}

    def setUp(self):
        sys.path.insert(0, str(ROOT / "builder"))
        import build
        self.build = build

    def test_each_app_has_its_lua_icon_readme_and_history(self):
        for folder in self.APPS:
            for name in ("mooboard.json", "app.lua", "icon.png", "README.md", "listing/icon-led.png",
                         "listing/history.json"):
                self.assertTrue((ROOT / folder / name).exists(), "%s/%s" % (folder, name))

    def test_manifests_pass_the_stores_own_checks(self):
        import json
        for folder in self.APPS:
            man = json.loads((ROOT / folder / "mooboard.json").read_text(encoding="utf-8"))
            self.build.check_settings(man["settings"], folder)
            self.build.check_controls(man["controls"], man["settings"], folder)
            self.assertEqual((man["format"], man["runtime"], man["version"], man["category"]),
                             (3, "lua54", "1.0.0", "Lifestyle"), folder)
            self.assertEqual(man["sources"], [], folder)   # nothing leaves the board

    def test_the_settings_are_every_hours_night_and_style(self):
        import json
        for folder in self.APPS:
            man = json.loads((ROOT / folder / "mooboard.json").read_text(encoding="utf-8"))
            kinds = {s["key"]: s["type"] for s in man["settings"]}
            self.assertEqual(kinds, {"every": "choice", "hours": "choice", "night": "toggle", "style": "choice"}, folder)
            hours = next(s for s in man["settings"] if s["key"] == "hours")
            self.assertIn("All day", hours["options"])
            style = next(s for s in man["settings"] if s["key"] == "style")
            self.assertEqual((style["options"], style["default"]), (["Gentle", "Bold"], "Gentle"), folder)

    def test_done_and_snooze_are_buttons_and_next_is_a_readout(self):
        import json
        for folder, done in self.APPS.items():
            man = json.loads((ROOT / folder / "mooboard.json").read_text(encoding="utf-8"))
            kinds = {c["key"]: c["type"] for c in man["controls"]}
            self.assertEqual((kinds.get(done), kinds.get("snooze"), kinds.get("next")), ("button", "button", "readout"),
                             folder)

    def test_every_option_the_lua_reads_is_in_the_manifest(self):
        import json
        import re
        for folder in self.APPS:
            man = json.loads((ROOT / folder / "mooboard.json").read_text(encoding="utf-8"))
            lua = (ROOT / folder / "app.lua").read_text(encoding="utf-8")
            for s in man["settings"]:
                if s["type"] == "choice" and s["key"] in ("every", "hours"):
                    for option in s["options"]:
                        self.assertIn('"%s"' % option, lua, (folder, option))
            for key in re.findall(r'input\.control == "([a-z_]+)"', lua):
                self.assertIn(key, [c["key"] for c in man["controls"]], folder)

    def test_public_text_has_no_em_dash_capital_mooboard_or_colon_in_a_sentence(self):
        for folder in self.APPS:
            for name in ("mooboard.json", "README.md", "listing/history.json"):
                text = (ROOT / folder / name).read_text(encoding="utf-8")
                self.assertNotIn("—", text, folder)
                self.assertNotIn("Mooboard", text, folder)
            readme = (ROOT / folder / "README.md").read_text(encoding="utf-8")
            prose = [line for line in readme.splitlines() if line and not line.startswith("#")]
            self.assertFalse([line for line in prose if ": " in line], folder)

    def test_history_starts_at_one_point_oh(self):
        import json
        for folder in self.APPS:
            rows = json.loads((ROOT / folder / "listing/history.json").read_text(encoding="utf-8"))
            self.assertEqual(rows[0]["version"], "1.0", folder)
            self.assertTrue(rows[0]["notes"].startswith("First release."), folder)


class ReminderLedIcons(unittest.TestCase):
    """Home's icon for each: 12 wide, 2 to 32 frames, 4 KB at most, a calm loop, and icon.png is its first frame at 2x"""

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
        return [tuple(img.getpixel((x, f * 12 + y)) for y in range(12) for x in range(12)) for f in range(img.height // 12)]

    def test_the_loops_move(self):
        for folder in (WATER, SIT):
            self.assertGreaterEqual(len(set(self.frames(folder))), 4, folder)

    def test_the_still_icon_is_the_loops_first_frame(self):
        for folder in (WATER, SIT):
            icon = self.Image.open(ROOT / folder / "icon.png").convert("RGB")
            self.assertEqual(icon.size, (32, 32), folder)
            got = tuple(icon.getpixel((4 + x * 2, 4 + y * 2)) for y in range(12) for x in range(12))
            self.assertEqual(got, self.frames(folder)[0], folder)

    def test_the_glass_fills_and_the_figure_rises(self):
        water = self.frames(WATER)
        blue = [sum(1 for p in f if p[2] > p[0] + 40) for f in water]
        self.assertGreater(max(blue), blue[0])
        sit = self.frames(SIT)
        top = [min((i // 12 for i, p in enumerate(f) if p != (0, 0, 0)), default=12) for f in sit]
        self.assertLess(min(top), top[0])


if __name__ == "__main__":
    unittest.main()
