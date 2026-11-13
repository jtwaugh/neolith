import os
import tempfile
import tomllib
import unittest

import numpy as np

from pipeline import places
from pipeline.tests.test_pipeline import make_grid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
YEARS = [-6000, -5000]


def site(name, lon, lat, phases, hex_id=1, **more):
    return {"geometry": {"coordinates": [lon, lat]},
            "properties": {"name": name, "hex": hex_id, "occupation": phases, "founding": phases[0][0],
                           "abandoned": phases[-1][1], "sources": ["test"], **more}}


def ctx(g, terrain, sites, residuals=None):
    return {
        "years": YEARS, "half": 500, "grid": g, "terrain": terrain, "area": np.full(len(g), 1000.0),
        "sites": sites,
        "site_xy": np.array([f["geometry"]["coordinates"] for f in sites], dtype=float).reshape(-1, 2),
        "site_on": places.active(sites, YEARS, 500), "residuals": residuals or {}, "survey": {}, "spec": {},
        "rivers": [], "lakes": [], "coasts": [], "audit": [],
    }


class Catalogue(unittest.TestCase):
    def test_repo_catalogue(self):
        cat = places.load_catalogue(os.path.join(ROOT, "data/places/places.toml"))
        # The map's extent, a little inside the configured region box.
        self.assertEqual(places.catalogue_problems(cat, [-16.46, 6.11, 65.95, 75.86]), [])
        self.assertGreater(len(cat), 40)

    def test_problems(self):
        good = {"key": "a_b", "name": "A", "kind": "strait", "box": [0, 0, 1, 1], "why": "x"}
        self.assertEqual(places.catalogue_problems([good]), [])
        errs = places.catalogue_problems([good, {**good, "kind": "volcano", "box": [1, 0, 0, 1]}])
        self.assertEqual(len(errs), 3)                    # key twice, kind, box
        self.assertTrue(places.catalogue_problems([{**good, "box": [0, 0, 9, 1]}], [0, 0, 5, 5]))
        self.assertTrue(places.catalogue_problems([{**good, "key": "Bad Key"}]))


class Geometry(unittest.TestCase):
    def test_km(self):
        self.assertAlmostEqual(float(places.km(0, 0, 1, 0)), 111.19, delta=0.1)
        self.assertEqual(float(places.km_to_box(0.5, 0.5, [0, 0, 1, 1])), 0.0)
        self.assertAlmostEqual(float(places.km_to_box(0.5, 2.0, [0, 0, 1, 1])), 111.19, delta=0.1)

    def test_active(self):
        s = [site("a", 0, 0, [[-6200, -5900]]), site("b", 0, 0, [[-4000, -3000]])]
        self.assertEqual(places.active(s, YEARS, 500).tolist(), [[True, False], [False, False]])

    def test_duplicates(self):
        rows = [{"name": "Sedd Adh-Dhraa II", "lon": 44.71, "lat": 14.35, "hex": 5},
                {"name": "Sedd Adh-Dhra´a II", "lon": 44.71, "lat": 14.35, "hex": 5},
                {"name": "Elsewhere", "lon": 46.0, "lat": 14.0, "hex": 9}]
        d = places.duplicates(rows)
        self.assertEqual([(x["a"], x["b"]) for x in d], [("Sedd Adh-Dhraa II", "Sedd Adh-Dhra´a II")])


