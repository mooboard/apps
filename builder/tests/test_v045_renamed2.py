"""Five of the renamed apps rebuilt with their own drawing (0.4.5, U570's second half): Tide Watch, Rocket Launch Pad,
Oscilloscope, Vintage Cassette Deck, and Uptime. The store's rules and the LED icons need nothing but the builder and
Pillow, and the apps run in the board's own Lua host (the dev kit's native runtime) + set DEVKIT and STORE_APPS_HOST or
those tests skip, as test_v044_apps.py does."""
import datetime
import json
import math
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

TIDE, ROCKET, SCOPE, CASSETTE, UPTIME = ("Lifestyle/Tide Watch", "Lifestyle/Rocket Launch Pad", "Ambiance/Oscilloscope",
                                         "Ambiance/Vintage Cassette Deck", "Tools/Uptime")
APPS = (TIDE, ROCKET, SCOPE, CASSETTE, UPTIME)
LED_APPS = (TIDE, ROCKET, UPTIME)
BASE = 1795100000
EAST = -5 * 3600
need = unittest.skipUnless(HAVE, "needs the dev kit's native runtime")


def app(folder, settings=None, data=None):
    return host.App(str(ROOT / folder), settings, None, data)


def ctx(epoch, ms=0, off=EAST, **kw):
    """a frame's ctx whose local clock is `off` from utc, as a board in that zone gives it"""
    loc = datetime.datetime.fromtimestamp(epoch + ms // 1000 + off, datetime.timezone.utc)
    return host.ctx(ms=ms, epoch=epoch, hour=loc.hour, minute=loc.minute, second=loc.second, year=loc.year,
                    month=loc.month, day=loc.day, **kw)


def utc(t, seconds=False):
    d = datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ" if seconds else "%Y-%m-%dT%H:%M")


def local_label(t, off=EAST, clock24=False):
    d = datetime.datetime.fromtimestamp(t + off, datetime.timezone.utc)
    if clock24:
        return "%d:%02d" % (d.hour, d.minute)
    return "%d:%02d %s" % ((d.hour % 12) or 12, d.minute, "AM" if d.hour < 12 else "PM")


def lit_in(rgb, xs, ys):
    return [(x, y) for y in ys for x in xs if host.at(rgb, x, y) != (0, 0, 0)]


def touching_edges(rgb):
    return [(x, y) for y in range(32) for x in range(128)
            if (x in (0, 127) or y in (0, 31)) and host.at(rgb, x, y) != (0, 0, 0)]


def count(rgb, color, xs=range(128), ys=range(32)):
    return sum(1 for y in ys for x in xs if host.at(rgb, x, y) == color)


def runs(rgb, x):
    """separate lit stretches down one column"""
    n, on = 0, False
    for y in range(32):
        now = host.at(rgb, x, y) != (0, 0, 0)
        if now and not on:
            n += 1
        on = now
    return n


# -- Tide Watch ------------------------------------------------------------------------------------------------------
T0 = (BASE // 86400 - 1) * 86400          # a utc midnight the day before BASE
PERIOD = 12.42 * 3600
HIGH = T0 + 30 * 3600 + 17 * 60            # a high tide a day and a bit in


def tide_feed(level=None, hours=72, status="ok"):
    level = level or (lambda t: 1.4 * math.cos(2 * math.pi * (t - HIGH) / PERIOD))
    times = [utc(T0 + h * 3600) for h in range(hours)]
    return {"tide": {"status": status, "value": {"latitude": 42.375, "longitude": -70.875, "hourly": {
        "time": times, "sea_level_height_msl": [None if level(T0 + h * 3600) is None
                                                else round(level(T0 + h * 3600), 2) for h in range(hours)]}}}}


def near(t, clock24=False):
    return {local_label(t + m * 60, clock24=clock24) for m in range(-3, 4)}


@need
class TideWatchApp(unittest.TestCase):
    def test_rising_shows_the_next_high_at_its_local_time(self):
        a = app(TIDE, None, tide_feed())
        a.rt.frame(ctx(HIGH - 2 * 3600))
        nxt = a.state()["next"]
        self.assertTrue(nxt.startswith("High at "), nxt)
        self.assertIn(nxt[len("High at "):], near(HIGH))

    def test_falling_shows_the_next_low(self):
        a = app(TIDE, None, tide_feed())
        a.rt.frame(ctx(HIGH + 2 * 3600))
        nxt = a.state()["next"]
        self.assertTrue(nxt.startswith("Low at "), nxt)
        self.assertIn(nxt[len("Low at "):], near(HIGH + PERIOD / 2))

    def test_the_24_hour_clock_has_no_am_or_pm(self):
        a = app(TIDE, None, tide_feed())
        a.rt.frame(ctx(HIGH - 2 * 3600) | {"clock24": True})
        self.assertIn(a.state()["next"][len("High at "):], near(HIGH, clock24=True))

    def test_the_water_stands_higher_at_high_tide(self):
        a = app(TIDE, {"curve": False}, tide_feed())
        top = lambda rgb: min(y for x in range(4, 15) for y in range(2, 30) if host.at(rgb, x, y) != (0, 0, 0))
        high = top(a.rt.frame(ctx(HIGH)))
        low = top(a.rt.frame(ctx(int(HIGH + PERIOD / 2))))
        self.assertLess(high, low - 10)

    def test_the_curve_takes_turns_unless_turned_off(self):
        wood = (138, 90, 48)
        a = app(TIDE, None, tide_feed())
        self.assertEqual(host.at(a.rt.frame(ctx(HIGH, ms=0)), 17, 3), wood)
        curve = a.rt.frame(ctx(HIGH, ms=8000))
        self.assertNotEqual(host.at(curve, 17, 3), wood)
        self.assertGreater(len(lit_in(curve, range(100, 126), range(9, 24))), 20)
        b = app(TIDE, {"curve": False}, tide_feed())
        self.assertEqual(host.at(b.rt.frame(ctx(HIGH, ms=8000)), 17, 3), wood)

    def test_no_sea_nearby_says_so(self):
        a = app(TIDE, None, tide_feed(lambda t: None))
        rgb = a.rt.frame(ctx(HIGH))
        self.assertEqual(a.state()["next"], "No tide here")
        self.assertGreater(host.count_lit(rgb), 0)

    def test_a_flat_sea_is_no_tide(self):
        a = app(TIDE, None, tide_feed(lambda t: 0.01))
        a.rt.frame(ctx(HIGH))
        self.assertEqual(a.state()["next"], "No tide here")

    def test_waiting_then_offline(self):
        a = app(TIDE)
        self.assertGreater(host.count_lit(a.rt.frame(ctx(HIGH))), 0)
        self.assertEqual(a.state()["next"], "Waiting for data")
        b = app(TIDE, None, {"tide": {"status": "error"}})
        b.rt.frame(ctx(HIGH))
        self.assertEqual(b.state()["next"], "Offline")

    def test_an_old_series_is_offline_not_a_wrong_tide(self):
        a = app(TIDE, None, tide_feed())
        a.rt.frame(ctx(T0 + 80 * 3600))
        self.assertEqual(a.state()["next"], "Offline")

    def test_a_stale_feed_shows_its_dot(self):
        a = app(TIDE, {"curve": False}, tide_feed(status="error"))
        self.assertEqual(host.at(a.rt.frame(ctx(HIGH - 3600)), 125, 2), (255, 149, 0))

    def test_nothing_touches_the_edges(self):
        a = app(TIDE, None, tide_feed())
        for t in (HIGH - 2 * 3600, HIGH, int(HIGH + PERIOD / 2)):
            for ms in (0, 700, 8000, 9500):
                self.assertEqual(touching_edges(a.rt.frame(ctx(t, ms=ms))), [], (t, ms))


# -- Rocket Launch Pad ------------------------------------------------------------------------------------------------
def launch(name, net, status="Go", where="Cape Canaveral SFS, FL, USA", precision="MIN", mission=None):
    rocket, _, rest = name.partition(" | ")
    return {"id": name, "name": name, "status": {"abbrev": status}, "net": utc(net, seconds=True),
            "net_precision": {"abbrev": precision}, "location": where, "mission": mission or rest}


def launches(*rows, status="ok"):
    return {"launches": {"status": status, "value": {"count": len(rows), "results": list(rows)}}}


GUIANA = "Guiana Space Centre, French Guiana"
DEC1 = 1796137200   # 2026-12-01 15:00 utc


def fleet(now):
    return launches(launch("Soyuz 2.1b | Progress MS-36", now - 2 * 3600, "Success", "Baikonur Cosmodrome, Kazakhstan"),
                    launch("Ariane 64 | Amazon Leo (LE-04)", now + 5 * 3600 + 12 * 60 + 30, where=GUIANA),
                    launch("Falcon 9 Block 5 | USSF-266", now + 2 * 86400 + 4 * 3600 + 60),
                    launch("Electron | Rideshare", DEC1, "TBD", "Rocket Lab LC-1A, New Zealand", "MONTH"))


@need
class RocketLaunchPadApp(unittest.TestCase):
    ROCKET_PARTS = {(216, 222, 230), (200, 206, 216), (255, 90, 60)}

    def test_it_skips_a_launch_already_gone_and_counts_down_to_the_next(self):
        a = app(ROCKET, None, fleet(BASE))
        a.rt.frame(ctx(BASE))
        self.assertEqual(a.state()["next"], "Ariane 64 in 5h 12m")

    def test_united_states_picks_the_first_launch_from_the_us(self):
        a = app(ROCKET, {"where": "United States"}, fleet(BASE))
        a.rt.frame(ctx(BASE))
        self.assertEqual(a.state()["next"], "Falcon 9 Block 5 in 2d 4h")

    def test_under_an_hour_counts_minutes(self):
        a = app(ROCKET, None, launches(launch("Vulcan | Dream Chaser", BASE + 41 * 60 + 5)))
        a.rt.frame(ctx(BASE))
        self.assertEqual(a.state()["next"], "Vulcan in 42 min")

    def test_liftoff_lights_the_engine_and_the_rocket_climbs(self):
        a = app(ROCKET, None, launches(launch("Ariane 64 | Amazon Leo", BASE, where=GUIANA)))
        top = lambda rgb: min(y for y in range(32) for x in range(11, 22) if host.at(rgb, x, y) in self.ROCKET_PARTS)
        early = a.rt.frame(ctx(BASE, ms=1000))
        late = a.rt.frame(ctx(BASE, ms=4000))
        self.assertEqual(a.state()["next"], "Ariane 64 liftoff")
        self.assertLess(top(late), top(early))
        fire = {(255, 242, 168), (255, 184, 28), (255, 90, 31)}
        self.assertGreater(sum(1 for y in range(32) for x in range(14, 19) if host.at(late, x, y) in fire), 0)

    def test_a_launch_that_slipped_past_its_time_moves_on(self):
        a = app(ROCKET, None, launches(launch("Starship | Flight 12", BASE - 300, "TBD"),
                                       launch("Falcon 9 | Starlink", BASE + 3 * 3600)))
        a.rt.frame(ctx(BASE))
        self.assertEqual(a.state()["next"], "Falcon 9 in 3h 0m")

    def test_a_month_only_date_shows_the_day_not_a_countdown(self):
        a = app(ROCKET, None, launches(launch("Electron | Rideshare", DEC1, "TBD", "Rocket Lab LC-1A, New Zealand",
                                              "MONTH")))
        a.rt.frame(ctx(BASE))
        self.assertEqual(a.state()["next"], "Electron on Dec 1")

    def test_waiting_offline_and_no_launches(self):
        a = app(ROCKET)
        self.assertGreater(host.count_lit(a.rt.frame(ctx(BASE))), 0)
        self.assertEqual(a.state()["next"], "Waiting for data")
        b = app(ROCKET, None, {"launches": {"status": "error"}})
        b.rt.frame(ctx(BASE))
        self.assertEqual(b.state()["next"], "Offline")
        c = app(ROCKET, None, launches())
        c.rt.frame(ctx(BASE))
        self.assertEqual(c.state()["next"], "No launches")

    def test_the_rocket_waits_on_its_pad(self):
        a = app(ROCKET, None, fleet(BASE))
        rgb = a.rt.frame(ctx(BASE))
        self.assertGreater(sum(1 for y in range(32) for x in range(11, 22) if host.at(rgb, x, y) in self.ROCKET_PARTS),
                           60)

    def test_nothing_touches_the_edges(self):
        a = app(ROCKET, None, fleet(BASE))
        for ms in (0, 500, 1300):
            self.assertEqual(touching_edges(a.rt.frame(ctx(BASE, ms=ms))), [], ms)


# -- Oscilloscope -----------------------------------------------------------------------------------------------------
def scope(settings, ms):
    a = app(SCOPE, settings)
    return a.rt.frame(host.ctx(ms=ms))


@need
class OscilloscopeApp(unittest.TestCase):
    def test_each_phosphor_tints_the_trace(self):
        for phosphor, channel in (("Green", 1), ("Amber", 0), ("Blue", 2)):
            rgb = scope({"phosphor": phosphor, "grid": False, "trace": "Waves"}, 1000)
            px = [p for p in host.lit(rgb) if p != (0, 0, 0)]
            led = sum(1 for p in px if p[channel] == max(p))
            self.assertGreater(led, 0.9 * len(px), phosphor)

    def test_waves_sweep_left_to_right(self):
        def beam(ms):
            rgb = scope({"grid": False, "trace": "Waves"}, ms)
            best = max(host.lit(rgb), key=sum)
            return min(x for y in range(32) for x in range(128) if host.at(rgb, x, y) == best)
        self.assertLess(beam(200), beam(1000))

    def test_figures_cross_each_column_more_than_once_and_waves_do_not(self):
        figure = scope({"grid": False, "trace": "Figures"}, 3000)
        wave = scope({"grid": False, "trace": "Waves"}, 3000)
        self.assertGreater(sum(1 for x in range(128) if runs(figure, x) >= 2), 30)
        self.assertLess(sum(1 for x in range(128) if runs(wave, x) >= 2), 6)

    def test_both_takes_turns(self):
        first = scope({"grid": False}, 3000)
        later = scope({"grid": False}, 18000)
        self.assertLess(sum(1 for x in range(128) if runs(first, x) >= 2), 6)
        self.assertGreater(sum(1 for x in range(128) if runs(later, x) >= 2), 30)

    def test_the_grid_is_drawn_or_left_off(self):
        self.assertNotEqual(host.at(scope({"trace": "Waves"}, 1000), 16, 4), (0, 0, 0))
        self.assertEqual(host.at(scope({"trace": "Waves", "grid": False}, 1000), 16, 4), (0, 0, 0))

    def test_figures_turn(self):
        self.assertNotEqual(scope({"trace": "Figures"}, 2000), scope({"trace": "Figures"}, 2600))

    def test_a_whole_minute_runs_in_budget_and_off_the_edges(self):
        for trace in ("Both", "Waves", "Figures"):
            a = app(SCOPE, {"trace": trace})
            for ms in range(0, 60000, 350):
                self.assertEqual(touching_edges(a.rt.frame(host.ctx(ms=ms))), [], (trace, ms))


# -- Vintage Cassette Deck --------------------------------------------------------------------------------------------
BROWN = (74, 42, 20)
SIDE = 1800


def deck(settings=None, pos=180, ms=0, cycle=2 * SIDE):
    a = app(CASSETTE, settings)
    epoch = BASE - BASE % cycle + pos
    return a.rt.frame(host.ctx(ms=ms, epoch=epoch - ms // 1000))


@need
class CassetteDeckApp(unittest.TestCase):
    def test_the_reels_turn(self):
        a = app(CASSETTE)
        frames = {}
        for ms in range(0, 1600, 100):
            frames[ms] = a.rt.frame(host.ctx(ms=ms, epoch=BASE))
        hub = lambda rgb: [host.at(rgb, x, y) for y in range(14, 23) for x in range(13, 23)]
        self.assertNotEqual(hub(frames[1000]), hub(frames[1500]))

    def test_side_a_winds_tape_from_left_to_right(self):
        left = lambda rgb: count(rgb, BROWN, range(3, 32))
        right = lambda rgb: count(rgb, BROWN, range(32, 61))
        early, late = deck(pos=180), deck(pos=SIDE - 180)
        self.assertGreater(left(early), left(late))
        self.assertLess(right(early), right(late))

    def test_side_b_winds_it_back(self):
        left = lambda rgb: count(rgb, BROWN, range(3, 32))
        self.assertLess(left(deck(pos=SIDE + 180)), left(deck(pos=2 * SIDE - 180)))

    def test_a_c90_side_lasts_longer(self):
        left = lambda rgb: count(rgb, BROWN, range(3, 32))
        self.assertGreater(left(deck({"tape": "C90"}, pos=1620, cycle=5400)), left(deck({"tape": "C60"}, pos=1620)))

    def test_the_label_is_written(self):
        label = lambda rgb: [host.at(rgb, x, y) for y in range(4, 11) for x in range(19, 57)]
        self.assertNotEqual(label(deck({"label": "WWWW"})), label(deck({"label": "II"})))

    def test_meters_dance_and_can_be_turned_off(self):
        green = (52, 199, 89)
        meters = lambda rgb: count(rgb, green, range(76, 126), range(11, 24))
        self.assertGreater(meters(deck(ms=300)), 0)
        self.assertNotEqual([deck(ms=ms) for ms in (300, 400, 500, 600)][1:], [deck(ms=300)] * 3)
        self.assertEqual(meters(deck({"meters": False}, ms=300)), 0)

    def test_each_shell_has_its_own_color(self):
        shells = {s: host.at(deck({"shell": s}), 4, 14) for s in ("Smoke", "Cream", "Red", "Blue")}
        self.assertEqual(len(set(shells.values())), 4)

    def test_a_whole_minute_runs_in_budget_and_off_the_edges(self):
        for meters in (True, False):
            a = app(CASSETTE, {"meters": meters})
            for ms in range(0, 60000, 350):
                self.assertEqual(touching_edges(a.rt.frame(host.ctx(ms=ms))), [], (meters, ms))


# -- Uptime -----------------------------------------------------------------------------------------------------------
def page(name, indicator="none", at=1):
    return {"status": "ok", "updatedAt": at, "value": {"page": {"name": name}, "status": {"indicator": indicator}}}


NONE = {"three": "none", "four": "none"}


@need
class UptimeApp(unittest.TestCase):
    def test_indicators_become_green_amber_and_red_lights(self):
        a = app(UPTIME, None, {"one": page("GitHub"), "two": page("Cloudflare", "minor"),
                               "three": page("Discord", "major")})
        rgb = a.rt.frame(host.ctx(ms=0))
        up, minor, major = host.at(rgb, 5, 6), host.at(rgb, 5, 16), host.at(rgb, 5, 26)
        self.assertEqual(max(up), up[1])
        self.assertTrue(minor[0] > minor[1] > minor[2], minor)
        self.assertTrue(major[0] > 3 * major[1], major)

    def test_the_worst_one_is_the_readout(self):
        a = app(UPTIME, None, {"one": page("GitHub", "minor"), "two": page("Cloudflare", "major"),
                               "three": page("Discord")})
        a.rt.frame(host.ctx())
        self.assertEqual(a.state()["status"], "Cloudflare has an outage")

    def test_all_up_reads_all_up(self):
        a = app(UPTIME, None, {"one": page("GitHub"), "two": page("Cloudflare"), "three": page("Discord")})
        a.rt.frame(host.ctx())
        self.assertEqual(a.state()["status"], "All up")

    def test_a_failed_check_is_down_and_named_from_its_link(self):
        a = app(UPTIME, {"one": "https://health.myserver.net/ping", "two": "none", **NONE},
                {"one": {"status": "error", "error": "timeout"}})
        a.rt.frame(host.ctx())
        self.assertEqual(a.state()["status"], "Myserver is down")

    def test_a_board_offline_is_not_a_service_down(self):
        a = app(UPTIME, None, {"one": {"status": "offline"}})
        a.rt.frame(host.ctx(online=False))
        self.assertEqual(a.state()["status"], "Board offline")

    def test_two_or_fewer_get_big_rows_and_more_get_small_ones(self):
        rows = app(UPTIME, NONE, {"one": page("GitHub"), "two": page("Cloudflare")}).rt.frame(host.ctx(ms=0))
        grid = app(UPTIME, None, {"one": page("GitHub"), "two": page("Cloudflare"),
                                  "three": page("Discord")}).rt.frame(host.ctx(ms=0))
        self.assertNotEqual(host.at(rows, 8, 8), (0, 0, 0))
        self.assertNotEqual(host.at(rows, 8, 23), (0, 0, 0))
        self.assertEqual(host.at(grid, 8, 8), (0, 0, 0))

    def test_no_services_asks_for_one(self):
        a = app(UPTIME, {"one": "none", "two": "none", **NONE})
        self.assertGreater(host.count_lit(a.rt.frame(host.ctx())), 0)
        self.assertEqual(a.state()["status"], "No services")

    def test_a_fresh_check_sends_out_a_ring(self):
        a = app(UPTIME, NONE, {"one": page("GitHub", at=1), "two": page("Cloudflare", at=1)})
        a.rt.frame(host.ctx(ms=0))
        quiet = a.rt.frame(host.ctx(ms=400))
        a.data({"one": page("GitHub", at=2), "two": page("Cloudflare", at=1)})
        a.rt.frame(host.ctx(ms=500))
        ring = a.rt.frame(host.ctx(ms=800))
        near = lambda rgb: lit_in(rgb, range(12, 15), range(4, 13))
        self.assertEqual(near(quiet), [])
        self.assertNotEqual(near(ring), [])

    def test_nothing_touches_the_edges(self):
        for settings in (None, NONE, {"two": "none", **NONE}):
            a = app(UPTIME, settings, {"one": page("GitHub"), "two": page("Cloudflare", "minor"),
                                       "three": page("Discord", "major"), "four": page("Zoom")})
            for ms in (0, 450, 900):
                self.assertEqual(touching_edges(a.rt.frame(host.ctx(ms=ms))), [], (settings, ms))


# -- the store's rules -------------------------------------------------------------------------------------------------
class RenamedStoreRules(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "builder"))
        import build
        self.build = build

    def manifest(self, folder):
        return json.loads((ROOT / folder / "mooboard.json").read_text(encoding="utf-8"))

    def test_each_app_has_its_lua_icon_readme_and_history(self):
        for folder in APPS:
            for name in ("mooboard.json", "app.lua", "icon.png", "README.md", "listing/history.json"):
                self.assertTrue((ROOT / folder / name).exists(), "%s/%s" % (folder, name))

    def test_each_app_loads_through_the_builder(self):
        for folder in APPS:
            category, name = folder.split("/")
            row = self.build.load_app(str(ROOT), category, name)[0]
            self.assertEqual((row["format"], row["runtime"], row["version"], row["minFirmware"]),
                             (3, "lua54", "1.0.0", "0.4.4"), folder)

    def test_home_icons_only_where_home_shows_them(self):
        for folder in APPS:
            led = (ROOT / folder / "listing/icon-led.png").exists()
            self.assertEqual(led, folder in LED_APPS, folder)

    def test_every_option_the_lua_reads_is_in_the_manifest(self):
        for folder in APPS:
            lua = (ROOT / folder / "app.lua").read_text(encoding="utf-8")
            for s in self.manifest(folder).get("settings", []):
                self.assertTrue("settings." + s["key"] in lua or ('"%s"' % s["key"] in lua and "settings[" in lua),
                                (folder, s["key"]))
                if s["type"] == "choice":
                    for option in s["options"][1:]:
                        self.assertTrue('"%s"' % option in lua or option + " =" in lua, (folder, option))
            for c in self.manifest(folder).get("controls", []):
                self.assertIn("state.%s =" % c["key"], lua, folder)

    def test_sources_use_https_and_no_keys(self):
        for folder in APPS:
            for s in self.manifest(folder).get("sources", []):
                self.assertTrue(s["url"].startswith("https://") or s["url"].startswith("{settings."), folder)
                self.assertNotIn("headers", s, folder)

    def test_public_text_follows_the_house_style(self):
        for folder in APPS:
            for name in ("mooboard.json", "README.md", "listing/history.json"):
                text = (ROOT / folder / name).read_text(encoding="utf-8")
                self.assertNotIn("—", text, folder)
                self.assertNotIn("Mooboard", text, folder)
                self.assertNotIn(";", text.replace("&", ""), folder)
            readme = (ROOT / folder / "README.md").read_text(encoding="utf-8")
            prose = [line for line in readme.splitlines() if line and not line.startswith("#")]
            self.assertFalse([line for line in prose if ": " in line], folder)
            for word in ("colour", "favourite", "centre", "metre"):
                self.assertNotIn(word, readme.lower(), folder)

    def test_history_starts_at_one_point_oh(self):
        for folder in APPS:
            rows = json.loads((ROOT / folder / "listing/history.json").read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1, folder)
            self.assertEqual(rows[0]["version"], "1.0", folder)
            self.assertTrue(rows[0]["notes"].startswith("First release."), folder)


class RenamedIcons(unittest.TestCase):
    """Home's LED icon for the three with a Home tile (12 wide, 2 to 32 frames, 4 KB at most, a loop that moves, and
    icon.png its first frame at 2x), and a drawn 32 x 32 icon for the two Ambiance apps"""

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
        for folder in LED_APPS:
            self.assertGreaterEqual(len(set(self.frames(folder))), 4, folder)

    def test_the_still_icon_is_the_loops_first_frame(self):
        for folder in LED_APPS:
            icon = self.Image.open(ROOT / folder / "icon.png").convert("RGB")
            self.assertEqual(icon.size, (32, 32), folder)
            got = tuple(icon.getpixel((4 + x * 2, 4 + y * 2)) for y in range(12) for x in range(12))
            self.assertEqual(got, self.frames(folder)[0], folder)

    def test_the_rocket_lifts_off_and_the_tide_moves(self):
        rocket = self.frames(ROCKET)
        top = [min((i // 12 for i, p in enumerate(f) if p == (216, 222, 230)), default=12) for f in rocket]
        self.assertLess(min(top), top[0])
        tide = self.frames(TIDE)
        water = [sum(1 for p in f if p[2] > p[0] + 40) for f in tide]
        self.assertGreater(max(water), min(water))

    def test_the_ambiance_icons_are_drawn(self):
        seen = set()
        for folder in (SCOPE, CASSETTE):
            icon = self.Image.open(ROOT / folder / "icon.png").convert("RGB")
            self.assertEqual(icon.size, (32, 32), folder)
            colors = {icon.getpixel((x, y)) for y in range(32) for x in range(32)}
            self.assertGreaterEqual(len(colors), 4, folder)
            seen.add(icon.tobytes())
        self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main()
