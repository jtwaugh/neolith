"""Inferred settlements (pipeline/inferred.py)."""
import unittest

import numpy as np

from pipeline import inferred


class Grid:
    """Two hexes split at lon 1.0, for _hex_of via a stub."""


class InferredTests(unittest.TestCase):
    def test_flows_is_a_step_function_absent_before_its_first_key(self):
        r = {"state": {"-5050": "perennial", "-3300": "absent"}}
        self.assertFalse(inferred.flows(r, -6000))
        self.assertTrue(inferred.flows(r, -5000))
        self.assertFalse(inferred.flows(r, -3000))

    def test_along_spaces_points_down_the_line(self):
        # About 111 km due north along a meridian; every 20 km from 10 km.
        pts = inferred.along([[0.0, 0.0], [0.0, 1.0]], 20.0, shift=0.5)
        self.assertEqual(len(pts), 6)
        lats = [p[1] for p in pts]
        self.assertAlmostEqual(lats[0] * inferred.KM_PER_DEG, 10.0, places=3)
        self.assertTrue(np.allclose(np.diff(lats) * inferred.KM_PER_DEG, 20.0))
        # The normal of a northward line points west or east.
        self.assertAlmostEqual(abs(pts[0][2][0]), 1.0)

    def test_candidates_alternate_sides_and_respect_bounds_and_flow(self):
        rivers = {"a": {"points": [[0.0, 0.0], [0.0, 1.0]], "state": {"-10000": "perennial"}},
                  "b": {"points": [[2.0, 0.0], [2.0, 1.0]], "state": {"-3500": "perennial"}}}
        rule = {"branches": ["a", "b"], "spacing_km": 20.0, "offset_km": [3.0], "max_lat": 0.5}
        pts = inferred.candidates(rule, rivers, -4000, 0.5)
        self.assertTrue(all(key == "a" for _, _, key in pts))   # b not flowing yet
        self.assertTrue(all(lat <= 0.5 for _, lat, _ in pts))
        sides = [np.sign(lon) for lon, _, _ in pts]
        self.assertEqual(sides[:2], [-sides[1], sides[1]])
        self.assertTrue(all(abs(abs(lon) * inferred.KM_PER_DEG - 3.0) < 0.05 for lon, _, _ in pts))

    def test_shore_cells_are_land_beside_open_sea_ranked_by_size(self):
        from pipeline.raster import Affine
        # 0.1 deg cells, row 0 at lat 0.9. Land west of column 5 and a
        # one-cell island at column 8; a closed pit below sea level inland.
        z = np.full((10, 10), -100.0)
        z[:, :5] = 10.0
        z[4, 8] = 10.0
        z[5, 1] = -20.0
        shore = inferred.Shore(z, Affine(0.1, -0.1, 0.0, 0.9), [[-10000, 0.0], [0, 0.0]], -50.0)
        cells = shore.cells(-5000, (0.0, 0.0, 0.9, 0.9))
        lons = sorted({round(lo, 3) for lo, _, _ in cells})
        self.assertEqual(lons, [0.4, 0.8])            # the coast column and the island
        self.assertTrue(all(sh == (1 if round(lo, 3) == 0.8 else 0) for lo, _, sh in cells))
        lats = [la for _, la, _ in cells]
        self.assertEqual(lats, sorted(lats, reverse=True))   # north to south

    def test_coast_candidates_prefer_then_space_and_cap(self):
        cells = [(0.0, la / 100, 0) for la in range(100, -1, -1)]   # a 111 km shore
        rule = {"coast": {"spacing_km": 30.0, "prefer": [[0.05, 0.5]], "prefer_km": 10.0}}
        pts = inferred.coast_candidates(rule, cells, lambda lo, la: la > 0.1)
        self.assertEqual(pts[0][:2], (0.0, 0.5))     # nearest cell to the preferred place
        self.assertTrue(all(la > 0.1 for _, la, _ in pts))
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                self.assertGreaterEqual(inferred.km(a, b), 30.0)
        rule["coast"]["max_points"] = 2
        self.assertEqual(len(inferred.coast_candidates(rule, cells, lambda lo, la: True)), 2)

    def test_tag_goes_to_the_first_placed_point_on_each_large_shore(self):
        import types
        # Three land hexes split at lon 1 and 2; hex 1 (lon 1-2) has a
        # recorded site, so the first shore-1 candidate there is cleared.
        grid = types.SimpleNamespace(ids=[0, 1, 2], centres=np.array([[0.5, 0], [1.5, 0], [2.5, 0]]))
        feats = [{"properties": {"terrain": {"-10000": "Grassland"}}} for _ in range(3)]
        rule = {"key": "r", "plan": "p", "label": "camp", "kind": "open air", "slices": [-5000],
                "clear": "hex", "confidence": "low", "reasoning": "x",
                "coast": {"box": [0, -1, 3, 1], "spacing_km": 10.0},
                "tag": {"name": "t", "slices": [-5000], "shores": 2, "confidence": "low", "reasoning": "y"}}
        cells = [(0.5, 0.0, 0), (1.5, 0.0, 1), (2.5, 0.0, 1), (2.6, 0.5, 2)]
        shore = types.SimpleNamespace(cells=lambda y, box: cells)
        sites = [{"geometry": {"coordinates": [1.5, 0.0]},
                  "properties": {"founding": -6000, "abandoned": -3000, "occupation": [[-6000, -3000]]}}]
        orig = inferred._hex_of
        inferred._hex_of = lambda g, lon, lat: int(lon)
        try:
            out, _ = inferred.build([rule], {}, grid, feats, sites, [-5000, -4000], log=lambda m: None, shore=shore)
        finally:
            inferred._hex_of = orig
        got = [(f["geometry"]["coordinates"][0], f["properties"]["inferred"].get("tag")) for f in out]
        self.assertEqual(got, [(0.5, "t"), (2.5, "t"), (2.6, None)])
        self.assertIsNone(inferred.tag_for(rule, -6000))
    def test_points_rule_places_named_points_on_land_and_tags_the_first(self):
        import types
        grid = types.SimpleNamespace(ids=[0, 1, 2], centres=np.array([[0.5, 0], [1.5, 0], [2.5, 0]]))
        feats = [{"properties": {"terrain": {"-10000": "Water" if i == 1 else "Grassland"}}} for i in range(3)]
        rule = {"key": "p", "plan": "p", "label": "camp", "kind": "open air", "slices": [-5000],
                "clear": "hex", "confidence": "low", "reasoning": "x",
                "points": {"at": [[0.5, 0.0], [1.5, 0.0], [2.5, 0.0]]},
                "tag": {"name": "t", "slices": [-5000], "shores": 1, "confidence": "low", "reasoning": "y"}}
        orig = inferred._hex_of
        inferred._hex_of = lambda g, lon, lat: int(lon)
        try:
            out, rep = inferred.build([rule], {}, grid, feats, [], [-5000, -4000], log=lambda m: None)
        finally:
            inferred._hex_of = orig
        got = [(f["geometry"]["coordinates"][0], f["properties"]["inferred"].get("tag")) for f in out]
        self.assertEqual(got, [(0.5, "t"), (2.5, None)])     # the Water hex is dropped
        self.assertEqual(rep[0][2]["water"], 1)


    def test_show_false_rules_are_not_shown(self):
        self.assertTrue(inferred.shown({"key": "a"}))
        self.assertTrue(inferred.shown({"key": "a", "show": True}))
        self.assertFalse(inferred.shown({"key": "a", "show": False}))

if __name__ == "__main__":
    unittest.main()
