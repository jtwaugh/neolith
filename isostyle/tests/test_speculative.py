"""The fill's sub-threshold evidence ramp and the bridge hold (isostyle/speculative.py)."""
import unittest

import numpy as np

from isostyle import speculative as spec


def line(n):
    """Neighbours of a row of n cells, as the (n, 6) array the fill uses."""
    nb = np.full((n, 6), -1)
    for i in range(n):
        js = [j for j in (i - 1, i + 1) if 0 <= j < n]
        nb[i, :len(js)] = js
    return nb


class SoftSources(unittest.TestCase):
    def test_ramp_toward_observed(self):
        n = 5
        obs = np.array([1.0, np.nan, np.nan, np.nan, np.nan])
        land = np.ones(n, bool)
        judged = np.full(n, 0.1)
        conf = np.full(n, "low", dtype=object)
        ref = np.full(n, "x", dtype=object)
        soft = np.array([0.0, 0.8, 0.0, 0.0, 0.0])
        v0, *_ = spec.fill(obs, land, judged, conf, ref, line(n), blend_rings=0)
        v1, basis, *_ = spec.fill(obs, land, judged, conf, ref, line(n), blend_rings=0, soft=soft)
        self.assertAlmostEqual(v0[1], 0.1)
        self.assertAlmostEqual(v1[1], 0.1 + 0.8 * 0.9)
        self.assertEqual(basis[1], "judged")          # never written as observed
        self.assertEqual(v1[0], 1.0)
        np.testing.assert_allclose(v1[2:], v0[2:])

    def test_firm_cells_not_raised(self):
        obs = np.array([1.0, np.nan])
        args = (obs, np.ones(2, bool), np.full(2, 0.1), np.full(2, "low", dtype=object), np.full(2, "", dtype=object), line(2))
        v, *_ = spec.fill(*args, blend_rings=0, firm=np.array([False, True]), soft=np.array([0.0, 0.9]))
        self.assertAlmostEqual(v[1], 0.1)


class BridgeHold(unittest.TestCase):
    def test_bridged_cell_keeps_its_records_mean(self):
        # Three slices, three cells: the middle cell is observed before and
        # after (0.1, 0.3); its neighbours are observed at 0.9 throughout.
        S, n = 3, 3
        obs = np.array([[0.9, 0.1, 0.9], [0.9, np.nan, 0.9], [0.9, 0.3, 0.9]])
        P = {"obs": obs, "land": np.ones((S, n), bool), "judged": np.full((S, n), 0.5),
             "jconf": np.full((S, n), "medium", dtype=object), "jref": np.full((S, n), "", dtype=object),
             "explicit": np.zeros((S, n), bool), "firm": np.zeros((S, n), bool), "range": (0.0, 1.0)}
        par = {**spec.DEFAULTS, "blend_rings": 4, "bridge": 1.0, "bridge_conf": 0, "time_smooth": 0.4,
               "smooth_iters": 8}
        held, *_ = spec.fill_layer(P, line(n), {**par, "bridge_hold": 1})
        free, *_ = spec.fill_layer(P, line(n), {**par, "bridge_hold": 0})
        self.assertAlmostEqual(held[1, 1], 0.2)
        self.assertGreater(free[1, 1], 0.3)


if __name__ == "__main__":
    unittest.main()
