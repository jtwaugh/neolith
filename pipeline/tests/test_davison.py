import unittest

import numpy as np

from pipeline import davison

CFG = {**davison.DEFAULTS, "coast_speed": 0.0, "river_speed": 0.0}


def flat(box=(30.0, 28.0, 40.0, 31.0), step=0.1):
    mesh = davison.Mesh(box, step)
    return mesh, np.zeros(mesh.shape), np.ones(mesh.shape, bool)


def reach(mesh, after, lat, t):
    """Easternmost longitude the front has reached by t along a latitude."""
    row = int(np.abs(mesh.lat - lat).argmin())
    return mesh.lon[np.flatnonzero(after[row] <= t).max()]


class Factors(unittest.TestCase):
    def test_latitude(self):
        f = davison.latitude_factor([20.0, 30.0, 38.0, 56.0, 80.0], davison.DEFAULTS)
        self.assertEqual(f[0], 1.0)
        self.assertEqual(f[1], 1.0)
        self.assertAlmostEqual(f[3] / f[2], 0.5, places=9)
        self.assertEqual(f[4], 0.0)

    def test_altitude(self):
        f = davison.altitude_factor([0.0, 1000.0, 2000.0], davison.DEFAULTS)
        self.assertAlmostEqual(f[0], 1.0, places=6)
        self.assertAlmostEqual(f[1], 0.5, places=9)
        self.assertLess(f[2], 1e-6)

    def test_block_mean(self):
        mesh = davison.Mesh((0.0, 0.0, 2.0, 1.0), 1.0)
        fine = np.arange(8, dtype=float).reshape(2, 4)       # 0.5-degree cells, row 0 north
        tf = davison.Affine(0.5, -0.5, 0.25, 0.75)
        np.testing.assert_allclose(davison.block_mean(fine, tf, mesh), [[(0 + 1 + 4 + 5) / 4, (2 + 3 + 6 + 7) / 4]])


class Front(unittest.TestCase):
    def test_speed_on_open_land_is_two_root_growth_times_diffusivity(self):
        mesh, alt, land = flat()
        F = davison.fields(mesh, alt, land, [], CFG)
        after = davison.run(mesh, F, [31.0, 29.5], 700, CFG)
        km = (reach(mesh, after, 29.5, 700) - reach(mesh, after, 29.5, 400)) * 111.3 * np.cos(np.radians(29.5))
        self.assertAlmostEqual(km / 300, 1.0, delta=0.12)     # 2 sqrt(0.02 x 12.5) = 1 km/yr

    def test_high_ground_stops_it_and_sea_only_lets_it_cross_a_strait(self):
        mesh, alt, land = flat()
        col = lambda lon: int(np.abs(mesh.lon - lon).argmin())
        wall = alt.copy()
        wall[:, col(33.0):col(33.5)] = 2000.0
        after = davison.run(mesh, davison.fields(mesh, wall, land, [], CFG), [31.0, 29.5], 900, CFG)
        self.assertTrue(np.isnan(after[:, col(33.6):]).all())
        self.assertTrue(np.isfinite(after[:, col(32.5)]).all())
        strait = land.copy()
        strait[:, col(33.0):col(33.2)] = False               # about 20 km of water
        after = davison.run(mesh, davison.fields(mesh, alt, strait, [], CFG), [31.0, 29.5], 900, CFG)
        self.assertTrue(np.isfinite(after[:, col(34.0)]).all())
        wide = land.copy()
        wide[:, col(33.0):col(35.0)] = False                 # about 190 km
        after = davison.run(mesh, davison.fields(mesh, alt, wide, [], CFG), [31.0, 29.5], 900, CFG)
        self.assertTrue(np.isnan(after[:, col(35.5):]).all())

    def test_a_river_strip_carries_the_front_ahead(self):
        mesh, alt, land = flat()
        river = [[(31.0, 29.5), (39.5, 29.5)]]
        slow = davison.run(mesh, davison.fields(mesh, alt, land, [], CFG), [31.0, 29.5], 300, CFG)
        fast = davison.run(mesh, davison.fields(mesh, alt, land, river, {**CFG, "river_speed": 5.0}), [31.0, 29.5], 300, CFG)
        self.assertGreater(reach(mesh, fast, 29.5, 300), reach(mesh, slow, 29.5, 300) + 0.5)
        # The tongue is furthest along the river itself; it spreads sideways from there.
        self.assertGreater(reach(mesh, fast, 29.5, 300), reach(mesh, fast, 28.2, 300))


if __name__ == "__main__":
    unittest.main()
