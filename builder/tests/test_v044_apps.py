"""The five 0.4.4 Lua apps run in the board's own Lua host (the dev kit's native runtime) + set DEVKIT to the dev kit's
folder or these tests skip."""
import datetime
import json
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
need = unittest.skipUnless(HAVE, "needs the dev kit's native runtime")


def app(folder, settings=None, data=None, state=None):
    return host.App(str(ROOT / folder), settings, state, data)


def at(place, **kw):
    """a frame's ctx with the board's place, as firmware 0.4.4 gives it (C7991)"""
    return host.ctx(**kw) | {"lat": place[0], "lon": place[1]}


BOSTON, LONDON, NEW_YORK = (42.35, -71.06), (51.51, -0.13), (40.71, -74.01)


def iso(t, off="-05:00"):
    shift = (-1 if off[0] == "-" else 1) * (int(off[1:3]) * 3600 + int(off[4:6]) * 60)
    d = datetime.datetime.fromtimestamp(t + shift, datetime.timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + off


@need
class NudgesApp(unittest.TestCase):
    F = "Lifestyle/Nudges"

    def run_to(self, a, minutes, **kw):
        return a.rt.frame(host.ctx(ms=1000, epoch=BASE + minutes * 60 - 1, **kw))

    def test_water_is_not_due_at_first_and_due_after_the_interval(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, epoch=BASE))
        self.run_to(a, 30)
        self.assertNotEqual(a.state()["water_left"], "now")
        self.run_to(a, 61)
        self.assertEqual(a.state()["water_left"], "now")

    def test_i_drank_starts_the_water_interval_over(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, epoch=BASE))
        self.run_to(a, 61)
        a.press("drank")
        self.run_to(a, 62)
        self.assertNotEqual(a.state()["water_left"], "now")

    def test_i_switched_flips_sitting_and_standing(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, epoch=BASE))
        self.assertFalse(a.state()["standing"])
        a.press("moved")
        self.assertTrue(a.state()["standing"])
        a.press("moved")
        self.assertFalse(a.state()["standing"])

    def test_the_interval_is_the_one_picked(self):
        a = app(self.F, {"water": "30 min", "stand": "20 min"})
        a.rt.frame(host.ctx(ms=0, epoch=BASE))
        self.run_to(a, 31)
        self.assertEqual((a.state()["water_left"], a.state()["stand_left"]), ("now", "now"))

    def test_quiet_hours_hold_every_nudge_and_dim_the_screen(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, epoch=BASE, hour=14))
        loud = host.count_lit(self.run_to(a, 90, hour=14))
        quiet = self.run_to(a, 91, hour=23)
        self.assertEqual((a.state()["water_left"], a.state()["stand_left"]), ("quiet", "quiet"))
        self.assertGreater(loud, 0)
        self.assertTrue(all(max(p) < 120 for p in host.lit(quiet)))

    def test_quiet_hours_cross_midnight_and_off_means_never_quiet(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, epoch=BASE, hour=3))
        self.run_to(a, 5, hour=3)
        self.assertEqual(a.state()["water_left"], "quiet")
        b = app(self.F, {"quiet": "Off"})
        b.rt.frame(host.ctx(ms=0, epoch=BASE, hour=3))
        self.run_to(b, 5, hour=3)
        self.assertNotEqual(b.state()["water_left"], "quiet")

    def test_night_mode_follows_the_boards_night(self):
        a = app(self.F, {"quiet": "Night mode"})
        a.rt.frame(host.ctx(ms=0, epoch=BASE, hour=12, night=True))
        self.assertEqual(a.state()["water_left"], "quiet")

    def test_one_nudge_alone_fills_the_screen_centered(self):
        a = app(self.F, {"show": "Water"})
        rgb = a.rt.frame(host.ctx(ms=0, epoch=BASE))
        xs = [x for y in range(32) for x in range(128) if host.at(rgb, x, y) != (0, 0, 0)]
        self.assertGreater(min(xs), 30)
        self.assertLess(max(xs), 98)

    def test_nothing_touches_the_edges(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, epoch=BASE))
        for minutes in (10, 70):
            rgb = self.run_to(a, minutes)
            edge = [(x, y) for y in range(32) for x in range(128) if (x in (0, 127) or y in (0, 31)) and host.at(rgb, x, y) != (0, 0, 0)]
            self.assertEqual(edge, [])


