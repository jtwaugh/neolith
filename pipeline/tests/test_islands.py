import unittest

import numpy as np

from pipeline import islands
from pipeline.tests.test_pipeline import make_grid

CFG = {"sea": {"curve": [[-10000, 0.0], [0, 0.0]]}}
ICFG = {"min_any_fraction": 0.01, "min_area_km2": 300.0, "min_hex_fraction": 0.1, "max_hexes": 5}


def cells_with(n, land):
    """Per hex 100 cells: `land[i]` of them at +10 m, the rest at -50 m."""
    return [np.sort(np.r_[np.full(100 - k, -50.0), np.full(k, 10.0)]) for k in (land.get(i, 0) for i in range(n))]


class Islands(unittest.TestCase):
    def setUp(self):
        # Hexes 1 degree wide near the equator: about 0.75 * 111 * 96 = 8000 km2 each.
        self.g = make_grid(6, 6)
        self.n = len(self.g)

    def run_islands(self, land, terrain=None, before=None):
        sea = np.full(self.n, "Water", dtype=object)
        t = {-5000: terrain if terrain is not None else sea}
        b = {-5000: before} if before is not None else {}
        out, stats, _ = islands.keep_islands(t, b, self.g, cells_with(self.n, land), CFG, [], ICFG)
        return out, stats

    def test_small_island_gets_its_best_hex(self):
        before = np.full(self.n, "Water", dtype=object)
        before[14] = "Chaparral"
        out, stats = self.run_islands({14: 30, 15: 5}, before=before)
        self.assertEqual(out[-5000][14], "Chaparral")       # own pre-water biome
        self.assertEqual(out[-5000][15], "Water")           # one hex is enough for ~2800 km2
        self.assertEqual(stats[-5000][0][2:], (1, 0, 1))

    def test_isolated_island_without_biome_takes_nearest_land(self):
        t = np.full(self.n, "Water", dtype=object)
        t[0] = "Boreal Forest"
        out, _ = self.run_islands({21: 40}, terrain=t)
        self.assertEqual(out[-5000][21], "Boreal Forest")

    def test_too_small_or_slivers_or_mainland_left_alone(self):
        out, stats = self.run_islands({14: 3})                # ~240 km2 < 300
        self.assertEqual(out[-5000][14], "Water")
        self.assertEqual(stats[-5000], [])
        big = {i: 50 for i in range(self.n)}                  # one landmass of 36 hexes > max_hexes
        out, stats = self.run_islands(big)
        self.assertTrue((out[-5000] == "Water").all())

    def test_already_shown_island_unchanged(self):
        t = np.full(self.n, "Water", dtype=object)
        t[14] = "Grassland"
        out, stats = self.run_islands({14: 30}, terrain=t)
        self.assertIs(out[-5000], t)
        self.assertEqual(stats[-5000], [])

    def test_land_fraction_and_levels(self):
        c = [np.array([-1.0, 1.0, 2.0, 3.0])]
        self.assertAlmostEqual(islands.land_fraction(c, np.array([0.0]))[0], 0.75)
        self.assertAlmostEqual(islands.land_fraction(c, np.array([2.0]))[0], 0.25)
        g = make_grid(1, 1)
        ring = [[-10, -10], [10, -10], [10, 10], [-10, 10], [-10, -10]]
        lakes = [{"key": "l", "shapes": [{"level": 5.0, "rings": [ring], "from": -5000, "to": -4500}]}]
        self.assertEqual(islands.water_levels(g, -5000, CFG, lakes)[0], 5.0)
        self.assertEqual(islands.water_levels(g, -4000, CFG, lakes)[0], 0.0)    # lake gone: the sea
        far = [[[50, 50], [60, 50], [60, 60], [50, 60], [50, 50]]]
        lakes[0]["shapes"][0]["rings"] = far
        self.assertEqual(islands.water_levels(g, -5000, CFG, lakes)[0], 0.0)    # outside the shoreline

    def test_majority_land_drawn_water_restored(self):
        t = np.full(self.n, "Grassland", dtype=object)
        t[14] = "Water"
        out, _, restored = islands.keep_islands({-5000: t}, {-5000: t.copy()}, self.g,
                                                cells_with(self.n, {i: 100 for i in range(self.n)} | {14: 60}),
                                                CFG, [], {**ICFG, "restore_majority_land": 0.5})
        self.assertEqual(out[-5000][14], "Grassland")
        self.assertEqual(restored[-5000], 1)

if __name__ == "__main__":
    unittest.main()
