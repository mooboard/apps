"""index2.json, icons2.bin, cores.json and the .core packages u652 u653 (cores-spec section 6)"""
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest
import unittest.mock
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402
from test_build import GENERATED, REPO, Tree, manifest, openssl, png, read  # noqa: E402

LATER = "2026-10-19T09:00:00Z"


def core_files(face=b"face bytes"):
    return {"data/OFL.txt": b"SIL Open Font License 1.1\n", "data/face-bold.ttf": face}


def core_json(files=None, **changes):
    files = core_files() if files is None else files
    doc = {"format": 1, "kind": "core", "id": "font-test", "version": "1.0.0", "type": "font",
           "roles": {"SfMedium": "data/face-bold.ttf"},
           "files": {path: hashlib.sha256(body).hexdigest() for path, body in sorted(files.items())}}
    doc.update(changes)
    return {key: value for key, value in doc.items() if value is not None}


def add_core(tree, doc=None, files=None, folder=None):
    files = core_files() if files is None else files
    doc = core_json(files) if doc is None else doc
    base = "Cores/%s/" % (folder or doc["id"])
    tree.write(base + "core.json", json.dumps(doc, indent=2) + "\n")
    for path, body in files.items():
        tree.write(base + path, body)


def uses(tree, cores, minimum="0.4.0-alpha.3"):
    """the tree's one app names these cores"""
    shutil.rmtree(os.path.join(tree.root, "Lifestyle"))
    tree.app("Lifestyle", "Prayer", manifest(cores=cores, minFirmware=minimum, uses="plasma"), {})


def load(out, name):
    return json.loads(read(os.path.join(out, name)))


