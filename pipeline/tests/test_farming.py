import unittest

import numpy as np

from pipeline import farming


def strip(n, step_deg=0.5):
    """n hexes in a west-east line on the equator, each linked to the next."""
    centres = np.column_stack([np.arange(n) * step_deg, np.zeros(n)])
    neighbours = [[j for j in (i - 1, i + 1) if 0 <= j < n] for i in range(n)]
    return centres, neighbours


KM = farming.distance_km((0, 0), (0.5, 0))   # one step, about 55.6 km
CFG = {"origin": [0.0, 0.0], "start": -9000, "speed_km_per_year": 1.0, "sea_reach_km": 0.0}
YEARS = list(range(-10000, -2999, 100))


def land(n, **changes):
    t = {y: np.array(["Plains"] * n, dtype=object) for y in YEARS}
    for i, (name, until) in changes.items():
        for y in YEARS:
            if y < until:
                t[y][int(i)] = name
    return t


class Arrival(unittest.TestCase):
    def test_distance(self):
        self.assertAlmostEqual(farming.distance_km((0, 0), (0, 90)), np.pi / 2 * farming.EARTH_KM, places=3)

    def test_front_moves_at_the_speed(self):
        c, nb = strip(6)
        out, origin = farming.arrival(c, nb, land(6), YEARS, CFG)
        self.assertEqual(origin, 0)
        np.testing.assert_allclose(out, -9000 + KM * np.arange(6), rtol=1e-9)
        fast, _ = farming.arrival(c, nb, land(6), YEARS, {**CFG, "speed_km_per_year": 2.0})
        np.testing.assert_allclose(fast, -9000 + KM / 2 * np.arange(6), rtol=1e-9)

    def test_sea_stops_it_unless_within_reach(self):
        c, nb = strip(6)
        t = land(6, **{"2": ("Water", 0)})
        out, _ = farming.arrival(c, nb, t, YEARS, CFG)
        self.assertTrue(np.isnan(out[2:]).all())
        out, _ = farming.arrival(c, nb, t, YEARS, {**CFG, "sea_reach_km": 2.1 * KM})
        self.assertTrue(np.isnan(out[2]))
        self.assertAlmostEqual(out[3], -9000 + 3 * KM, places=6)
        # Two hexes of sea are out of reach.
        t = land(6, **{"2": ("Water", 0), "3": ("Water", 0)})
        out, _ = farming.arrival(c, nb, t, YEARS, {**CFG, "sea_reach_km": 2.1 * KM})
        self.assertTrue(np.isnan(out[2:]).all())

    def test_waits_for_ice_to_go(self):
        c, nb = strip(4)
        out, _ = farming.arrival(c, nb, land(4, **{"1": ("Ice", -8000)}), YEARS, CFG)
        self.assertEqual(out[1], -8000)
        self.assertAlmostEqual(out[2], -8000 + KM, places=6)

    def test_stops_at_the_last_year_and_starts_on_open_land(self):
        c, nb = strip(200)
        out, origin = farming.arrival(c, nb, land(200, **{"0": ("Water", 0)}), YEARS, CFG)
        self.assertEqual(origin, 1)
        self.assertTrue(np.nanmax(out) <= -3000)
        self.assertTrue(np.isnan(out[-1]) and np.isnan(out[0]))


if __name__ == "__main__":
    unittest.main()
