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

    def test_the_source_takes_the_places_coordinates(self):
        man = json.load(open(ROOT / self.F / "mooboard.json"))
        url = man["sources"][0]["url"]
        self.assertTrue(url.startswith("https://air-quality-api.open-meteo.com/"))
        self.assertIn("latitude={settings.lat}", url)
        self.assertIn("longitude={settings.lon}", url)


@need
class SpaceApp(unittest.TestCase):
    F = "Lifestyle/Space"

    def iss(self, lat, lon, ts):
        return {"iss": {"status": "ok", "value": {"latitude": lat, "longitude": lon, "timestamp": ts}}}

    def watch(self, mylat, mylon, lats, lon=0.0):
        a = app(self.F, {"lat": str(mylat), "lon": str(mylon)})
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

    def test_no_feed_asks_for_one_and_draws_without_reading_data(self):
        a = app(self.F)
        rgb = a.rt.frame(host.ctx(ms=0, epoch=BASE))
        self.assertGreater(host.count_lit(rgb), 30)
        self.assertNotIn("next", a.state())

    def test_the_default_feed_is_empty_until_the_owner_picks_a_city(self):
        man = json.load(open(ROOT / self.F / "mooboard.json"))
        feed = [s for s in man["settings"] if s["key"] == "feed"][0]
        self.assertFalse(feed["default"].startswith("https://"))

    def test_two_rows_show_and_a_soon_arrival_flashes(self):
        a = app(self.F, self.FEED, self.mbta(("Red", 1, 0), ("Orange", 7, 0), ("Blue", 9, 0)))
        one = a.rt.frame(host.ctx(ms=0, epoch=BASE))
        two = a.rt.frame(host.ctx(ms=400, epoch=BASE))
        self.assertNotEqual(one, two)
        self.assertGreater(host.count_lit(one), 150)


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
            self.assertEqual((kind, row["uses"], row["version"]), (3, "lua54", "1.0.0"))

    def test_public_text_has_no_em_dash_or_capital_mooboard(self):
        for folder in self.APPS:
            for name in ("mooboard.json", "README.md", "listing/history.json"):
                text = (ROOT / folder / name).read_text(encoding="utf-8")
                self.assertNotIn("—", text, folder)
                self.assertNotIn("Mooboard", text, folder)


if __name__ == "__main__":
    unittest.main()
