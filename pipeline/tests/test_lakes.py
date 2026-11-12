import os
import tempfile
import unittest

import numpy as np

from pipeline import lakes, rivers
from pipeline.raster import Affine
from pipeline.tests.test_pipeline import make_grid


def bowl():
    """A 30 x 30 bowl: floor 0 m, rim 100 m, with a notch (outlet) at 40 m
    on the east side."""
    yy, xx = np.mgrid[0:30, 0:30]
    z = np.hypot(yy - 15, xx - 15) * 8.0
    z = np.minimum(z, 100.0)
    z[14:16, 18:] = 40.0
    return z.astype(np.float32)


class Minimax(unittest.TestCase):
    def test_spill_is_the_outlet(self):
        need, spill = lakes.minimax(bowl().astype(float), (15, 15))
        self.assertAlmostEqual(spill, 40.0)
        self.assertEqual(need[15, 15], 0.0)
        # A cell on the slope is covered once the lake reaches its height.
        self.assertAlmostEqual(need[15, 10], 40.0)

    def test_level_fn(self):
        f = lakes.level_fn([[-9000, 300.0], [-8000, 320.0]])
        self.assertEqual((f(-10000), f(-8500), f(-7000)), (300.0, 310.0, 320.0))


class Area(unittest.TestCase):
    def test_area_target_picks_the_level(self):
        z = np.zeros((20, 20))
        z[0, :] = z[-1, :] = z[:, 0] = z[:, -1] = 50.0
        order = []
        need, _ = lakes.minimax(z, (10, 10), order)
        # A flat floor: every cell needs 0 m, until ties are split.
        self.assertEqual(lakes.area_fn(need, np.ones(20))(30), 0.0)
        need = lakes.split_ties(need, order)
        f = lakes.area_fn(need, np.ones(20))
        lv = f(30)
        self.assertTrue(0.0 <= lv < 1.0)
        self.assertEqual(lakes.covered_km2(need, np.ones(20), lv), 30)
        # Filled outward from the seed.
        self.assertLessEqual(need[10, 10], need[10, 13])
        self.assertEqual(f(0), -np.inf)
        self.assertEqual(f(1e6), np.inf)

    def test_dam_closes_the_outlet(self):
        z = bowl().astype(float)
        cells = lakes.dam_cells([[0.9, 1.0], [0.9, 0.0]], Affine(0.05, -0.05, 0.0, 1.45), slice(0, 30), slice(0, 30))
        for r, c in cells:
            z[r, c] = max(z[r, c], 90.0)
        self.assertGreater(lakes.minimax(z, (15, 15))[1], 40.0)


class Contours(unittest.TestCase):
    def test_square_and_island(self):
        m = np.zeros((9, 9), dtype=bool)
        m[1:8, 1:8] = True
        m[4, 4] = False  # an island
        rings = lakes.contours(m)
        self.assertEqual(len(rings), 2)
        outer = max(rings, key=len)
        # Halfway between wet and dry cells.
        self.assertAlmostEqual(outer[:, 0].min(), 0.5)
        self.assertAlmostEqual(outer[:, 1].max(), 7.5)


