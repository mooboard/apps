"""The 0.4.5 personal counters: GitHub Counter and YouTube Subscribers. The store's rules and the LED icons need only
Python and Pillow. The apps themselves run in the board's own Lua host (the dev kit's native runtime) + set DEVKIT and
STORE_APPS_HOST or those tests skip, as test_v045_roadmap.py does. Nothing here calls an API. The feeds are in
builder/tests/counters/: github-user.json and github-search.json recorded from api.github.com on Nov 24 with no token,
github-days.json from api.mooboard.co/github (the feed GitHub Grid reads), and youtube-channel.json shaped from the
YouTube Data API's channels.list reference with the fields the URL asks for (no key was used)."""
import copy
import json
import os
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DEVKIT = os.environ.get("DEVKIT") or str(Path.home() / "mooboard/tmp-store-apps/devkit")
HOST = os.environ.get("STORE_APPS_HOST") or str(Path.home() / "mooboard/tmp-store-apps/tools")
HAVE = os.path.isdir(os.path.join(DEVKIT, "mooboard", "native")) and os.path.isfile(os.path.join(HOST, "host.py"))
if HAVE:
    sys.path.insert(0, HOST)
    import host

need = unittest.skipUnless(HAVE, "needs the dev kit's native runtime")
GITHUB = "Tools/GitHub Counter"
YOUTUBE = "Tools/YouTube Subscribers"
FEEDS = ROOT / "builder/tests/counters"


def recorded(name):
    return json.loads((FEEDS / name).read_text(encoding="utf-8"))


USER, SEARCH, DAYS, CHANNEL = (recorded(n) for n in ("github-user.json", "github-search.json", "github-days.json",
                                                     "youtube-channel.json"))
STALE = (255, 149, 0)
NO_KEY = "configure the source credentials"   # LiveFeeds' error when a header's secret isn't set, so nothing is sent
REFUSED = "data source returned an error"     # a 4xx or 5xx, whose body the board doesn't keep


def ok(value):
    return {"status": "ok", "value": value}


def github_feeds(followers=None, stars=None, levels=None, login="octocat", repo="octocat/Hello-World", user="torvalds"):
    u = copy.deepcopy(USER)
    u["login"] = login
    if followers is not None:
        u["followers"] = followers
    s = copy.deepcopy(SEARCH)
    s["items"][0]["full_name"] = repo
    if stars is not None:
        s["items"][0]["stargazers_count"] = stars
    d = copy.deepcopy(DAYS)
    d["user"] = user
    if levels is not None:
        d["levels"] = levels
    return {"user": ok(u), "repo": ok(s), "days": ok(d)}


def youtube_feeds(subscribers=None, by="id", hidden=False, status="ok", error=""):
    c = copy.deepcopy(CHANNEL)
    stats = c["items"][0]["statistics"]
    if subscribers is not None:
        stats["subscriberCount"] = subscribers
    if hidden:
        stats.pop("subscriberCount")
        stats["hiddenSubscriberCount"] = True
    found, empty = {"status": status, "value": c, "error": error}, {"status": "ok", "value": {}}
    return {"byid": found, "byhandle": empty} if by == "id" else {"byid": empty, "byhandle": found}


def app(folder, feeds=None, settings=None):
    return host.App(str(ROOT / folder), settings, None, feeds)


def frame(a, ms=3000, night=False):
    return a.rt.frame(host.ctx(ms=ms, night=night, hour=23 if night else 14))


def touching_edges(rgb):
    return [(x, y) for y in range(32) for x in range(128)
            if (x in (0, 127) or y in (0, 31)) and host.at(rgb, x, y) != (0, 0, 0)]


def region(rgb, x0, x1):
    return [host.at(rgb, x, y) for y in range(32) for x in range(x0, x1)]