@need
class GithubGridApp(unittest.TestCase):
    F = "Tools/GitHub Grid"

    def feed(self, levels, total=321):
        return {"grid": {"status": "ok", "value": {"user": "octocat", "total": total, "levels": levels}}}

    def test_every_day_is_a_square_in_its_week_and_row(self):
        levels = "0" * 7 * 53
        levels = levels[:10] + "4" + levels[11:]   # week 1, row 3
        a = app(self.F, {"total": False}, self.feed(levels))
        rgb = a.rt.frame(host.ctx(ms=0))
        self.assertEqual(host.at(rgb, 2 + 1 * 2, 10 + 3 * 3), (125, 255, 160))
        self.assertEqual(host.at(rgb, 2 + 1 * 2, 10 + 2 * 3), (28, 42, 36))

    def test_levels_run_dark_to_bright(self):
        a = app(self.F, {"total": False}, self.feed("01234" * 10))
        rgb = a.rt.frame(host.ctx(ms=0))
        got = [sum(host.at(rgb, 2 + (i // 7) * 2, 10 + (i % 7) * 3)) for i in range(5)]
        self.assertEqual(got, sorted(got))

    def test_the_total_is_kept_for_the_readout_and_drawn(self):
        a = app(self.F, None, self.feed("1" * 371, 1847))
        rgb = a.rt.frame(host.ctx(ms=0))
        self.assertEqual(a.state()["count"], 1847)
        self.assertTrue(any(min(host.at(rgb, x, y)) > 200 for y in range(0, 8) for x in range(90, 127)))
        b = app(self.F, {"total": False}, self.feed("1" * 371, 1847))
        self.assertFalse(any(min(host.at(b.rt.frame(host.ctx(ms=0)), x, y)) > 200 for y in range(0, 8) for x in range(90, 127)))

    def test_the_colors_setting_changes_the_squares(self):
        feed = self.feed("3" * 371)
        green = app(self.F, {"total": False}, feed).rt.frame(host.ctx(ms=0))
        pink = app(self.F, {"total": False, "colors": "Pink"}, feed).rt.frame(host.ctx(ms=0))
        self.assertNotEqual(host.at(green, 2, 10), host.at(pink, 2, 10))

    def test_loading_sweeps_and_an_unknown_user_says_so(self):
        a = app(self.F)
        one, two = a.rt.frame(host.ctx(ms=0)), a.rt.frame(host.ctx(ms=600))
        self.assertNotEqual(one, two)
        b = app(self.F, None, {"grid": {"status": "error", "value": {"error": "user"}}})
        rgb = b.rt.frame(host.ctx(ms=0))
        self.assertTrue(any(host.at(rgb, x, y) == (255, 149, 0) for y in range(0, 8) for x in range(60, 127)))

    def test_today_blinks(self):
        a = app(self.F, {"total": False}, self.feed("1" * 371))
        seen = {host.at(a.rt.frame(host.ctx(ms=ms)), 2 + 52 * 2, 10 + 6 * 3) for ms in (0, 500)}
        self.assertEqual(len(seen), 2)

    def test_source_is_the_mooboard_grid_route(self):
        man = json.load(open(ROOT / self.F / "mooboard.json"))
        self.assertEqual(man["sources"][0]["url"], "https://api.mooboard.co/github/{settings.user}")


@need
class AirAndUvApp(unittest.TestCase):
    F = "Lifestyle/Air and UV"

    def air(self, aqi, uv):
        return {"air": {"status": "ok", "value": {"current": {"us_aqi": aqi, "uv_index": uv}}}}

    def test_levels_have_words_and_a_color_each(self):
        for aqi, word, color in ((42, "GOOD", (52, 199, 89)), (75, "FAIR", (255, 214, 10)), (118, "SENSITIVE", (255, 149, 0)),
                                 (170, "BAD", (255, 59, 48)), (250, "VERY BAD", (175, 82, 222)), (350, "HAZARD", (194, 24, 91))):
            a = app(self.F, None, self.air(aqi, 0))
            rgb = a.rt.frame(host.ctx(ms=0))
            self.assertEqual(a.state()["aqi"], "%d %s" % (aqi, word))
            self.assertIn(color, host.lit(rgb))

    def test_uv_levels(self):
        for uv, word in ((0.4, "LOW"), (4.2, "MODERATE"), (7.0, "HIGH"), (9.5, "VERY HIGH"), (11.4, "EXTREME")):
            a = app(self.F, None, self.air(30, uv))
            a.rt.frame(host.ctx(ms=0))
            self.assertTrue(a.state()["uv"].endswith(word), a.state()["uv"])

    def test_waiting_for_data_draws_a_title(self):
        a = app(self.F)
        self.assertGreater(host.count_lit(a.rt.frame(host.ctx(ms=0))), 20)

    def test_uv_levels_go_by_the_whole_number_shown(self):
        for uv, word in ((2.4, "LOW"), (2.6, "MODERATE"), (5.4, "MODERATE"), (5.5, "HIGH"), (10.6, "EXTREME")):
            a = app(self.F, None, self.air(30, uv))
            a.rt.frame(host.ctx(ms=0))
            self.assertTrue(a.state()["uv"].endswith(word), (uv, a.state()["uv"]))

    def test_the_source_takes_the_boards_place_and_there_is_no_place_setting(self):
        man = json.load(open(ROOT / self.F / "mooboard.json"))
        url = man["sources"][0]["url"]
        self.assertTrue(url.startswith("https://air-quality-api.open-meteo.com/"))
        self.assertIn("latitude={place.lat}", url)
        self.assertIn("longitude={place.lon}", url)
        self.assertEqual(man.get("settings", []), [])
        self.assertEqual(man["minFirmware"], "0.4.4")

    def test_complications_offer_air_quality_and_uv_in_the_apps_own_colors(self):
        man = json.load(open(ROOT / self.F / "mooboard.json"))
        comps = {c["key"]: c for c in man["complications"]}
        self.assertEqual(sorted(comps), ["aqi", "uv"])
        self.assertEqual((comps["aqi"]["path"], comps["uv"]["path"]), ("current.us_aqi", "current.uv_index"))
        # the number alone, so the bar in its level's color fits beside it in a corner + the label names it in two lines
        self.assertEqual([("format" in c, c["icon"]) for c in man["complications"]], [(False, "bar"), (False, "bar")])
        sys.path.insert(0, DEVKIT)
        from mooboard import complication
        if not hasattr(complication, "level_of"):
            self.skipTest("needs a dev kit with complication levels (firmware C7993)")
        for aqi, uv in ((42, 0.4), (75, 2.6), (118, 6.4), (170, 9.5), (250, 11.4), (350, 3.0)):
            data = self.air(aqi, uv)
            a = app(self.F, None, data)
            lit = host.lit(a.rt.frame(host.ctx(ms=0)))
            for index in (0, 1):
                self.assertIn(complication.level_of(man, data, index), lit, (aqi, uv, index))



@need
class SpaceApp(unittest.TestCase):
    F = "Lifestyle/Space"

    def iss(self, lat, lon, ts):
        return {"iss": {"status": "ok", "value": {"latitude": lat, "longitude": lon, "timestamp": ts}}}

    def watch(self, mylat, mylon, lats, lon=0.0):
        a = app(self.F)
        a.rt.frame(at((mylat, mylon), ms=0))   # the station's pass is worked out at the place the last frame had
        for i, lat in enumerate(lats):
            a.data(self.iss(lat, lon, BASE + i * 30))
        return a

    def test_the_first_sample_has_no_heading_so_it_says_so(self):
        a = self.watch(0, 0, [0.0])
        self.assertNotIn("pass", a.state())

    def test_over_you_now_is_overhead(self):
        a = self.watch(5, 0, [4.0, 5.0])
        self.assertEqual(a.state()["next"], "overhead")

    def test_the_next_pass_is_about_one_orbit_later_when_earth_has_turned_away(self):
        a = self.watch(0, -23.3, [-1.0, 0.0], lon=0.0)
        self.assertTrue(80 * 60 < a.state()["pass"] < 95 * 60, a.state())

    def test_going_down_works_too(self):
        a = self.watch(0, -23.3, [1.0, 0.0])
        self.assertTrue(40 * 60 < a.state()["pass"] < 95 * 60 or a.state()["pass"] == 0, a.state())

    def test_a_far_side_of_the_world_waits_longer_than_a_near_one(self):
        near = self.watch(30, 5, [4.0, 5.0]).state()["pass"]
        far = self.watch(30, 170, [4.0, 5.0]).state().get("pass", 10 ** 9)
        self.assertGreater(far, near)

    def test_without_the_boards_place_it_keeps_locating(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0))
        for i, lat in enumerate((4.0, 5.0)):
            a.data(self.iss(lat, 0.0, BASE + i * 30))
        self.assertNotIn("pass", a.state())
        self.assertEqual(a.state()["next"], "waiting for the board's place")

    def test_there_is_no_place_setting(self):
        man = json.load(open(ROOT / self.F / "mooboard.json"))
        self.assertEqual([s["key"] for s in man["settings"]], ["iss", "showers", "eclipses", "moon"])   # moon in 1.2

    def test_the_station_flies_on_an_arc_with_the_earths_center(self):
        """page 1: every lit dot of the earth's edge is 48 from (20, 70) and the station's body 58, frame after frame"""
        import math
        a = app(self.F)
        body, edge = (200, 206, 216), (31, 122, 168)
        seen = set()
        for ms in range(0, 6000, 250):
            rgb = a.rt.frame(host.ctx(ms=ms))
            dots = [(x, y) for y in range(32) for x in range(40) if host.at(rgb, x, y) == body]
            self.assertTrue(dots, ms)
            cx = sum(x for x, _ in dots) / len(dots)
            cy = sum(y for _, y in dots) / len(dots)
            self.assertAlmostEqual(math.hypot(cx - 20, cy - 70), 58, delta=0.8)
            seen.add(round(cx))
            for x, y in ((x, y) for y in range(32) for x in range(40) if host.at(rgb, x, y) == edge):
                self.assertAlmostEqual(math.hypot(x - 20, y - 70), 48, delta=0.8)
        self.assertGreater(len(seen), 15)   # it travels across

    def test_the_led_icon_flies_on_an_arc_with_the_earths_center_too(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("needs Pillow")
        import math
        img = Image.open(ROOT / self.F / "listing/icon-led.png").convert("RGB")
        frames = img.height // 12
        white, blue = (255, 255, 255), (60, 170, 255)
        radii = set()
        for f in range(frames):
            px = lambda x, y: img.getpixel((x, f * 12 + y))
            station = [(x, y) for y in range(12) for x in range(12) if px(x, y) == white]
            if len(station) == 2:   # the body whole on the icon
                cx = sum(x for x, _ in station) / len(station)
                cy = sum(y for _, y in station) / len(station)
                radii.add(math.hypot(cx - 5.5, cy - 18))
            edge = [(x, y) for x in range(12) for y in range(12) if px(x, y) == blue and
                    (y == 0 or px(x, y - 1) == (0, 0, 0)) and y >= 7]
            for x, y in edge:
                self.assertAlmostEqual(math.hypot(x - 5.5, y - 18), 10, delta=0.75, msg=(f, x, y))
        self.assertGreater(len(radii), 4)
        self.assertLess(max(radii) - min(radii), 1.0, sorted(radii))   # one orbit, a dot's rounding apart

    def test_showers_and_eclipses_come_from_the_date(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, year=2026, month=11, day=19))
        self.assertEqual(a.state()["shower"], "LEONIDS -2")
        self.assertEqual(a.state()["eclipse"], "RING SOLAR 79")

    def test_a_shower_just_past_its_peak_is_still_the_next_one(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, year=2026, month=11, day=21))
        self.assertEqual(a.state()["shower"], "LEONIDS -4")
        a.rt.frame(host.ctx(ms=0, year=2026, month=11, day=22))
        self.assertEqual(a.state()["shower"], "GEMINIDS 22")

    def test_the_year_rolls_over_to_the_new_years_first_shower(self):
        a = app(self.F)
        a.rt.frame(host.ctx(ms=0, year=2026, month=12, day=30))
        self.assertTrue(a.state()["shower"].startswith("QUADRANTIDS"))

    def test_each_page_can_be_switched_off(self):
        only = app(self.F, {"iss": False, "showers": False, "eclipses": True})
        a = only.rt.frame(host.ctx(ms=0))
        b = only.rt.frame(host.ctx(ms=7000))
        self.assertGreater(host.count_lit(a), 50)
        self.assertGreater(host.count_lit(b), 50)
        none = app(self.F, {"iss": False, "showers": False, "eclipses": False})
        self.assertGreater(host.count_lit(none.rt.frame(host.ctx(ms=0))), 0)


@need
class TransitApp(unittest.TestCase):
    F = "Tools/Transit"
    FEED = {"feed": "https://example.com/stop"}

    def mbta(self, *rows):
        return {"stop": {"status": "ok", "value": {"data": [
            {"attributes": {"arrival_time": iso(BASE + m * 60), "direction_id": d}, "relationships": {"route": {"data": {"id": r}}}}
            for r, m, d in rows]}}}

    def next_of(self, data, settings=None):
        a = app(self.F, dict(self.FEED, **(settings or {})), data)
        a.rt.frame(host.ctx(ms=0, epoch=BASE))
        return a.state().get("next")

    def test_the_next_arrival_is_the_earliest_whatever_the_order(self):
        self.assertEqual(self.next_of(self.mbta(("Orange", 9, 0), ("Red", 4, 0))), "Red 4 min")

    def test_the_offset_in_the_time_is_honored(self):
        for off in ("-05:00", "-04:00", "+01:00", "+05:30"):
            row = {"attributes": {"arrival_time": iso(BASE + 300, off)}, "relationships": {"route": {"data": {"id": "1"}}}}
            self.assertEqual(self.next_of({"stop": {"status": "ok", "value": {"data": [row]}}}), "1 5 min", off)

    def test_a_terminal_with_only_a_departure_uses_it(self):
        row = {"attributes": {"arrival_time": None, "departure_time": iso(BASE + 180)}, "relationships": {"route": {"data": {"id": "Blue"}}}}
        self.assertEqual(self.next_of({"stop": {"status": "ok", "value": {"data": [row]}}}), "Blue 3 min")

    def test_direction_and_route_filters(self):
        data = self.mbta(("Red", 2, 0), ("Red", 5, 1), ("Orange", 3, 1))
        self.assertEqual(self.next_of(data, {"heading": "Inbound"}), "Orange 3 min")
        self.assertEqual(self.next_of(data, {"heading": "Outbound"}), "Red 2 min")
        self.assertEqual(self.next_of(data, {"route": "Red", "heading": "Inbound"}), "Red 5 min")
        self.assertEqual(self.next_of(data, {"route": "Blue"}), "none")

    def test_the_plain_feed_with_epoch_seconds(self):
        data = {"stop": {"status": "ok", "value": {"arrivals": [{"route": "7", "at": BASE + 600}, {"route": "9", "at": BASE + 120}]}}}
        self.assertEqual(self.next_of(data), "9 2 min")

    def test_past_arrivals_are_dropped(self):
        self.assertEqual(self.next_of(self.mbta(("Red", -10, 0), ("Orange", 6, 0))), "Orange 6 min")

    def test_no_link_and_no_city_near_asks_for_a_stop(self):
        for ctx in (host.ctx(ms=0, epoch=BASE), at(LONDON, ms=0, epoch=BASE), at(NEW_YORK, ms=0, epoch=BASE)):
            a = app(self.F, None, {"boston": {"status": "far"}})
            rgb = a.rt.frame(ctx)
            self.assertGreater(host.count_lit(rgb), 30)
            self.assertEqual(a.state()["next"], "pick your stop")

    def test_near_boston_with_no_link_shows_the_stops_near_the_board(self):
        near = self.mbta(("Red", 4, 0), ("Orange", 7, 1))["stop"]["value"]
        near["data"][0]["relationships"]["stop"] = {"data": {"id": "70079"}}
        near["included"] = [{"id": "70079", "type": "stop", "attributes": {"name": "South Station"}}]
        a = app(self.F, None, {"boston": {"status": "ok", "value": near}})
        rgb = a.rt.frame(at(BOSTON, ms=0, epoch=BASE))
        self.assertEqual(a.state()["next"], "Red 4 min")
        self.assertGreater(host.count_lit(rgb), 150)
        loading = app(self.F, None, {"boston": {"status": "loading"}})
        loading.rt.frame(at(BOSTON, ms=0, epoch=BASE))
        self.assertNotIn("next", loading.state())

    def test_your_own_link_wins_over_the_city_near_you(self):
        a = app(self.F, self.FEED, {"stop": self.mbta(("Blue", 3, 0))["stop"], "boston": self.mbta(("Red", 1, 0))["stop"]})
        a.rt.frame(at(BOSTON, ms=0, epoch=BASE))
        self.assertEqual(a.state()["next"], "Blue 3 min")

    def test_each_city_is_a_source_asked_only_near_it(self):
        man = json.load(open(ROOT / self.F / "mooboard.json"))
        feed = [s for s in man["settings"] if s["key"] == "feed"][0]
        self.assertFalse(feed["default"].startswith("https://"))
        boston = [s for s in man["sources"] if s["key"] == "boston"][0]
        self.assertEqual(boston["near"], "42.36,-71.06,60")
        self.assertTrue(boston["url"].startswith("https://api-v3.mbta.com/predictions?"))
        self.assertIn("filter[latitude]={place.lat}&filter[longitude]={place.lon}", boston["url"])
        lua = (ROOT / self.F / "app.lua").read_text()
        self.assertIn('{name = "BOSTON", source = "boston", lat = 42.36, lon = -71.06, km = 60}', lua)

    def test_two_rows_show_and_a_soon_arrival_flashes(self):
        a = app(self.F, self.FEED, self.mbta(("Red", 1, 0), ("Orange", 7, 0), ("Blue", 9, 0)))
        one = a.rt.frame(host.ctx(ms=0, epoch=BASE))
        two = a.rt.frame(host.ctx(ms=400, epoch=BASE))
        self.assertNotEqual(one, two)
        self.assertGreater(host.count_lit(one), 150)


class LedIconsSwitchAToB(unittest.TestCase):
    """Air and UV and Transit's Home icons play option A's loop, then B's, and repeat (the owner, U909): a clean cut
    between them, each part its option's loop played whole for 2 s or more, inside Home's icon limits, and the still
    icon.png is A's best frame. Each option is known by a dot only it lights."""
    APPS = {   # folder: (A's dot, B's dot, the icon maker's A and B, A's best frame)
        "Lifestyle/Air and UV": ((8, 3, (255, 184, 28)), (5, 8, (205, 210, 215)), ("air_a", "air_b"), 0),   # sun, needle
        "Tools/Transit": ((10, 2, (255, 59, 48)), (4, 1, (60, 170, 255)), ("transit_a", "transit_b"), 5),   # stop, train
    }

    def setUp(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("needs Pillow")
        self.Image = Image

    def strip(self, folder):
        """the listing's icon-led.png as frames of 144 dots, after Home's limits: 12 wide, 2 to 32 frames, 4 KB"""
        path = ROOT / folder / "listing/icon-led.png"
        img = self.Image.open(path).convert("RGB")
        self.assertEqual((img.width, img.height % 12), (12, 0), folder)
        self.assertTrue(2 <= img.height // 12 <= 32, (folder, img.height // 12))
        self.assertLessEqual(path.stat().st_size, 4096, folder)
        return [tuple(img.getpixel((x, f * 12 + y)) for y in range(12) for x in range(12)) for f in range(img.height // 12)]

    def option(self, folder, frame):
        a, b = self.APPS[folder][:2]
        lit = [frame[y * 12 + x] == k for x, y, k in (a, b)]
        self.assertEqual(sum(lit), 1, "%s: a frame is A or B, never both or neither" % folder)
        return "A" if lit[0] else "B"

    def runs(self, folder):
        out = []
        for frame in self.strip(folder):
            key = self.option(folder, frame)
            if out and out[-1][0] == key:
                out[-1][1] += 1
            else:
                out.append([key, 1])
        return [tuple(r) for r in out]

    def test_air_and_uv_plays_wind_and_sun_then_the_gauge(self):
        runs = self.runs("Lifestyle/Air and UV")
        self.assertEqual([k for k, _ in runs], ["A", "B"], runs)   # one cut to B, and the loop's wrap cuts back to A
        self.assertTrue(all(n >= 10 for _, n in runs), runs)   # 2 s or more each at 200 ms a frame

    def test_transit_plays_the_bus_then_the_train(self):
        runs = self.runs("Tools/Transit")
        self.assertEqual([k for k, _ in runs], ["A", "B"], runs)
        self.assertTrue(all(n >= 10 for _, n in runs), runs)

    def test_each_part_is_its_options_own_loop_played_whole(self):
        if not os.path.isfile(os.path.join(HOST, "icons.py")):
            self.skipTest("needs the icon maker (STORE_APPS_HOST)")
        sys.path.insert(0, HOST)
        import icons
        rgb = lambda rows: tuple(icons.ledkit.PAL.get(k, (0, 0, 0)) for row in rows for k in row)
        for folder, (_, _, names, _) in self.APPS.items():
            frames = self.strip(folder)
            a, b = ([rgb(f) for f in getattr(icons, n)()] for n in names)
            cut = next(i for i, f in enumerate(frames) if self.option(folder, f) == "B")
            self.assertEqual((cut % len(a), (len(frames) - cut) % len(b)), (0, 0), folder)
            self.assertEqual(frames, a * (cut // len(a)) + b * ((len(frames) - cut) // len(b)), folder)

    def test_the_still_icon_is_option_as_best_frame(self):
        for folder, (_, _, _, best) in self.APPS.items():
            frame = self.strip(folder)[best]
            self.assertEqual(self.option(folder, frame), "A", folder)
            icon = self.Image.open(ROOT / folder / "icon.png").convert("RGB")
            self.assertEqual(tuple(icon.getpixel((4 + x * 2, 4 + y * 2)) for y in range(12) for x in range(12)), frame,
                             folder)


class StoreRules(unittest.TestCase):
    APPS = ("Lifestyle/Nudges", "Lifestyle/Space", "Lifestyle/Air and UV", "Tools/GitHub Grid", "Tools/Transit")

    def test_each_app_has_its_own_lua_icons_and_listing(self):
        for folder in self.APPS:
            base = ROOT / folder
            for name in ("mooboard.json", "app.lua", "icon.png", "README.md", "listing/icon-led.png", "listing/clip.webp",
                         "listing/shot-1.png", "listing/shot-2.png", "listing/history.json"):
                self.assertTrue((base / name).exists(), "%s/%s" % (folder, name))

    def test_manifests_pass_the_stores_own_checks_and_pin_a_flat_version(self):
        sys.path.insert(0, str(ROOT / "builder"))
        import build
        for folder in self.APPS:
            category, name = folder.split("/")
            row, icon, body, boards, kind, extra = build.load_app(ROOT, category, name)
            version = {"Lifestyle/Space": "1.1.0", "Lifestyle/Air and UV": "1.2.0", "Tools/Transit": "1.2.0"}.get(folder, "1.0.0")
            self.assertEqual((kind, row["uses"], row["version"]), (3, "lua54", version), folder)

    def test_public_text_has_no_em_dash_or_capital_mooboard(self):
        for folder in self.APPS:
            for name in ("mooboard.json", "README.md", "listing/history.json"):
                text = (ROOT / folder / name).read_text(encoding="utf-8")
                self.assertNotIn("—", text, folder)
                self.assertNotIn("Mooboard", text, folder)


if __name__ == "__main__":
    unittest.main()
