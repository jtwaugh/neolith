"""Unit tests for the evidence layers: python -m unittest discover -s isostyle/tests -t ."""
import os
import tempfile
import unittest

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from isostyle import landcover, layers, people, pollen, sources, surface

REGISTRY = layers.Registry.load("data/isostyle/layers.toml")


class SiteTypes(unittest.TestCase):
    def hits(self, lid, texts):
        rx = REGISTRY[lid]["site_type_re"]
        return [bool(rx.search(t)) for t in texts]

    def test_megaliths_exclude_non_megalithic(self):
        self.assertEqual(self.hits("megalithic_tombs", ["passage grave", "dolmen in rou tumulus",
                                                        "non-megalithic chambered grave", "settlement"]),
                         [True, True, False, False])

    def test_houses_exclude_dead_house(self):
        self.assertEqual(self.hits("houses", ["neolithic house", "settlement (house)", "dead house", "longhouse"]),
                         [True, True, False, True])

    def test_enclosures(self):
        self.assertEqual(self.hits("enclosures", ["causewayed enclosure", "henge monument", "ring-ditch", "cave"]),
                         [True, True, True, False])


class Livestock(unittest.TestCase):
    def phase(self, rows):
        df = pd.DataFrame(rows, columns=["key", "taxon", "n", "isdom", "uncertain"])
        df = df.assign(site="s", lon=0.0, lat=0.0, tpq=-6000.0, taq=-5500.0)
        g = sources._livestock_phase(df, ["site", "lon", "lat", "tpq", "taq"], "n", "isdom", 50)
        return dict(zip(g["key"], g["present"]))

    def test_domestic_present(self):
        self.assertEqual(self.phase([("a", "Bos taurus", 10, True, False), ("a", "Cervus elaphus", 90, False, False)]),
                         {"a": 1})

    def test_absent_needs_enough_bones(self):
        out = self.phase([("big", "Cervus elaphus", 60, False, False), ("small", "Cervus elaphus", 20, False, False)])
        self.assertEqual(out, {"big": 0})

    def test_uncertain_livestock_blocks_absence(self):
        self.assertEqual(self.phase([("a", "Ovis/Capra", 5, False, True), ("a", "Cervus elaphus", 90, False, False)]), {})


class Cereals(unittest.TestCase):
    def test_present_and_absent_phases(self):
        rows = pd.DataFrame({
            "site_name": ["A", "A"] + ["B"] * 5 + ["C"], "phase_code": ["A1", "A1"] + ["B1"] * 5 + ["C1"],
            "latitude": 35.0, "longitude": 38.0,
            "age_start": [9500, 9500] + [12000] * 5 + [9000], "age_end": [9300, 9300] + [11800] * 5 + [8800],
            "n": [3, 5, 7, 1, 1, 1, 1, 2], "taxon": ["einkorn", "lentil", "t1", "t2", "t3", "t4", "t5", "flax"],
            "founder_crop": ["einkorn wheat", None, None, None, None, None, None, "flax"]})
        with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as f:
            rows.to_csv(f, sep="\t", index=False)
        try:
            out = sources.swasia_flora(f.name)
        finally:
            os.unlink(f.name)
        got = dict(zip(out["site"], out["present"]))
        self.assertEqual(got, {"A": 1, "B": 0})          # C: one taxon is too few to call an absence
        a = out[out["site"] == "A"].iloc[0]
        self.assertEqual((a["tpq"], a["taq"]), (1950 - 9500, 1950 - 9300))


class Cores(unittest.TestCase):
    def test_absent_only_where_counted(self):
        grid = gpd.GeoDataFrame({"cell": [1], "lon": [10.0], "lat": [50.0]}, geometry=[box(0, 40, 20, 60)], crs="EPSG:4326")
        years = np.array([-6000, -5000])
        edges = np.column_stack([years - 500, years + 500])
        lv = pd.DataFrame({"datasetid": [1, 1, 2, 3], "site": "x", "lon": 10.0, "lat": 50.0,
                           "age_bp": [7950, 7000, 7950, 6950], "pollen_sum": 300,
                           "cereal": [0, 4, 0, 0], "dung": [np.nan, np.nan, 2, np.nan], "database": "EPD"})
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "pollen"))
            lv.to_csv(os.path.join(d, "pollen", "levels.csv.gz"), index=False)
            cfg = {"output": {"build_dir": d}}
            u, W = pollen.units(cfg, grid, years, edges, REGISTRY, {}, log=lambda m: None)
        got = {(r.datasetid, r.slice): (r.y_cereal_pollen, r.y_dung_spores) for r in u.itertuples()}
        self.assertEqual(got[(1, 0)][0], 0.0)          # counted, no cereal: absent
        self.assertEqual(got[(1, 1)][0], 1.0)
        self.assertEqual(got[(2, 0)][1], 1.0)          # dung counted there
        self.assertTrue(np.isnan(got[(3, 1)][1]))      # dung not counted: unknown, not absent
        self.assertTrue(np.allclose(W.sum(axis=1), 1))