class FirmwareOrder(unittest.TestCase):
    def test_pw_otas_order_and_a_bare_minimum_lets_in_its_pre_releases(self):
        order = ["0.3.2", "0.4.0", "0.4.0-alpha.1", "0.4.0-alpha.3", "0.4.0-alpha", "0.4.0-beta.1", "0.4.0-beta",
                 "0.4.1"]
        self.assertEqual(sorted(order, key=build.firmware_floor), order)
        for bad in ("0.4", "0.4.0-rc.1", "0.4.0-alpha.0", "0.4.0-alpha.", "v0.4.0"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build.firmware_floor(bad)

    def test_a_manifest_takes_a_pre_release_minimum(self):
        tree = Tree(self)
        shutil.rmtree(os.path.join(tree.root, "Lifestyle"))
        tree.app("Lifestyle", "Prayer", manifest(minFirmware="0.4.0-beta.2", uses="plasma"), {})
        self.assertEqual(load(tree.build(), "index2.json")["apps"][0]["minFirmware"], "0.4.0-beta.2")
        tree.app("Lifestyle", "Prayer", manifest(minFirmware="0.4.0-rc.1", uses="plasma"), {})
        with self.assertRaises(build.Refused) as caught:
            tree.build()
        self.assertIn("minFirmware must be X.Y.Z, X.Y.Z-alpha.N, or X.Y.Z-beta.N", str(caught.exception))


class Index2(unittest.TestCase):
    def tree(self):
        tree = Tree(self)
        tree.app("Games", "Snake", manifest(id="snake", name="Snake", uses="snake", category="Games",
                                            minFirmware="0.3.1"), {})
        game = {"abi": 1, "palette": ["#000000", "#75e8f0"], "step": [["halt"]], "draw": [["const", 0, 0],
                                                                                            ["clear", 0]]}
        tree.app("Games", "Test Game", manifest(id="test-game", name="Test Game", uses="game", category="Games",
                                                minFirmware="0.4.0-alpha.3"), {"game.json": json.dumps(game)})
        tree.app("Games", "Later", manifest(id="later", name="Later", uses="snake", category="Games",
                                            minFirmware="0.4.1"), {})
        tree.app("Games", "Beta", manifest(id="beta", name="Beta", uses="snake", category="Games",
                                           minFirmware="0.4.0-beta"), {})
        return tree

    def test_index2_lists_every_app_and_the_legacy_index_what_old_firmware_runs(self):
        out = self.tree().build()
        legacy, index2 = load(out, "index.json"), load(out, "index2.json")
        self.assertEqual([a["id"] for a in legacy["apps"]], ["prayer", "snake"])
        self.assertEqual([a["id"] for a in index2["apps"]], ["prayer", "beta", "later", "snake", "test-game"])
        self.assertEqual(list(index2), ["format", "stamp", "categories", "apps"])
        self.assertEqual((index2["format"], index2["stamp"], index2["categories"]),
                         (2, GENERATED, legacy["categories"]))
        game = index2["apps"][-1]
        self.assertEqual((game["uses"], game["runtime"], game["minFirmware"]), ("game", "game", "0.4.0-alpha.3"))
        self.assertNotIn("runtime", index2["apps"][0])

    def test_rows_are_the_legacy_rows_with_the_icon_as_a_slice_of_icons2(self):
        out = self.tree().build()
        legacy = {a["id"]: a for a in load(out, "index.json")["apps"]}
        icons = read(os.path.join(out, "icons2.bin"))
        end = 0
        for row in load(out, "index2.json")["apps"]:
            slot = row.pop("icon")
            self.assertEqual(list(slot), ["offset", "length", "sha256"])
            self.assertEqual(slot["offset"], end)   # in row order, nothing between
            body = icons[slot["offset"]:slot["offset"] + slot["length"]]
            self.assertEqual(hashlib.sha256(body).hexdigest(), slot["sha256"])
            end += slot["length"]
            if row["id"] in legacy:
                old = legacy[row["id"]]
                self.assertEqual(base64.b64decode(old.pop("icon")), body)
                self.assertEqual(old, row)
        self.assertEqual(end, len(icons))

    def test_a_lua_app_is_index2s_alone(self):
        tree = Tree(self)
        tree.write("Tools/Custom Tool/mooboard.json", json.dumps(
            {"format": 3, "id": "custom-tool", "name": "Custom Tool", "version": "1.0.0", "by": "Developer",
             "description": "A tool.", "category": "Tools", "runtime": "lua54", "minFirmware": "0.4.0-alpha.3"}))
        tree.write("Tools/Custom Tool/app.lua", "return {frame=function() end}\n")
        out = tree.build()
        row = load(out, "index2.json")["apps"][-1]
        self.assertEqual((row["id"], row["uses"], row["runtime"]), ("custom-tool", "lua54", "lua"))
        self.assertEqual([a["id"] for a in load(out, "index.json")["apps"]], ["prayer"])
        tree.write("Tools/Custom Tool/mooboard.json", read(os.path.join(tree.root, "Tools/Custom Tool/mooboard.json"))
                   .replace(b"0.4.0-alpha.3", b"0.4.0"))
        with self.assertRaises(build.Refused) as caught:
            tree.build()
        self.assertIn("a lua app needs minFirmware 0.4.0-alpha.3", str(caught.exception))

    def test_each_cap_is_refused_before_anything_is_written(self):
        for name, value, words in (("APPS_MAX", 1, "2 apps, over the 1 a board reads"),
                                   ("APPS2_MAX", 4, "5 apps, over the 4 index2.json holds"),
                                   ("INDEX_CAP", 100, "index.json is"), ("INDEX2_CAP", 100, "index2.json is")):
            tree = self.tree()
            out = os.path.join(tree.root, "dist")
            with self.subTest(cap=name), unittest.mock.patch.object(build, name, value), \
                    self.assertRaises(build.Refused) as caught:
                tree.build()
            self.assertIn(words, str(caught.exception))
            self.assertFalse(os.path.exists(out))


class Cores(unittest.TestCase):
    def test_a_core_is_core_json_then_data_sorted_stored_and_listed(self):
        tree = Tree(self)
        add_core(tree)
        out = tree.build()
        body = read(os.path.join(out, "font-test-1.0.0.core"))
        z = zipfile.ZipFile(io.BytesIO(body))
        self.assertEqual(z.namelist(), ["core.json", "data/OFL.txt", "data/face-bold.ttf"])
        self.assertTrue(all(i.compress_type == zipfile.ZIP_STORED and i.date_time == (1980, 1, 1, 0, 0, 0)
                            for i in z.infolist()))
        self.assertEqual(z.read("core.json"), read(os.path.join(tree.root, "Cores/font-test/core.json")))
        listed = load(out, "cores.json")
        self.assertEqual((listed["format"], listed["stamp"]), (1, GENERATED))
        self.assertEqual(listed["cores"], [{"id": "font-test", "version": "1.0.0", "type": "font",
                                            "file": "font-test-1.0.0.core", "size": len(body),
                                            "sha256": hashlib.sha256(body).hexdigest(),
                                            "minFirmware": "0.4.0-alpha.3", "boards": ["s3", "p4"]}])
        self.assertNotIn("font-test", [a["id"] for a in load(out, "index2.json")["apps"]])
        shutil.rmtree(out)
        self.assertEqual(read(os.path.join(tree.build(), "font-test-1.0.0.core")), body)

    def refused(self, edit, words):
        tree = Tree(self)
        edit(tree)
        with self.assertRaises(build.Refused) as caught:
            tree.build()
        self.assertIn(words, str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(tree.root, "dist")))

    def test_core_json_is_held_to_its_files_and_rules(self):
        changed = dict(core_files(), **{"data/face-bold.ttf": b"other"})
        self.refused(lambda t: add_core(t, core_json(), changed), "data/face-bold.ttf does not match core.json")
        self.refused(lambda t: add_core(t, core_json(), dict(core_files(), **{"data/extra.ttf": b"x"})),
                     "must list every data/ file")
        self.refused(lambda t: add_core(t, core_json(version="0.9.0")), "1.0.0 or later")
        self.refused(lambda t: add_core(t, core_json(), folder="font-other"), "id must be its folder's name")
        self.refused(lambda t: add_core(t, core_json(roles=None)), "a font core and only a font core has roles")
        self.refused(lambda t: add_core(t, core_json(type="data")), "a font core and only a font core has roles")
        self.refused(lambda t: add_core(t, core_json(minFirmware="0.4.0")), "minFirmware must be 0.4.0-alpha.3")
        self.refused(lambda t: add_core(t, core_json(icon="x")), "unknown key icon")
        self.refused(lambda t: add_core(t, core_json(id="prayer"), folder="prayer"), "the core prayer has an app's id")
        with unittest.mock.patch.object(build, "CORES_CAP", 100):
            self.refused(add_core, "cores.json is")

    def test_an_app_names_a_core_in_range_on_new_firmware(self):
        tree = Tree(self)
        add_core(tree, core_json(version="1.2.0"))
        uses(tree, {"font-test": "1.1.0"})
        out = tree.build()
        row = load(out, "index2.json")["apps"][0]
        self.assertEqual(row["cores"], {"font-test": "1.1.0"})
        self.assertEqual(load(out, "index.json")["apps"], [])   # older firmware never sees it
        package = zipfile.ZipFile(os.path.join(out, row["file"]))
        self.assertEqual(json.loads(package.read("mooboard.json"))["cores"], {"font-test": "1.1.0"})

    def test_an_app_naming_a_core_out_of_range_or_on_old_firmware_is_refused(self):
        def app(cores, minimum="0.4.0-alpha.3"):
            def edit(tree):
                add_core(tree, core_json(version="1.2.0"))
                uses(tree, cores, minimum)
            return edit
        self.refused(app({"font-test": "1.3.0"}), "cores.json has no font-test from 1.3.0 below 2.0.0")
        self.refused(app({"font-other": "1.0.0"}), "cores.json has no font-other")
        self.refused(app({"font-test": "1.0.0"}, "0.4.0"), "an app with cores needs minFirmware 0.4.0-alpha.3")
        self.refused(app({"font-test": "0.1.0"}), "1.0.0 or later")
        self.refused(app({}), "cores must name 1 to 8 cores")

    def test_the_size_check_counts_the_app_and_its_cores(self):
        tree = Tree(self)
        add_core(tree, files=core_files(b"x" * 4000))
        uses(tree, {"font-test": "1.0.0"})
        size = os.path.getsize(os.path.join(tree.build(), "font-test-1.0.0.core"))
        with unittest.mock.patch.dict(build.BOARD_CAP, s3=size + 100):
            with self.assertRaises(build.Refused) as caught:
                tree.build(previous=None)
        self.assertIn("prayer with its cores is", str(caught.exception))

    def test_previous_keeps_older_versions_and_a_version_out_never_changes(self):
        tree = Tree(self)
        add_core(tree)
        first = tree.build()
        previous = build.read_previous_cores(os.path.join(first, "cores.json"))
        old = previous[0]
        shutil.rmtree(os.path.join(tree.root, "Cores/font-test"))
        files = core_files(b"new face")
        add_core(tree, core_json(files, version="1.1.0"), files)
        out = tree.build(previous_cores=previous)
        rows = load(out, "cores.json")["cores"]
        self.assertEqual([r["version"] for r in rows], ["1.0.0", "1.1.0"])
        self.assertEqual(rows[0], old)
        self.assertTrue(os.path.exists(os.path.join(out, "font-test-1.0.0.core")))   # still listed, still kept
        stale = os.path.join(out, "font-gone-1.0.0.core")
        with open(stale, "wb") as f:
            f.write(b"x")
        tree.build()
        self.assertFalse(os.path.exists(stale))
        shutil.rmtree(os.path.join(tree.root, "Cores/font-test"))
        add_core(tree, core_json(files), files)   # 1.0.0 again with other bytes
        with self.assertRaises(build.Refused) as caught:
            tree.build(previous_cores=previous)
        self.assertIn("font-test 1.0.0 is not the bytes already out", str(caught.exception))

    def test_the_command_reads_the_live_cores_beside_the_live_index(self):
        tree = Tree(self)
        add_core(tree)
        out = os.path.join(tree.root, "dist")
        build.build(tree.root, out, generated=GENERATED)
        with unittest.mock.patch.object(build, "build") as called:
            build.main(["--out", out, "--generated", LATER])
        self.assertEqual([r["id"] for r in called.call_args.kwargs["previous_cores"]], ["font-test"])
        with open(os.path.join(out, "cores.json"), "w") as f:
            f.write("{}")
        with unittest.mock.patch.object(sys, "stderr", io.StringIO()), unittest.mock.patch.object(build, "build"):
            self.assertEqual(build.main(["--out", out, "--generated", LATER]), 1)


