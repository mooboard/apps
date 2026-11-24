"""The 0.4.5 roadmap apps: Rain Soon (and Space 1.2's moon and eclipses). The store's rules and the LED icons need
only Python and Pillow. The apps themselves run in the board's own Lua host (the dev kit's native runtime) + set
DEVKIT and STORE_APPS_HOST or those tests skip, as test_v044_apps.py does. Nothing here calls an API: the feeds are
builder/tests/roadmap/open-meteo-15min.json, one response recorded from Open-Meteo on Nov 24, with its slots
rewritten per test."""
import copy
import json
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
RAIN = "Lifestyle/Rain Soon"
SPACE = "Lifestyle/Space"
RECORDED = json.loads((ROOT / "builder/tests/roadmap/open-meteo-15min.json").read_text(encoding="utf-8"))
NOW = RECORDED["current"]["time"] + 237   # when it was recorded, 3 min 57 s into the quarter


def forecast(amounts, snow=None, now=NOW, status="ok"):
    """the recorded response with its 15 minute slots set to amounts (mm, each the sum of the 15 minutes before its
    time) and the first slot the quarter now is in, as Open-Meteo sends them"""
    v = copy.deepcopy(RECORDED)
    t0 = now - now % 900
    snow = list(snow or [0.0] * len(amounts))
    v["minutely_15"].update(time=[t0 + 900 * k for k in range(len(amounts))], precipitation=list(amounts), snowfall=snow)
    v["current"].update(time=t0, precipitation=amounts[0], snowfall=snow[0])
    return {"rain": {"status": status, "value": v}}


# slot 1 is the quarter now is in, and slot 2 starts 11 min from NOW
COMING = [0.0, 0.0, 0.3, 0.6, 0.2, 0.0, 0.0, 0.0]


def rain_app(feed=None, settings=None):
    return host.App(str(ROOT / RAIN), settings, None, feed)