class Haplogroups(unittest.TestCase):
    def test_prefix_and_exclude(self):
        hits = people.in_clade(["H1a", "HV0", "H", "K1a"], ["H"], exclude=["HV"])
        self.assertEqual(hits.tolist(), [True, False, True, False])

    def test_normal_mass_sums_to_inside_share(self):
        edges = np.array([[-6500, -5500], [-5500, -4500]])
        m = people.normal_mass(np.array([-5500.0]), np.array([50.0]), edges)
        self.assertAlmostEqual(m.sum(), 1.0, places=4)
        self.assertAlmostEqual(m[0, 0], 0.5, places=4)


class Surfaces(unittest.TestCase):
    def test_constant_value_gives_constant_surface(self):
        rng = np.random.default_rng(1)
        lon, lat = rng.uniform(5, 15, 300), rng.uniform(45, 55, 300)
        W = np.zeros((300, 2))
        W[:, 0] = 1
        y = np.full(300, 0.7)
        gl, ga = np.array([10.0, 11.0]), np.array([50.0, 51.0])
        res = surface.surfaces(gl, ga, lon, lat, W, y, np.zeros(300, bool), W, lon, lat, 100, 2.5, 1.0, 1.2, 5, 0)
        self.assertTrue(np.allclose(res["f"][:, 0], 0.7))