class Build(unittest.TestCase):
    def test_lake_floods_and_exposes_hexes(self):
        # Hex grid of 0.1-degree hexes over the bowl raster (0.05-degree cells).
        g = make_grid(12, 10, w=0.1, h=0.1 * np.sqrt(3) / 2)
        g.bbox[:, [0, 2]] += 0.25
        g.bbox[:, [1, 3]] += 1.25
        for r in g.rings:
            for p in r:
                p[0] += 0.25
                p[1] += 1.25
        tf = Affine(0.05, -0.05, 0.0, 1.45)
        z = bowl()
        years = [-9000, -8000]
        # The drawn maps have the whole bowl as Water both years.
        terrain = {y: np.array(["Plains"] * len(g), dtype=object) for y in years}
        c = g.centres
        drawn = np.hypot(c[:, 0] - 0.75, c[:, 1] - 0.7) < 0.3
        for y in years:
            terrain[y][drawn] = "Water"
        cat = ('[[lake]]\nkey = "b"\nname = "Bowl"\nseed = [0.75, 0.7]\nbox = [0.0, 0.0, 1.5, 1.5]\n'
               'level = [[-9000, 80.0], [-8000, 10.0]]\n')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lakes.toml")
            with open(path, "w") as f:
                f.write(cat)
            cfg = {"lakes": {"catalogue": path, "hex_fraction": 0.5, "basin_margin": 25.0,
                             "shore_step": 2.0, "min_ring_cells": 4, "simplify": 0.0}}
            out, ls = lakes.build(cfg, g, terrain, z, tf, years, log=lambda m: None)
        lk = ls[0]
        # 80 m is above the 40 m outlet: held just under it.
        self.assertAlmostEqual(lk["level"][-9000], 39.5)
        wet_hi = (out[-9000] == "Water").sum()
        wet_lo = (out[-8000] == "Water").sum()
        self.assertGreater(wet_hi, wet_lo)
        self.assertGreater(wet_lo, 0)
        # Exposed hexes take land, not Water.
        self.assertTrue(set(out[-8000][drawn]) <= {"Water", "Plains"})
        self.assertEqual([s["from"] for s in lk["shapes"]], years)
        self.assertEqual(lk["shapes"][0]["to"], -8000)

    def test_until_hands_the_lake_back(self):
        g = make_grid(12, 10, w=0.1, h=0.1 * np.sqrt(3) / 2)
        g.bbox[:, [0, 2]] += 0.25
        g.bbox[:, [1, 3]] += 1.25
        for r in g.rings:
            for p in r:
                p[0] += 0.25
                p[1] += 1.25
        tf = Affine(0.05, -0.05, 0.0, 1.45)
        years = [-9000, -8000]
        terrain = {y: np.array(["Plains"] * len(g), dtype=object) for y in years}
        cat = ('[[lake]]\nkey = "b"\nname = "Bowl"\nseed = [0.75, 0.7]\nbox = [0.0, 0.0, 1.5, 1.5]\n'
               'level = [[-9000, 30.0]]\nuntil = -8000\n')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lakes.toml")
            with open(path, "w") as f:
                f.write(cat)
            cfg = {"lakes": {"catalogue": path, "hex_fraction": 0.5, "basin_margin": 25.0,
                             "shore_step": 2.0, "min_ring_cells": 4, "simplify": 0.0}}
            out, ls = lakes.build(cfg, g, terrain, bowl(), tf, years, log=lambda m: None)
        self.assertGreater((out[-9000] == "Water").sum(), 0)
        # From `until` the terrain is untouched and the shoreline ends.
        self.assertTrue((out[-8000] == "Plains").all())
        self.assertEqual(ls[0]["shapes"][0]["to"], -8000)
        self.assertEqual(ls[0]["shapes"][-1]["rings"], [])

    def test_sea_or_outlet_switches_with_the_sea(self):
        g = make_grid(12, 10, w=0.1, h=0.1 * np.sqrt(3) / 2)
        g.bbox[:, [0, 2]] += 0.25
        g.bbox[:, [1, 3]] += 1.25
        for r in g.rings:
            for p in r:
                p[0] += 0.25
                p[1] += 1.25
        tf = Affine(0.05, -0.05, 0.0, 1.45)
        z = bowl() - 60.0           # floor -60, notch (outlet) at -20
        z[14:16, 29] = -100.0       # open sea at the window edge, beyond the notch
        years = [-9000, -8000]
        terrain = {y: np.array(["Plains"] * len(g), dtype=object) for y in years}
        lk = {"key": "b", "name": "Bowl", "seed": [0.75, 0.7], "box": [0.0, 0.0, 1.5, 1.5],
              "level": "sea-or-outlet"}
        cfg = {"lakes": {"hex_fraction": 0.5, "shore_step": 2.0, "min_ring_cells": 4, "simplify": 0.0},
               "isostasy": {"centre": [0.0, 0.0], "azimuth": 0.0, "axes": [1.0, 1.0],
                            "peak_rate": 0.0, "scale": 1.0, "tau": 5.0},
               # Sea at -40 m (below the -20 m notch) then -10 m (above it).
               "sea": {"curve": [[-9000, -40.0], [-8000, -10.0]]}}
        out = lakes._sea_or_outlet(lk, cfg, g, terrain, z.astype(float), tf, years, lambda m: None)
        self.assertAlmostEqual(out["level"][-9000], -20.5)   # a lake at its outlet
        self.assertEqual(out["level"][-8000], -10.0)          # open sea
        self.assertTrue(out["shapes"][0]["rings"])            # lake: a shoreline
        self.assertEqual(out["shapes"][-1]["rings"], [])      # sea: none
        self.assertGreater((terrain[-8000] == "Water").sum(), (terrain[-9000] == "Water").sum())

    def test_spillway_river_follows_the_lake(self):
        lk = {"key": "b", "spill": 40.0, "raw": {-9000: 80.0, -8000: 10.0}}
        f = rivers._spill_fn({"lake": "b", "above": "outlet"}, {"b": lk}, "R")
        self.assertEqual((f(-9000), f(-8000)), ("perennial", "absent"))
        f = rivers._spill_fn({"lake": "b", "above": 5.0, "state": "seasonal"}, {"b": lk}, "R")
        self.assertEqual(f(-8000), "seasonal")
        with self.assertRaises(ValueError):
            rivers._spill_fn({"lake": "x", "above": 1.0}, {"b": lk}, "R")


if __name__ == "__main__":
    unittest.main()
