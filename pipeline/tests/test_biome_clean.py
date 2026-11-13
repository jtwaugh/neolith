import unittest

import numpy as np

from pipeline import biome_clean, elevation
from pipeline.tests.test_pipeline import make_grid


def boundary_turns(grid, t):
    """How many hexes on the A|B boundary have a boundary neighbour in a
    different row: zero for a straight vertical edge."""
    col = np.rint((grid.centres[:, 0] - grid.centres[:, 0].min()) / 0.75).astype(int)
    edge = [i for i in range(len(t)) if any(t[j] != t[i] for j in grid.neighbours[i]) and t[i] == "A"]
    return len(set(col[edge]))


class Warp(unittest.TestCase):
    def setUp(self):
        self.g = make_grid(30, 30)
        x = self.g.centres[:, 0]
        # A straight north-south edge between two land biomes.
        self.t = np.where(x < x.mean(), "Grassland", "Boreal Forest").astype(object)

    def test_roughens_a_straight_edge(self):
        g = self.g
        a = np.where(self.t == "Grassland", "A", "B")
        targets = biome_clean.warp_targets(g, {"seed": 3, "amplitude": 1.5, "period": 4.0})
        out, n = biome_clean.warp(self.t, targets, np.ones(len(g), dtype=bool))
        self.assertGreater(n, 10)
        b = np.where(out == "Grassland", "A", "B")
        self.assertLessEqual(boundary_turns(g, a), 1)
        self.assertGreater(boundary_turns(g, b), 1)

    def test_same_field_every_year_and_masked(self):
        g = self.g
        cfg = {"seed": 3}
        t1 = biome_clean.warp_targets(g, cfg)
        t2 = biome_clean.warp_targets(g, cfg)
        self.assertTrue((t1 == t2).all())
        out, n = biome_clean.warp(self.t, t1, np.zeros(len(g), dtype=bool))
        self.assertEqual(n, 0)

    def test_water_and_ice_never_move(self):
        g = self.g
        t = self.t.copy()
        t[:50] = "Water"
        t[50:80] = "Ice"
        targets = biome_clean.warp_targets(g, {"seed": 1, "amplitude": 2.0})
        out, _ = biome_clean.warp(t, targets, np.ones(len(g), dtype=bool))
        self.assertTrue((out[:80] == t[:80]).all())
        self.assertFalse(np.isin(out[80:], ["Water", "Ice"]).any())


class Adjacency(unittest.TestCase):
    def test_no_forbidden_pair_is_left(self):
        g = make_grid(20, 20)
        x = g.centres[:, 0]
        t = np.where(x < x.mean(), "Extreme Desert", "Boreal Forest").astype(object)
        t[:20] = "Ice"
        forbid = biome_clean.forbid_table({"forbid": [
            ["Extreme Desert", "Boreal Forest", "Steppe-Forest"],
            ["Ice", "Extreme Desert", "Tundra"],
        ]})
        prefer = x >= x.mean()
        out, n = biome_clean.fix_adjacency(t, g.neighbours, forbid, prefer)
        self.assertGreater(n, 0)
        for i, ns in enumerate(g.neighbours):
            for j in ns:
                self.assertNotIn(frozenset((out[i], out[j])), forbid, (i, j, out[i], out[j]))
        # Ice is fixed; the preferred (model) side took the bridge.
        self.assertTrue((out[:20] == "Ice").all())
        self.assertEqual(int((out[~prefer] == "Steppe-Forest").sum()), 0)


class Floodplain(unittest.TestCase):
    def test_desert_river_turns_green_forest_river_does_not(self):
        g = make_grid(12, 12)
        n = len(g)
        x = g.centres[:, 0]
        col = np.rint((x - x.min()) / 0.75).astype(int)
        t = np.full(n, "Extreme Desert", dtype=object)
        t[col >= 8] = "Temperate Forest"
        river = np.zeros(n, dtype=int)
        on = np.abs(g.centres[:, 1] - np.median(g.centres[:, 1])) < 0.45
        river[on] = 2
        elev = np.full(n, 100.0)
        elev[on] = 90.0
        landform = np.full(n, elevation.FLAT)
        cfg = {"apply_to": ["Extreme Desert"], "max_rise": 30.0, "spread": 1}
        out, k = biome_clean.floodplains(t, river, elev, landform, g.neighbours, cfg)
        fp = out == "Floodplain"
        self.assertTrue(fp[on & (col < 8)].all())
        self.assertFalse(fp[col >= 8].any())
        self.assertGreater(fp.sum(), (on & (col < 8)).sum())   # spread a ring
        # Too high above the river: no spread.
        elev2 = np.where(on, 90.0, 300.0)
        out2, _ = biome_clean.floodplains(t, river, elev2, landform, g.neighbours, cfg)
        self.assertEqual(int((out2 == "Floodplain").sum()), int((on & (col < 8)).sum()))

    def test_mountain_rivers_are_skipped(self):
        g = make_grid(4, 4)
        t = np.full(len(g), "Grassland", dtype=object)
        river = np.full(len(g), 2)
        landform = np.full(len(g), elevation.MOUNTAINS)
        out, k = biome_clean.floodplains(t, river, np.zeros(len(g)), landform, g.neighbours,
                                         {"apply_to": ["Grassland"]})
        self.assertEqual(k, 0)

    def test_keyframe_eligibility_holds_through_a_biome_swap(self):
        g = make_grid(6, 1)
        n = len(g)
        river = np.zeros(n)
        river[0] = 2
        landform = np.full(n, elevation.FLAT)
        elev = np.zeros(n)
        cfg = {"apply_to": ["Grassland", "Steppe-Forest"], "spread": 1, "no_spread": ["Steppe-Forest"]}
        grass = np.full(n, "Grassland", dtype=object)
        forest = np.full(n, "Temperate Forest", dtype=object)
        # Open in two of three keyframes: still a floodplain in the forest year.
        elig = biome_clean.floodplain_eligibility({-7000: grass, -6000: grass, -5000: forest}, cfg)
        out, _ = biome_clean.floodplains(forest, river, elev, landform, g.neighbours, cfg, elig)
        self.assertEqual(out[0], "Floodplain")
        self.assertGreater((out == "Floodplain").sum(), 1)   # Grassland spreads a ring
        # Commonest open biome Steppe-Forest: the river hex only, no ring.
        sf = np.full(n, "Steppe-Forest", dtype=object)
        elig = biome_clean.floodplain_eligibility({-7000: sf, -6000: sf}, cfg)
        out, _ = biome_clean.floodplains(sf, river, elev, landform, g.neighbours, cfg, elig)
        self.assertEqual(int((out == "Floodplain").sum()), 1)
        # Open in only one of three: never.
        elig = biome_clean.floodplain_eligibility({-7000: grass, -6000: forest, -5000: forest}, cfg)
        out, _ = biome_clean.floodplains(grass, river, elev, landform, g.neighbours, cfg, elig)
        self.assertEqual(int((out == "Floodplain").sum()), 0)


class WaterPopulation(unittest.TestCase):
    def test_cleared_on_water_only(self):
        terrain = {-9000: np.array(["Water", "Grassland", "Water"], dtype=object)}
        pop = {-9000: np.array([0.5, 1.0, 0.0])}
        out, n = biome_clean.clear_water_population(pop, terrain)
        self.assertEqual(out[-9000].tolist(), [0.0, 1.0, 0.0])
        self.assertEqual(n, 1)
        self.assertEqual(pop[-9000][0], 0.5)   # input untouched


if __name__ == "__main__":
    unittest.main()