class LandCover(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(landcover.window_bounds(1), (0, 100))
        self.assertEqual(landcover.window_bounds(4), (700, 1200))
        self.assertEqual(landcover.window_bounds(25), (11200, 11700))


if __name__ == "__main__":
    unittest.main()


class SourceList(unittest.TestCase):
    def test_every_layer_reader_is_listed(self):
        """Each dataset reader in sources.py is wired into sources.load."""
        import inspect
        src = inspect.getsource(sources.load)
        for name in ("evershed", "rigaud2018", "dolbunova", "windler", "tsirintoulaki", "bda", "medafricarbon", "rotunno",
                     "dobsiss", "defc", "swasia_flora", "ademnes_fauna", "opencontext_eol", "phelps_fauna", "rondels",
                     "euroevol_botany", "euroevol_fauna"):
            self.assertIn(f" {name},", src, f"{name} is not listed in sources.load")


class LabelRules(unittest.TestCase):
    def test_stage_presence_means_absence_in_listed_countries(self):
        from isostyle.observe import _label_vote
        rule = {"present_cultures": ["ubaid"], "absent_cultures": [], "present_stages": ["neolithic"],
                "absent_stages": ["mesolithic"], "present_stages_absent_in_countries": ["Saudi Arabia"]}
        self.assertEqual(_label_vote(rule, [], ["neolithic"], -5000, "Syria"), 1.0)
        self.assertEqual(_label_vote(rule, [], ["neolithic"], -5000, "Saudi Arabia"), 0.0)
        self.assertEqual(_label_vote(rule, ["ubaid"], ["neolithic"], -5000, "Saudi Arabia"), 1.0)
        self.assertEqual(_label_vote(rule, [], ["mesolithic"], -8000, "Saudi Arabia"), 0.0)
        rule["present_stages"] = ["neolithic", "bronze_age"]
        rule["present_stages_absent_in_countries_stages"] = ["neolithic"]
        self.assertEqual(_label_vote(rule, [], ["bronze_age"], -2500, "Saudi Arabia"), 1.0)


class Speculative(unittest.TestCase):
    def test_fill_order_and_blend(self):
        from isostyle import speculative
        # A line of 8 cells: 0-1 observed, 2-6 judged, 7 neither.
        nb = [[k for k in (i - 1, i + 1) if 0 <= k < 8] for i in range(8)]
        obs = np.array([1.0, 1.0] + [np.nan] * 6)
        land = np.ones(8, bool)
        judged = np.array([np.nan, np.nan, 0, 0, 0, 0, 0, np.nan])
        conf = np.array(["", "", "low", "low", "low", "low", "low", ""], dtype=object)
        ref = np.array([""] * 8, dtype=object)
        v, basis, c, r = speculative.fill(obs, land, judged, conf, ref, nb)
        self.assertEqual(list(basis), ["observed"] * 2 + ["judged"] * 5 + ["extrapolated"])
        self.assertAlmostEqual(v[2], 0.75)       # one step from observed: 0.75 * 1 + 0.25 * 0
        self.assertAlmostEqual(v[3], 0.5)
        self.assertAlmostEqual(v[5], 0.0)        # beyond the blend rings
        self.assertEqual(c[7], "none")

    def test_firm_cells_do_not_blend(self):
        from isostyle import speculative
        nb = [[k for k in (i - 1, i + 1) if 0 <= k < 6] for i in range(6)]
        obs = np.array([1.0] + [np.nan] * 5)
        judged = np.array([np.nan, 0, 0, 0, 0, 0.0])
        conf = np.array([""] + ["low"] * 5, dtype=object)
        firm = np.array([False, False, True, False, False, False])
        v, basis, *_ = speculative.fill(obs, np.ones(6, bool), judged, conf, np.array([""] * 6, dtype=object), nb,
                                        firm=firm)
        self.assertAlmostEqual(v[1], 0.75)
        self.assertAlmostEqual(v[2], 0.0)        # firm: the judged value, one step further out
        self.assertAlmostEqual(v[3], 0.25)
        # judged_values reports which cells an adjust marked firm.
        j = {"expected": 0.5, "adjust": [{"kind": "area", "bbox": [0, 0, 1, 1], "value": 0.1, "firm": True}]}
        fm = np.zeros(2, bool)
        out = speculative.judged_values(j, np.array([0, 1]), np.array([0.5, 5.0]), np.array([0.5, 5.0]), -5000,
                                        np.array([1e9, 1e9]), firm=fm)
        self.assertEqual(fm.tolist(), [True, False])
        self.assertEqual(out.tolist(), [0.1, 0.5])

    def test_smoothing_never_moves_observed_cells(self):
        from isostyle import speculative
        nb = [[k for k in (i - 1, i + 1) if 0 <= k < 8] for i in range(8)]
        v = np.array([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, np.nan, 0.5])
        fixed = np.array([True, True] + [False] * 6)
        out = speculative.smooth_space(v, fixed, nb, 4)
        self.assertEqual(list(out[:2]), [1.0, 1.0])
        self.assertTrue(np.isnan(out[6]))                      # no value stays no value
        self.assertEqual(out[7], 0.5)                          # no valued neighbour: unchanged
        self.assertTrue(np.all(np.diff(out[1:6]) <= 0) and 0 < out[2] < 1)   # the cliff became a ramp
        # Time: a speculative spike between two slices is pulled toward them; observed is not.
        V = np.array([[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]])
        F = np.array([[False, False], [False, True], [False, False]])
        T = speculative.smooth_time(V, F, 0.5)
        self.assertAlmostEqual(T[1, 0], 0.5)
        self.assertEqual(T[1, 1], 1.0)

    def test_ring_distance_spreads_the_nearest_values(self):
        from isostyle import speculative
        nb = [[k for k in (i - 1, i + 1) if 0 <= k < 6] for i in range(6)]
        src = np.array([True, False, False, False, False, True])
        dist, val = speculative.ring_distance(src, np.array([1.0, 0, 0, 0, 0, 3.0]), nb)
        self.assertEqual(list(dist), [0, 1, 2, 2, 1, 0])
        self.assertEqual(list(val), [1.0, 1.0, 1.0, 3.0, 3.0, 3.0])

    def test_land_between_covers_cells_that_emerge_between_slices(self):
        import json, tempfile
        from isostyle import grid
        feats = [{"properties": {"terrain": t}} for t in (
            {"-12000": "Water", "-8500": "Tundra"},        # emerges after the -9000 slice
            {"-12000": "Water"},                           # always sea
            {"-12000": "Ice", "-9500": "Water"},           # ice, then a lake: never land
            {"-12000": "Plains", "-9500": "Water"})]       # drowned before -9000
        with tempfile.NamedTemporaryFile("w", suffix=".geojson") as f:
            json.dump({"features": feats}, f)
            f.flush()
            got = grid.land_between(f.name, [-10000, -9000, -8000])
        self.assertEqual(got.tolist(), [[False, True, True], [False] * 3, [False] * 3, [True, True, False]])

    def test_set_other_takes_the_remainder(self):
        from isostyle import speculative
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "intuitions"))
            open(os.path.join(d, "intuitions", "y_haplogroup.toml"), "w").write(
                '[meta]\nlayer = "Y haplogroup"\nsummary = "x"\n[[judgement]]\nregion = "Iberia"\nslices = [-6000]\n'
                'expected = { y_g2a = 0.6, y_i2 = 0.3 }\nconfidence = "low"\n')
            js = speculative.load_judgements(d, REGISTRY)
        self.assertAlmostEqual(js["y_g2a"][0]["expected"], 0.6)
        self.assertAlmostEqual(js["y_r1b"][0]["expected"], 0.0)
        self.assertAlmostEqual(js["y_other"][0]["expected"], 0.1)