class BuiltInCores(unittest.TestCase):
    """the firmware's own cores (pw_apps Cores.h kBuiltInCores) + named with no .core and never in cores.json"""
    def refused(self, edit, words):
        tree = Tree(self)
        edit(tree)
        with self.assertRaises(build.Refused) as caught:
            tree.build()
        self.assertIn(words, str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(tree.root, "dist")))

    def test_the_builder_knows_the_firmwares_two(self):
        self.assertEqual(build.BUILT_IN_CORES, {"font-nunito": "1.0.0", "font-product-sans": "1.0.0"})

    def test_an_app_names_a_built_in_core_with_no_core_file(self):
        tree = Tree(self)
        uses(tree, {"font-nunito": "1.0.0", "font-product-sans": "1.0.0"})
        out = tree.build()
        row = load(out, "index2.json")["apps"][0]
        # the row names them as the manifest does, which the board holds the two to (Package.cpp sameCores)
        self.assertEqual(row["cores"], {"font-nunito": "1.0.0", "font-product-sans": "1.0.0"})
        package = zipfile.ZipFile(os.path.join(out, row["file"]))
        self.assertEqual(json.loads(package.read("mooboard.json"))["cores"], row["cores"])
        self.assertEqual(load(out, "cores.json")["cores"], [])
        self.assertEqual([n for n in os.listdir(out) if n.endswith(".core")], [])
        self.assertEqual(load(out, "index.json")["apps"], [])   # older firmware never sees it

    def test_a_built_in_core_beside_a_downloaded_one_leaves_cores_json_to_the_downloaded(self):
        tree = Tree(self)
        add_core(tree)
        uses(tree, {"font-nunito": "1.0.0", "font-test": "1.0.0"})
        out = tree.build()
        self.assertEqual(load(out, "index2.json")["apps"][0]["cores"], {"font-nunito": "1.0.0", "font-test": "1.0.0"})
        self.assertEqual([r["id"] for r in load(out, "cores.json")["cores"]], ["font-test"])
        self.assertEqual(sorted(n for n in os.listdir(out) if n.endswith(".core")), ["font-test-1.0.0.core"])

    def test_a_built_in_core_adds_nothing_to_the_size_check(self):
        tree = Tree(self)
        uses(tree, {"font-nunito": "1.0.0"})
        out = tree.build()
        size = os.path.getsize(os.path.join(out, load(out, "index2.json")["apps"][0]["file"]))
        with unittest.mock.patch.dict(build.BOARD_CAP, s3=size):
            tree.build(previous=None)

    def test_a_built_in_core_above_the_firmwares_version_is_refused(self):
        for least in ("1.0.1", "1.1.0", "2.0.0"):
            self.refused(lambda tree, least=least: uses(tree, {"font-nunito": least}),
                         "prayer: font-nunito is built into the firmware at 1.0.0, below the %s it names" % least)
        self.refused(lambda tree: uses(tree, {"font-product-sans": "1.2.0"}),
                     "font-product-sans is built into the firmware at 1.0.0")

    def test_an_unknown_core_with_no_core_file_is_still_refused(self):
        self.refused(lambda tree: uses(tree, {"font-nunito": "1.0.0", "font-other": "1.0.0"}),
                     "prayer: cores.json has no font-other from 1.0.0 below 2.0.0")

    def test_a_core_folder_for_a_built_in_id_is_refused(self):
        self.refused(lambda tree: add_core(tree, core_json(id="font-nunito")),
                     "Cores/font-nunito is built into the firmware and has no .core")