def frame(a, at=NOW, ms=0, night=False, hour=14):
    return a.rt.frame(host.ctx(ms=ms, epoch=at - ms // 1000, night=night, hour=hour))


def touching_edges(rgb):
    return [(x, y) for y in range(32) for x in range(128)
            if (x in (0, 127) or y in (0, 31)) and host.at(rgb, x, y) != (0, 0, 0)]


def blue(p):
    return p[2] > 120 and p[2] > p[0] + 40


@need
class RainSoonApp(unittest.TestCase):
    def test_rain_in_the_next_hour_says_when(self):
        a = rain_app(forecast(COMING))
        frame(a)
        self.assertEqual(a.state()["next"], "Rain in 11 min")

    def test_it_counts_down_between_forecasts(self):
        a = rain_app(forecast(COMING))
        frame(a, NOW + 300)
        self.assertEqual(a.state()["next"], "Rain in 6 min")

    def test_a_dry_hour_is_quiet(self):
        a = rain_app(forecast([0.0] * 8))
        dry = frame(a)
        self.assertEqual(a.state()["next"], "Dry this hour")
        self.assertLessEqual(max(max(p) for p in host.lit(dry)), 130)
        coming = rain_app(forecast(COMING))
        self.assertLess(host.count_lit(dry), host.count_lit(frame(coming)))

    def test_rain_after_the_hour_stays_quiet(self):
        a = rain_app(forecast([0.0] * 6 + [0.8, 0.8]))   # slot 6 starts 71 min from NOW
        frame(a)
        self.assertEqual(a.state()["next"], "Dry this hour")

    def test_rain_already_falling_says_so(self):
        a = rain_app(forecast([0.2, 0.4, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0]))
        frame(a)
        self.assertEqual(a.state()["next"], "Raining now")

    def test_snow_says_snow(self):
        a = rain_app(forecast(COMING, [0.0, 0.0, 0.4, 0.7, 0.1, 0.0, 0.0, 0.0]))
        frame(a)
        self.assertEqual(a.state()["next"], "Snow in 11 min")
        a = rain_app(forecast([0.3] * 8, [0.5] * 8))
        frame(a)
        self.assertEqual(a.state()["next"], "Snowing now")

    def test_steady_rain_lets_a_drizzle_pass(self):
        drizzle = [0.0, 0.0, 0.1, 0.2, 0.1, 0.0, 0.0, 0.0]
        a = rain_app(forecast(drizzle), {"warn": "Steady rain"})
        frame(a)
        self.assertEqual(a.state()["next"], "Dry this hour")
        a = rain_app(forecast(drizzle))
        frame(a)
        self.assertEqual(a.state()["next"], "Rain in 11 min")
        a = rain_app(forecast(COMING), {"warn": "Steady rain"})
        frame(a)
        self.assertEqual(a.state()["next"], "Rain in 26 min")   # 0.3 is a drizzle, and 0.6 in slot 3 is steady

    def test_before_the_first_forecast_it_waits_with_its_name(self):
        a = rain_app()
        rgb = frame(a)
        self.assertEqual(a.state()["next"], "Waiting for the forecast")
        self.assertGreater(host.count_lit(rgb), 20)

    def test_an_old_forecast_waits_instead_of_guessing(self):
        a = rain_app(forecast(COMING, now=NOW - 3 * 3600))
        frame(a)
        self.assertEqual(a.state()["next"], "Waiting for the forecast")

    def test_a_failed_refresh_keeps_the_last_forecast_with_a_dot(self):
        a = rain_app(forecast(COMING, status="error"))
        rgb = frame(a)
        self.assertEqual(a.state()["next"], "Rain in 11 min")
        self.assertEqual(host.at(rgb, 126, 2), (255, 149, 0))

    def test_the_bar_lights_each_quarter_with_rain(self):
        """the next hour as four quarters under the words: the one now is dry, the next three have rain"""
        rgb = frame(rain_app(forecast(COMING)))
        quarters = [sum(1 for x in range(34 + 22 * q, 55 + 22 * q) for y in (22, 23) if blue(host.at(rgb, x, y)))
                    for q in range(4)]
        self.assertEqual(quarters[0], 0, quarters)
        self.assertTrue(all(n >= 30 for n in quarters[1:]), quarters)

    def test_the_drops_fall(self):
        a = rain_app(forecast(COMING))
        drops = lambda rgb: [(x, y) for y in range(16, 31) for x in range(2, 30) if blue(host.at(rgb, x, y))]
        first, later = drops(frame(a, ms=0)), drops(frame(a, ms=400))
        self.assertTrue(first and later)
        self.assertNotEqual(first, later)

    def test_night_is_dim(self):
        for feed in (forecast(COMING), forecast([0.0] * 8), None):
            rgb = frame(rain_app(feed), night=True, hour=23)
            self.assertLessEqual(max((max(p) for p in host.lit(rgb)), default=0), 120)

    def test_nothing_touches_the_edges(self):
        for feed in (forecast(COMING), forecast([0.5] * 8), forecast(COMING, [0.5] * 8), forecast([0.0] * 8), None):
            for ms in range(0, 3000, 100):
                self.assertEqual(touching_edges(frame(rain_app(feed), ms=ms)), [], (feed and feed["rain"]["value"]["minutely_15"], ms))


BOSTON, LONDON, SYDNEY = (42.35, -71.06), (51.51, -0.13), (-33.87, 151.21)


def space(settings=None):
    return host.App(str(ROOT / SPACE), settings, None, None)


def sky(a, epoch, place=None, year=2026, month=11, day=24, ms=0):
    """a frame at 2 pm local on the day, epoch at 19:00 UTC (Boston's 2 pm), so tonight is 8 hours on"""
    return a.rt.frame(host.ctx(ms=ms, epoch=epoch, hour=14, minute=0, year=year, month=month, day=day, place=place))


MOON_ONLY = {"iss": False, "showers": False, "eclipses": False, "moon": True}


@need
class SpaceMoonAndEclipses(unittest.TestCase):
    """Space 1.2: tonight's moon, worked out on the board, and the next eclipse seen from the board's place"""

    def test_tonights_moon_has_its_phase_and_how_much_is_lit(self):
        for epoch, (y, m, d), name, low, high in (
                (1795546800, (2026, 11, 24), "FULL MOON", 97, 100),
                (1796842800, (2026, 12, 9), "NEW MOON", 0, 3),
                (1797447600, (2026, 12, 16), "FIRST QUARTER", 40, 60),
                (1796151600, (2026, 12, 1), "LAST QUARTER", 40, 60),
                (1795201200, (2026, 11, 20), "WAXING GIBBOUS", 70, 90)):
            a = space(MOON_ONLY)
            sky(a, epoch, BOSTON, y, m, d)
            got, lit = a.state()["moon"].rsplit(" ", 1)
            self.assertEqual(got, name, (y, m, d, a.state()["moon"]))
            self.assertTrue(low <= int(lit) <= high, (y, m, d, a.state()["moon"]))

    def test_the_lit_side_is_right_in_the_north_and_left_in_the_south(self):
        lit = lambda rgb, xs: sum(1 for x in xs for y in range(6, 27) if sum(host.at(rgb, x, y)) > 450)
        north = sky(space(MOON_ONLY), 1797447600, BOSTON, 2026, 12, 16)
        south = sky(space(MOON_ONLY), 1797447600, SYDNEY, 2026, 12, 16)
        self.assertGreater(lit(north, range(17, 28)), 3 * max(1, lit(north, range(5, 15))))
        self.assertGreater(lit(south, range(5, 15)), 3 * max(1, lit(south, range(17, 28))))

    def test_the_next_eclipse_is_one_seen_from_the_boards_place(self):
        for place, want in ((LONDON, "TOTAL SOLAR 256"), (BOSTON, "PART LUNAR 419"), (SYDNEY, "PART LUNAR 595")):
            a = space()
            a.rt.frame(host.ctx(ms=0, year=2026, month=11, day=19, place=place))
            self.assertEqual(a.state()["eclipse"], want, place)

    def test_without_the_boards_place_every_eclipse_counts(self):
        a = space()
        a.rt.frame(host.ctx(ms=0, year=2026, month=11, day=19))
        self.assertEqual(a.state()["eclipse"], "RING SOLAR 79")

    def test_the_moon_page_draws_the_moon_and_its_words(self):
        rgb = sky(space(MOON_ONLY), 1795546800, BOSTON)
        disk = sum(1 for x in range(4, 29) for y in range(4, 29) if host.at(rgb, x, y) != (0, 0, 0))
        words = sum(1 for x in range(34, 127) for y in range(1, 31) if host.at(rgb, x, y) != (0, 0, 0))
        self.assertGreater(disk, 300)
        self.assertGreater(words, 60)
        self.assertEqual(touching_edges(rgb), [])

    def test_the_moon_is_a_setting_of_its_own(self):
        man = json.loads((ROOT / SPACE / "mooboard.json").read_text(encoding="utf-8"))
        self.assertEqual(man["version"], "1.2.0")
        self.assertEqual([(s["key"], s["label"], s["default"]) for s in man["settings"]][-1], ("moon", "Tonight's moon", True))
        rows = json.loads((ROOT / SPACE / "listing/history.json").read_text(encoding="utf-8"))
        self.assertEqual((rows[0]["version"], rows[0]["date"]), ("1.2", "2026-11-24"))

    def test_night_and_every_page_stay_off_the_edges(self):
        a = space(MOON_ONLY)
        for epoch, (y, m, d) in ((1795546800, (2026, 11, 24)), (1797447600, (2026, 12, 16)), (1795201200, (2026, 11, 20))):
            for place in (BOSTON, SYDNEY):
                self.assertEqual(touching_edges(sky(a, epoch, place, y, m, d)), [])


class RoadmapStoreRules(unittest.TestCase):
    APPS = (RAIN,)

    def setUp(self):
        sys.path.insert(0, str(ROOT / "builder"))
        import build
        self.build = build

    def man(self, folder):
        return json.loads((ROOT / folder / "mooboard.json").read_text(encoding="utf-8"))

    def test_each_app_has_its_lua_icon_readme_and_history(self):
        for folder in self.APPS:
            for name in ("mooboard.json", "app.lua", "icon.png", "README.md", "listing/icon-led.png",
                         "listing/history.json"):
                self.assertTrue((ROOT / folder / name).exists(), "%s/%s" % (folder, name))

    def test_each_app_passes_the_stores_live_app_checks(self):
        for folder in self.APPS:
            category, name = folder.split("/")
            man = self.build.load_app(str(ROOT), category, name)[0]
            self.assertEqual((man["format"], man["runtime"], man["category"]), (3, "lua54", "Lifestyle"), folder)

    def test_rain_soon_reads_open_meteos_15_minute_forecast_at_the_boards_place(self):
        man = self.man(RAIN)
        self.assertEqual((man["version"], man["minFirmware"]), ("1.0.0", "0.4.4"))
        [source] = man["sources"]
        self.assertEqual(source["key"], "rain")
        url = source["url"]
        self.assertTrue(url.startswith("https://api.open-meteo.com/v1/forecast?"), url)
        for part in ("latitude={place.lat}", "longitude={place.lon}", "minutely_15=precipitation,snowfall",
                     "forecast_minutely_15=8", "timeformat=unixtime"):
            self.assertIn(part, url)
        self.assertGreaterEqual(source["refresh"], 300)   # the forecast changes each quarter hour
        self.assertEqual([(s["key"], s["type"], s["options"], s["default"]) for s in man["settings"]],
                         [("warn", "choice", ["Any rain", "Steady rain"], "Any rain")])
        self.assertEqual([(c["key"], c["type"]) for c in man["controls"]], [("next", "readout")])

    def test_the_recorded_response_is_the_shape_the_url_asks_for(self):
        self.assertEqual(sorted(RECORDED["minutely_15"]), ["precipitation", "snowfall", "time"])
        self.assertEqual(RECORDED["minutely_15_units"]["time"], "unixtime")
        self.assertEqual(RECORDED["minutely_15"]["time"][0], RECORDED["current"]["time"])
        self.assertEqual(RECORDED["current"]["interval"], 900)

    def test_every_option_and_control_the_lua_reads_is_in_the_manifest(self):
        for folder in self.APPS:
            man = self.man(folder)
            lua = (ROOT / folder / "app.lua").read_text(encoding="utf-8")
            for s in man.get("settings", []):
                if s["type"] == "choice":
                    for option in s["options"][1:]:
                        self.assertIn('"%s"' % option, lua, (folder, option))
            for key in re.findall(r"settings\.([a-z_]+)", lua):
                self.assertIn(key, [s["key"] for s in man.get("settings", [])], folder)
            readouts = [c["key"] for c in man.get("controls", []) if c["type"] == "readout"]
            for key in readouts:
                self.assertIn("state.%s =" % key, lua, folder)

    def test_public_text_has_no_em_dash_capital_mooboard_colon_or_semicolon_in_a_sentence(self):
        for folder in self.APPS:
            for name in ("mooboard.json", "README.md", "listing/history.json"):
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

    def test_history_starts_at_one_point_oh_today(self):
        for folder in self.APPS:
            rows = json.loads((ROOT / folder / "listing/history.json").read_text(encoding="utf-8"))
            self.assertEqual((rows[0]["version"], rows[0]["date"]), ("1.0", "2026-11-24"), folder)
            self.assertTrue(rows[0]["notes"].startswith("First release."), folder)


class RoadmapLedIcons(unittest.TestCase):
    """Home's icon for each: 12 wide, 2 to 32 frames, 4 KB at most, a loop that moves, and icon.png is its first
    frame at 2x"""
    APPS = (RAIN,)

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
        for folder in self.APPS:
            self.assertGreaterEqual(len(set(self.frames(folder))), 4, folder)

    def test_the_still_icon_is_the_loops_first_frame(self):
        for folder in self.APPS:
            icon = self.Image.open(ROOT / folder / "icon.png").convert("RGB")
            self.assertEqual(icon.size, (32, 32), folder)
            got = tuple(icon.getpixel((4 + x * 2, 4 + y * 2)) for y in range(12) for x in range(12))
            self.assertEqual(got, self.frames(folder)[0], folder)

    def test_the_rain_falls_under_its_cloud(self):
        frames = self.frames(RAIN)
        drops = [frozenset(i for i, p in enumerate(f) if i // 12 >= 7 and blue(p)) for f in frames]
        self.assertTrue(all(drops), "every frame has drops under the cloud")
        self.assertGreaterEqual(len(set(drops)), 4)


if __name__ == "__main__":
    unittest.main()