class Adjust(unittest.TestCase):
    def test_adjust_kinds_in_order(self):
        from isostyle import speculative
        lon = np.array([30.0, 30.0, 30.0, 40.0, 50.0])
        lat = np.array([60.0, 64.0, 70.0, 64.0, 37.0])
        coast = np.array([500.0, 500.0, 50.0, 500.0, 500.0])
        cells = np.arange(5)
        j = {"expected": 0.3, "adjust": [
            {"kind": "gradient", "axis": "lat", "from": [62.0, 0.5], "to": [66.0, 0.1]},
            {"kind": "coast", "within_km": 100, "value": 0.9},
            {"kind": "area", "bbox": [45.0, 35.0, 55.0, 40.0], "value": 0.7},
            {"kind": "near", "point": [40.0, 64.0], "radius_km": 50, "value": 0.2}]}
        v = speculative.judged_values(j, cells, lon, lat, -5000, coast)
        self.assertAlmostEqual(v[0], 0.5)     # south of the gradient: its start value
        self.assertAlmostEqual(v[1], 0.3)     # halfway
        self.assertAlmostEqual(v[2], 0.9)     # coast overrides
        self.assertAlmostEqual(v[3], 0.2)     # near a point
        self.assertAlmostEqual(v[4], 0.7)     # inside the box
        j2 = {"expected": 0.3, "adjust": [{"kind": "slice_value", "slices": [-3000], "value": 0.8}]}
        self.assertAlmostEqual(speculative.judged_values(j2, cells, lon, lat, -3000, coast)[0], 0.8)
        self.assertAlmostEqual(speculative.judged_values(j2, cells, lon, lat, -4000, coast)[0], 0.3)


class AdjustModes(unittest.TestCase):
    def test_slices_add_and_elevation(self):
        from isostyle import speculative
        lon = np.array([30.0, 30.0]); lat = np.array([50.0, 50.0]); cells = np.arange(2)
        coast = np.array([500.0, 500.0]); elev = np.array([100.0, 2000.0])
        j = {"expected": 0.5, "adjust": [
            {"kind": "area", "bbox": [29.0, 49.0, 31.0, 51.0], "value": 0.9, "slices": [-3000]},
            {"kind": "elevation", "above_m": 1500, "value": -0.3, "mode": "add"}]}
        v = speculative.judged_values(j, cells, lon, lat, -5000, coast, elev)
        self.assertAlmostEqual(v[0], 0.5)       # the box applies only at -3000
        self.assertAlmostEqual(v[1], 0.2)       # high ground: 0.5 - 0.3
        v = speculative.judged_values(j, cells, lon, lat, -3000, coast, elev)
        self.assertAlmostEqual(v[0], 0.9)
        self.assertAlmostEqual(v[1], 0.6)
        j2 = {"expected": 0.9, "adjust": [{"kind": "area", "bbox": [0, 0, 90, 90], "value": 0.5, "mode": "add"}]}
        self.assertAlmostEqual(speculative.judged_values(j2, cells, lon, lat, -3000, coast)[0], 1.0)   # clipped


class RiverPolygon(unittest.TestCase):
    def test_polygon(self):
        from isostyle import speculative
        lon = np.array([47.0, 50.0]); lat = np.array([31.0, 31.0]); cells = np.arange(2)
        j = {"expected": 0.5, "adjust": [{"kind": "polygon", "points": [[46, 30], [48, 30], [48, 32], [46, 32]],
                                          "value": 0.1}]}
        v = speculative.judged_values(j, cells, lon, lat, -5000, np.array([1e9, 1e9]))
        self.assertEqual(v.round(2).tolist(), [0.1, 0.5])

    def test_named_river_follows_its_state(self):
        from isostyle.hydro import Hydro
        h = Hydro()
        if "Nile" not in h.river_names():
            self.skipTest("build/rivers.geojson not built")
        lon, lat = np.array([31.25, 25.0]), np.array([30.05, 27.0])      # Cairo; western desert
        d = h.distance_km(lon, lat, -5000, names=["Nile"])
        self.assertLess(d[0], 30)
        self.assertGreater(d[1], 200)

    def test_unnamed_reaches_by_size(self):
        from isostyle.hydro import Hydro
        h = Hydro()
        if not os.path.exists(h._reaches_path):
            self.skipTest("HydroRIVERS cache not built")
        # Merv oasis on the Murghab
        d = h.distance_km(np.array([61.8]), np.array([37.6]), -4000, min_upland_km2=20000, bbox=[60, 35, 64, 39])
        self.assertLess(d[0], 40)


class Lakes(unittest.TestCase):
    def test_lake_shoreline_and_inside(self):
        from isostyle.hydro import Hydro
        h = Hydro()
        if "Lake Megachad" not in h.lake_names():
            self.skipTest("build/lakes.geojson not built")
        # Inside Megachad's early Holocene extent, and far outside it.
        d = h.distance_km(np.array([17.0, 5.0]), np.array([16.0, 30.0]), -8000, lakes=["Lake Megachad"])
        self.assertEqual(d[0], 0.0)
        self.assertGreater(d[1], 500)
