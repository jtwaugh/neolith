import unittest

import numpy as np

from pipeline import productivity


class Fill(unittest.TestCase):
    def test_fills_ring_by_ring_and_stops(self):
        # A chain 0-1-2-3-4: only hex 0 has data.
        nb = [[1], [0, 2], [1, 3], [2, 4], [3]]
        v = np.array([400.0, np.nan, np.nan, np.nan, np.nan])
        out, n = productivity.fill_from_neighbours(v, nb, 2)
        self.assertEqual(n, 2)
        np.testing.assert_array_equal(out[:3], [400, 400, 400])
        self.assertTrue(np.isnan(out[3:]).all())

    def test_a_pass_reads_only_the_previous_ring(self):
        # Hex 1 sits between 200 and a gap; it must not see hex 2's fill.
        nb = [[1], [0, 2], [1, 3], [2]]
        v = np.array([200.0, np.nan, np.nan, 600.0])
        out, _ = productivity.fill_from_neighbours(v, nb, 1)
        np.testing.assert_array_equal(out, [200, 200, 600, 600])


class Miami(unittest.TestCase):
    def test_the_scarcer_of_warmth_and_water_limits(self):
        # Values from the two published curves.
        self.assertAlmostEqual(float(productivity.miami(10.0, 5000.0)), 3000 / (1 + np.exp(1.315 - 1.19)), places=6)
        self.assertAlmostEqual(float(productivity.miami(30.0, 100.0)), 3000 * (1 - np.exp(-0.0664)), places=6)
        # Cold desert and hot desert are both poor; warm and wet is rich.
        v = productivity.miami([-15.0, 28.0, 25.0], [400.0, 20.0, 2000.0])
        self.assertLess(v[0], 150)
        self.assertLess(v[1], 50)
        self.assertGreater(v[2], 2000)
        self.assertTrue(np.isnan(productivity.miami(np.nan, 500.0)))


if __name__ == "__main__":
    unittest.main()