@need
class GitHubCounterApp(unittest.TestCase):
    def count(self, feeds=None, settings=None):
        a = app(GITHUB, feeds, settings)
        frame(a)
        return a.state()["count"]

    def test_followers_come_from_the_users_profile(self):
        self.assertEqual(USER["followers"], 25367)
        self.assertEqual(self.count(github_feeds()), "25,367 followers")

    def test_stars_come_from_the_repo_by_owner_and_name(self):
        self.assertEqual(SEARCH["items"][0]["stargazers_count"], 4046)
        self.assertEqual(self.count(github_feeds(), {"show": "Stars"}), "4,046 stars")
        self.assertEqual(self.count(github_feeds(stars=1), {"show": "Stars"}), "1 star")

    def test_the_repo_name_matches_without_case(self):
        feeds = github_feeds(repo="OctoCat/hello-world")
        self.assertEqual(self.count(feeds, {"show": "Stars"}), "4,046 stars")

    def test_streak_counts_the_days_in_a_row_up_to_today(self):
        settings = {"show": "Streak", "user": "torvalds"}
        self.assertEqual(self.count(github_feeds(levels="0000111"), settings), "3 day streak")
        self.assertEqual(self.count(github_feeds(levels="1102341"), settings), "4 day streak")
        self.assertEqual(self.count(github_feeds(levels="0000001"), settings), "1 day streak")

    def test_a_quiet_today_keeps_yesterdays_streak(self):
        settings = {"show": "Streak", "user": "torvalds"}
        self.assertEqual(self.count(github_feeds(levels="0011110"), settings), "4 day streak")
        self.assertEqual(self.count(github_feeds(levels="1111100"), settings), "0 day streak")

    def test_the_recorded_streak(self):
        levels = DAYS["levels"]
        today = levels[:-1] if levels.endswith("0") else levels
        want = len(today) - len(today.rstrip("1234"))
        self.assertGreater(want, 0)
        self.assertEqual(self.count(github_feeds(), {"show": "Streak", "user": "torvalds"}), "%d day streak" % want)

    def test_another_names_old_count_never_shows(self):
        """a settings change keeps the last value until the next fetch, so each count is checked against its name"""
        self.assertEqual(self.count(github_feeds(), {"user": "rakki"}), "Waiting for GitHub")
        self.assertEqual(self.count(github_feeds(), {"user": "OCTOCAT"}), "25,367 followers")
        self.assertEqual(self.count(github_feeds(), {"show": "Stars", "repo": "octocat/Spoon-Knife"}), "Waiting for GitHub")
        self.assertEqual(self.count(github_feeds(user="octocat"), {"show": "Streak", "user": "torvalds"}),
                         "Waiting for GitHub")

    def test_a_repo_needs_its_owner(self):
        self.assertEqual(self.count(github_feeds(), {"show": "Stars", "repo": "Hello-World"}), "Use owner/name for the repo")

    def test_a_repo_search_finds_nothing(self):
        feeds = github_feeds()
        feeds["repo"] = ok({"total_count": 0, "incomplete_results": False, "items": []})
        self.assertEqual(self.count(feeds, {"show": "Stars"}), "Repo not found")

    def test_a_refused_name_says_check_it(self):
        feeds = github_feeds()
        feeds["user"] = {"status": "error", "error": REFUSED}
        self.assertEqual(self.count(feeds), "Check the username")
        feeds["user"] = {"status": "error", "error": "data source is unreachable"}
        self.assertEqual(self.count(feeds), "Waiting for GitHub")

    def test_before_the_first_answer_it_waits_with_its_name(self):
        a = app(GITHUB)
        rgb = frame(a)
        self.assertEqual(a.state()["count"], "Waiting for GitHub")
        self.assertGreater(host.count_lit(rgb), 20)

    def test_big_counts_shorten(self):
        self.assertEqual(self.count(github_feeds(followers=999999)), "999,999 followers")
        self.assertEqual(self.count(github_feeds(followers=1234567)), "1.23M followers")
        self.assertEqual(self.count(github_feeds(followers=1)), "1 follower")

    def test_the_count_rolls_up_then_holds(self):
        a = app(GITHUB, github_feeds())
        early, settled, later = frame(a, 200), frame(a, 2500), frame(a, 4000)
        self.assertNotEqual(region(early, 32, 126), region(settled, 32, 126))
        self.assertEqual(region(settled, 32, 126), region(later, 32, 126))

    def test_a_failed_refresh_keeps_the_count_with_a_dot(self):
        feeds = github_feeds()
        feeds["user"]["status"] = "error"
        a = app(GITHUB, feeds)
        rgb = frame(a)
        self.assertEqual(a.state()["count"], "25,367 followers")
        self.assertEqual(host.at(rgb, 126, 2), STALE)
        self.assertNotEqual(host.at(frame(app(GITHUB, github_feeds())), 126, 2), STALE)

    def test_each_count_has_its_own_moving_picture(self):
        pictures = []
        for show in ("Followers", "Stars", "Streak"):
            a = app(GITHUB, github_feeds(), {"show": show, "user": "torvalds" if show == "Streak" else "octocat"})
            shots = [region(frame(a, ms), 2, 30) for ms in range(3000, 6000, 250)]
            self.assertGreater(len(set(map(tuple, shots))), 1, show)
            pictures.append(shots[0])
        self.assertEqual(len(set(map(tuple, pictures))), 3)

    def test_night_is_dim(self):
        for show in ("Followers", "Stars", "Streak"):
            for feeds in (github_feeds(), None):
                rgb = frame(app(GITHUB, feeds, {"show": show, "user": "torvalds" if show == "Streak" else "octocat"}),
                            night=True)
                self.assertLessEqual(max((max(p) for p in host.lit(rgb)), default=0), 120, show)

    def test_nothing_touches_the_edges(self):
        cases = [({}, github_feeds()), ({}, github_feeds(followers=88888888)), ({}, github_feeds(followers=888888)),
                 ({"show": "Stars", "repo": "octocat/a-very-long-repository-name"},
                  github_feeds(stars=888888, repo="octocat/a-very-long-repository-name")),
                 ({"show": "Streak", "user": "torvalds"}, github_feeds(levels="1" * 367)),
                 ({}, None), ({"show": "Stars", "repo": "x"}, github_feeds())]
        for settings, feeds in cases:
            a = app(GITHUB, feeds, settings)   # one app a case, so the count rolls up and then holds at its widest
            for ms in range(0, 4000, 100):
                self.assertEqual(touching_edges(frame(a, ms)), [], (settings, ms))


