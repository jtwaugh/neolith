import unittest

import numpy as np

from pipeline import residuals as R


class Pieces(unittest.TestCase):
    def test_hex_area(self):
        # A hex 0.5774 x 0.5 degrees on the equator: 3/4 of its box.
        a = R.hex_area_km2(np.array([[0.0, 0.25, 0.5774, -0.25]]))
        self.assertAlmostEqual(a[0], 0.75 * 0.5774 * 111.32 * 0.5 * 110.57, delta=1.0)
        north = R.hex_area_km2(np.array([[0.0, 60.25, 0.5774, 59.75]]))
        self.assertAlmostEqual(north[0] / a[0], 0.5, delta=0.01)

    def test_at_year_is_a_step_function(self):
        m = {"-10000": "Tundra", "-7700": "Water"}
        self.assertEqual(R.at_year(m, -8000), "Tundra")
        self.assertEqual(R.at_year(m, -7700), "Water")
        self.assertIsNone(R.at_year(m, -10001))

    def test_observed_counts_sites_occupied_within_the_window(self):
        site = lambda hex_id, phases: {"properties": {"hex": hex_id, "occupation": phases}}
        sites = [site(7, [[-6200, -5800]]), site(7, [[-9000, -8900], [-5400, -5000]]), site(9, [[-4600, -4500]]),
                 site(99, [[-6000, -5000]]), site(7, [])]
        out = R.observed(sites, np.array([7, 9]), [-6000, -5000, -4000], 500)
        np.testing.assert_array_equal(out, [[1, 1, 0], [0, 1, 0]])
        # A phase ending exactly where the window starts doesn't count.
        self.assertEqual(R.observed([site(7, [[-7000, -6500]])], np.array([7]), [-6000], 500)[0, 0], 0)


class Shared(unittest.TestCase):
    def test_coastal_factor_matches_the_rust_model(self):
        import os
        import tomllib
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, "pipeline/config.toml"), "rb") as f:
            rc = tomllib.load(f)["residuals"]
        a, b = rc["shore_factor"]
        with open(os.path.join(root, "neolith-rs/crates/core/src/forager.rs")) as f:
            rust = f.read()
        self.assertIn(f"({a} - {-b} * (shore_km.clamp(0.0, MAX_SHORE_KM) + 10.0).ln()).exp()", rust)
        self.assertIn(f"pub const MAX_SHORE_KM: f64 = {rc['max_shore_km']};", rust)


class Model(unittest.TestCase):
    def test_poisson_recovers_coefficients_with_an_offset(self):
        rng = np.random.default_rng(3)
        n = 20000
        x = rng.normal(size=n)
        off = rng.normal(2.0, 0.5, size=n)
        y = rng.poisson(np.exp(-1.0 + 0.7 * x + off)).astype(float)
        X = np.column_stack([np.ones(n), x])
        beta, se, dev = R.poisson(X, y, off)
        self.assertAlmostEqual(beta[0], -1.0, delta=4 * se[0])
        self.assertAlmostEqual(beta[1], 0.7, delta=4 * se[1])
        self.assertLess(se[1], 0.02)
        # Letting the offset's exponent go free finds 1.
        bf, sf, dev_free = R.poisson(np.column_stack([X, off]), y, np.zeros(n))
        self.assertAlmostEqual(bf[2], 1.0, delta=4 * sf[2])
        self.assertLessEqual(dev_free, dev + 1e-6)

    def test_classify(self):
        names = R.REASONS
        obs = np.array([0.0, 0.0, 0.0, 6.0, 2.0, 0.0])
        mu = np.array([0.5, 0.5, 3.5, 3.0, 2.0, 0.2])
        full = np.array([4.0, 4.0, 4.0, 2.0, 2.5, 0.6])
        parts = np.array([[1.5, 0.5, 0.0], [0.0, 1.6, 0.4], [0.0, 0.1, 0.0], [0, 0, 0], [0, 0, 0], [0, 1.0, 0]])
        out = [names[i] for i in R.classify(obs, mu, full, parts, 1.0, 2.0)]
        self.assertEqual(out, ["drowned", "little dated archaeology nearby", "unexplained shortfall",
                               "more sites than expected", "as expected", "as expected"])


if __name__ == "__main__":
    unittest.main()