class Dossier(unittest.TestCase):
    def setUp(self):
        self.g = make_grid(6, 6)                           # lon -0.5..4.25, lat about -5.6..0.4
        self.s = dict(places.DEFAULTS)
        self.place = {"key": "p", "name": "P", "kind": "strait", "box": [0.5, -3.0, 2.5, -1.0], "why": "w"}

    def test_empty_and_full(self):
        sel = places.hexes_in(self.g, self.place["box"])
        ter = np.full((len(self.g), 2), "Grassland", dtype=object)
        ter[sel[0], 1] = "Water"                           # one hex drowns by the last epoch
        res = {int(self.g.ids[i]): {y: {"sites_expected": "0.1", "missing": "0.5", "outcome": "as expected",
                                        "expected_per_km2": "0.02"} for y in YEARS} for i in sel}
        far = site("far", 4.0, -5.0, [[-6200, -5800]], 30)
        empty = places.dossier(self.place, ctx(self.g, ter, [far], res), self.s)
        self.assertEqual([e["sites_in_box"] for e in empty["epochs"]], [0, 0])
        self.assertEqual(empty["epochs"][0]["drowned_later"], 1)
        self.assertEqual(empty["epochs"][1]["water_hexes"], 1)
        self.assertAlmostEqual(empty["epochs"][0]["missing"], 0.5 * len(sel))
        self.assertIsNone(empty["epochs"][1]["nearest_site_km"])
        self.assertEqual(empty["epochs_without_sites"], 2)

        inside = site("in", 1.5, -2.0, [[-6200, -4800]], 8)
        full = places.dossier(self.place, ctx(self.g, ter, [far, inside], res), self.s)
        self.assertEqual([e["sites_in_box"] for e in full["epochs"]], [1, 1])
        self.assertLess(full["emptiness"], empty["emptiness"])
        self.assertEqual([r["name"] for r in full["sites_in_box"]], ["in"])
        md = places.dossier_md(full, self.s)
        self.assertIn("| in |", md)
        self.assertIn("6,000 BCE", md)

    def test_all_water(self):
        ter = np.full((len(self.g), 2), "Water", dtype=object)
        d = places.dossier(self.place, ctx(self.g, ter, []), self.s)
        self.assertFalse(d["ever_land"])
        self.assertIn("open water", places.dossier_md(d, self.s))


PLAN = '''
[meta]
place = "p"
written = "2026-11-12"
verdict = "research"
confidence = "low"
really_empty = "Yes."
why_empty = ["research_intensity"]
summary = "s"

[[known_site]]
name = "X"
lon = 1.0
lat = -2.0
coordinates = "approximate"
start = -6000
end = -5000
what = "midden"
cite = "A 2000"
url = "https://example.org/a"
checked = true

[[speculate]]
target = "isostyle:pottery"
slices = [-6000]
rule = "r"
confidence = "low"
reasoning = "because"
[[speculate.adjust]]
kind = "near"
point = [1.0, -2.0]
radius_km = 50
value = 0.5
'''


class Plans(unittest.TestCase):
    cat = [{"key": "p", "name": "P", "kind": "strait", "box": [0.5, -3.0, 2.5, -1.0], "why": "w"}]

    def problems(self, text, sources="https://example.org/a"):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.toml")
            with open(path, "w") as f:
                f.write(text)
            return places.plan_problems(path, self.cat, {"pottery"}, YEARS, sources)

    def test_good(self):
        self.assertEqual(self.problems(PLAN), [])

    def test_bad(self):
        tomllib.loads(PLAN)
        for change, word in [
            (("verdict = \"research\"", "verdict = \"dig\""), "verdict"),
            (("[\"research_intensity\"]", "[\"aliens\"]"), "cause"),
            (("lon = 1.0", "lon = 30.0"), "km from"),
            (("start = -6000", "start = -4000"), "start"),
            (("isostyle:pottery", "isostyle:nonsense"), "target"),
            (("slices = [-6000]", "slices = [-6500]"), "slices"),
            (("radius_km = 50\n", ""), "radius_km"),
            (("coordinates = \"approximate\"", "coordinates = \"guess\""), "coordinates"),
            (("place = \"p\"", "place = \"q\""), "file name"),
        ]:
            errs = self.problems(PLAN.replace(*change))
            self.assertTrue(any(word in e for e in errs), f"{change}: {errs}")
        self.assertTrue(any("SOURCES" in e for e in self.problems(PLAN, sources="")))
        self.assertTrue(any("needs at least one" in e for e in self.problems(PLAN.split("[[known_site]]")[0])))

    def test_leave_needs_only_meta(self):
        text = PLAN.split("[[known_site]]")[0].replace("\"research\"", "\"leave\"").replace(
            "[\"research_intensity\"]", "[]")
        self.assertEqual(self.problems(text), [])


if __name__ == "__main__":
    unittest.main()