@need
class YouTubeSubscribersApp(unittest.TestCase):
    ID = {"channel": "UC_x5XG1OV2P6uZZ5FSM9Ttw"}

    def count(self, feeds=None, settings=None):
        a = app(YOUTUBE, feeds, dict(self.ID, **(settings or {})))
        frame(a)
        return a.state()["count"]

    def test_subscribers_by_channel_id(self):
        self.assertEqual(self.count(youtube_feeds()), "2.56M subscribers")

    def test_a_handle_finds_the_channel_too(self):
        for handle in ("@GoogleDevelopers", "googledevelopers"):
            self.assertEqual(self.count(youtube_feeds(by="handle"), {"channel": handle}), "2.56M subscribers")

    def test_small_counts_are_exact(self):
        self.assertEqual(self.count(youtube_feeds("12345")), "12,345 subscribers")
        self.assertEqual(self.count(youtube_feeds("1")), "1 subscriber")

    def test_views_and_videos(self):
        self.assertEqual(self.count(youtube_feeds(), {"show": "Views"}), "321M views")
        self.assertEqual(self.count(youtube_feeds(), {"show": "Videos"}), "6,123 videos")

    def test_a_hidden_count_says_hidden(self):
        self.assertEqual(self.count(youtube_feeds(hidden=True)), "Subscribers hidden")

    def test_no_key_asks_for_one(self):
        feeds = {"byid": {"status": "error", "error": NO_KEY}, "byhandle": {"status": "error", "error": NO_KEY}}
        a = app(YOUTUBE, feeds, self.ID)
        rgb = frame(a)
        self.assertEqual(a.state()["count"], "Add your API key")
        self.assertGreater(host.count_lit(rgb), 20)

    def test_a_refused_key_says_check_it(self):
        feeds = {"byid": {"status": "error", "error": REFUSED}, "byhandle": {"status": "error", "error": REFUSED}}
        self.assertEqual(self.count(feeds), "Check your API key")

    def test_an_unknown_channel_says_not_found(self):
        feeds = {"byid": ok({}), "byhandle": ok({})}
        self.assertEqual(self.count(feeds), "Channel not found")

    def test_another_channels_old_count_never_shows(self):
        self.assertEqual(self.count(youtube_feeds(), {"channel": "UCBR8-60-B28hp2BmDPdntcQ"}), "Waiting for YouTube")
        self.assertEqual(self.count(youtube_feeds(by="handle"), {"channel": "@YouTube"}), "Waiting for YouTube")

    def test_before_the_first_answer_it_waits(self):
        self.assertEqual(self.count(None), "Waiting for YouTube")

    def test_the_count_rolls_up_then_holds(self):
        a = app(YOUTUBE, youtube_feeds("12345"), self.ID)
        early, settled, later = frame(a, 200), frame(a, 2500), frame(a, 4000)
        self.assertNotEqual(region(early, 32, 126), region(settled, 32, 126))
        self.assertEqual(region(settled, 32, 126), region(later, 32, 126))

    def test_a_failed_refresh_keeps_the_count_with_a_dot(self):
        a = app(YOUTUBE, youtube_feeds(status="error", error="data source is unreachable"), self.ID)
        rgb = frame(a)
        self.assertEqual(a.state()["count"], "2.56M subscribers")
        self.assertEqual(host.at(rgb, 126, 2), STALE)

    def test_the_play_button_is_red_and_moves(self):
        a = app(YOUTUBE, youtube_feeds(), self.ID)
        shots = [region(frame(a, ms), 2, 30) for ms in range(3000, 6000, 250)]
        self.assertGreater(len(set(map(tuple, shots))), 1)
        reds = [p for p in shots[0] if p[0] > 180 and p[1] < 60 and p[2] < 60]
        self.assertGreater(len(reds), 60)

    def test_night_is_dim(self):
        for feeds in (youtube_feeds(), None):
            rgb = frame(app(YOUTUBE, feeds, self.ID), night=True)
            self.assertLessEqual(max((max(p) for p in host.lit(rgb)), default=0), 120)

    def test_nothing_touches_the_edges(self):
        cases = [youtube_feeds(), youtube_feeds("888888"), youtube_feeds("888000000"), youtube_feeds(hidden=True), None,
                 {"byid": {"status": "error", "error": NO_KEY}, "byhandle": {"status": "error", "error": NO_KEY}}]
        for feeds in cases:
            for show in ("Subscribers", "Views", "Videos"):
                a = app(YOUTUBE, feeds, dict(self.ID, show=show))
                for ms in range(0, 4000, 200):
                    self.assertEqual(touching_edges(frame(a, ms)), [], (show, ms))