class Signed(unittest.TestCase):
    def test_index2_and_cores_are_signed_with_the_catalogs_key(self):
        tree = Tree(self)
        add_core(tree)
        key = os.path.join(tree.root, "throwaway.pem")
        with open(key, "wb") as f:
            f.write(openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout"))
        public = os.path.join(tree.root, "throwaway.pub")
        with open(public, "wb") as f:
            f.write(openssl("ec", "-in", key, "-pubout"))
        out = tree.build(key=key)
        for body, sig in (("index.json", "index.sig"), ("index2.json", "index2.sig"), ("cores.json", "cores.sig")):
            der = os.path.join(tree.root, sig + ".der")
            with open(der, "wb") as f:
                f.write(base64.b64decode(read(os.path.join(out, sig)), validate=True))
            result = subprocess.run(["openssl", "dgst", "-sha256", "-verify", public, "-signature", der],
                                    input=read(os.path.join(out, body)), stdout=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, sig)


class TheRepoCores(unittest.TestCase):
    """the four font cores u652 + made by the firmware's tools/gen_fonts.py --core, each with its licence"""

    def test_the_font_cores_build_and_every_app_is_in_index2(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        build.build(REPO, out, generated=GENERATED)
        rows = load(out, "cores.json")["cores"]
        self.assertEqual([(r["id"], r["version"], r["type"]) for r in rows],
                         [("font-albert-sans", "1.0.0", "font"), ("font-figtree", "1.0.0", "font"),
                          ("font-inter", "1.0.0", "font"), ("font-outfit", "1.0.0", "font")])
        for row in rows:
            names = zipfile.ZipFile(os.path.join(out, row["file"])).namelist()
            self.assertEqual(names[:2], ["core.json", "data/OFL.txt"])
            self.assertTrue(all(n.endswith(".ttf") for n in names[2:]))
            self.assertLessEqual(row["size"], 192 * 1024)
        legacy = [a["id"] for a in load(out, "index.json")["apps"]]
        every = [a["id"] for a in load(out, "index2.json")["apps"]]
        self.assertEqual([a for a in every if a in legacy], legacy)
        self.assertLessEqual(len(legacy), build.APPS_MAX)


if __name__ == "__main__":
    unittest.main()