class CounterStoreRules(unittest.TestCase):
    APPS = (GITHUB, YOUTUBE)

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
            self.assertEqual((man["format"], man["runtime"], man["category"]), (3, "lua54", "Tools"), folder)
            self.assertEqual((man["version"], man["minFirmware"]), ("1.0.0", "0.4.4"), folder)

    def test_github_reads_public_endpoints_with_no_key_and_minds_the_rate_limit(self):
        man = self.man(GITHUB)
        sources = {s["key"]: s for s in man["sources"]}
        self.assertEqual(sources["user"]["url"], "https://api.github.com/users/{settings.user}")
        self.assertEqual(sources["repo"]["url"],
                         "https://api.github.com/search/repositories?q=repo:{settings.repo}&per_page=1")
        self.assertEqual(sources["days"]["url"], "https://api.mooboard.co/github/{settings.user}")
        self.assertFalse([s for s in man["sources"] if "headers" in s])
        self.assertFalse([s for s in man["settings"] if s["type"] == "secret"])
        # 60 an hour per address for the core API, 10 a minute for search: at most 4 + 2 an hour here
        self.assertGreaterEqual(sources["user"]["refresh"], 900)
        self.assertGreaterEqual(sources["repo"]["refresh"], 1800)
        self.assertGreaterEqual(sources["days"]["refresh"], 3600)   # the worker caches an hour
        self.assertEqual([(s["key"], s["type"], s.get("options")) for s in man["settings"]],
                         [("user", "text", None), ("show", "choice", ["Followers", "Stars", "Streak"]),
                          ("repo", "text", None)])
        self.assertEqual([(c["source"], c["path"]) for c in man["complications"]],
                         [("user", "followers"), ("repo", "items[0].stargazers_count")])

    def test_youtube_sends_the_users_key_only_in_a_header(self):
        man = self.man(YOUTUBE)
        [secret] = [s for s in man["settings"] if s["type"] == "secret"]
        self.assertEqual((secret["key"], secret["label"]), ("key", "API key"))
        self.assertNotIn("default", secret)
        for source in man["sources"]:
            self.assertNotIn("{settings.key}", source["url"])
            self.assertEqual(source["headers"], {"X-goog-api-key": "{settings.key}"})
            self.assertGreaterEqual(source["refresh"], 900)   # 1 unit a call against 10,000 a day
            url = urlsplit(source["url"])
            self.assertEqual((url.scheme, url.netloc, url.path), ("https", "www.googleapis.com", "/youtube/v3/channels"))
            query = parse_qs(url.query)
            self.assertEqual(query["part"], ["snippet,statistics"])
            self.assertEqual(query["fields"], ["items(id,snippet(title,customUrl),statistics)"])
        lookups = [sorted(set(parse_qs(urlsplit(s["url"]).query)) - {"part", "fields"}) for s in man["sources"]]
        self.assertEqual(lookups, [["id"], ["forHandle"]])

    def test_the_recorded_answers_are_the_shapes_the_urls_ask_for(self):
        self.assertEqual((USER["login"], type(USER["followers"])), ("octocat", int))
        self.assertEqual((SEARCH["total_count"], SEARCH["items"][0]["full_name"]), (1, "octocat/Hello-World"))
        self.assertEqual(sorted(DAYS), ["levels", "total", "user"])
        self.assertTrue(re.fullmatch("[0-4]+", DAYS["levels"]))
        self.assertEqual(sorted(CHANNEL["items"][0]), ["id", "snippet", "statistics"])
        self.assertEqual(sorted(CHANNEL["items"][0]["snippet"]), ["customUrl", "title"])
        # each answer fits a board feed (16 KB a body, 7,900 bytes a snapshot)
        for value in (USER, SEARCH, DAYS, CHANNEL):
            self.assertLess(len(json.dumps(value, separators=(",", ":"))), 7000)

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
            self.assertNotIn("settings.key", lua, folder)   # the key stays in the header
            for source in man["sources"]:
                self.assertRegex(lua, r"\b(data|d)\.%s\b|\"%s\"" % (source["key"], source["key"]), folder)
            for key in [c["key"] for c in man.get("controls", []) if c["type"] == "readout"]:
                self.assertIn("state.%s =" % key, lua, folder)

    def test_the_lua_uses_no_string_patterns(self):
        """the board's Lua host leaves out find, match, gmatch, and gsub (pw_runtime's guard list)"""
        for folder in self.APPS:
            lua = (ROOT / folder / "app.lua").read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"[:.](find|match|gmatch|gsub)\(", lua), [], folder)

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


class CounterLedIcons(unittest.TestCase):
    """Home's icon for each: 12 wide, 2 to 32 frames, 4 KB at most, a loop that moves, and icon.png is its first
    frame at 2x"""
    APPS = (GITHUB, YOUTUBE)

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

    def test_github_has_a_gold_star_in_every_frame(self):
        gold = lambda p: p[0] > 200 and p[1] > 150 and p[2] < 90
        self.assertTrue(all(sum(1 for p in f if gold(p)) >= 9 for f in self.frames(GITHUB)))

    def test_youtube_is_a_red_play_button_in_every_frame(self):
        red = lambda p: p[0] > 180 and p[1] < 60 and p[2] < 60
        white = lambda p: min(p) > 200
        for f in self.frames(YOUTUBE):
            self.assertGreaterEqual(sum(1 for p in f if red(p)), 30)
            self.assertGreaterEqual(sum(1 for p in f if white(p)), 4)


if __name__ == "__main__":
    unittest.main()
