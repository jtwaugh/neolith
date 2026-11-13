import unittest

import numpy as np

from pipeline import edge_sea
from pipeline.raster import Affine


class OpenSea(unittest.TestCase):
    def test_closed_basins_are_not_sea(self):
        z = np.full((7, 7), 100.0)
        z[:, 0] = -3000.0            # ocean down the west side
        z[3, 1:3] = -20.0            # a bay joined to it
        z[3, 5] = -400.0             # a closed basin below sea level
        sea = edge_sea.open_sea(z, 0.0, -1500.0)
        self.assertTrue(sea[:, 0].all() and sea[3, 1] and sea[3, 2])
        self.assertFalse(sea[3, 5])
        # A lower sea leaves the shallow bay dry.
        self.assertFalse(edge_sea.open_sea(z, -50.0, -1500.0)[3, 1])


class Distances(unittest.TestCase):
    def setUp(self):
        # 1-degree cells, lon 0..20, lat 10 (row 0) down to 0; sea south of 3N.
        self.tf = Affine(1.0, -1.0, 0.0, 10.0)
        self.z = np.full((11, 21), 200.0)
        self.z[8:] = -2000.0
        self.z[5, 10] = -2000.0      # deep water inside the map's box

    def test_only_sea_outside_the_box_counts(self):
        box = (0.0, 4.0, 20.0, 10.0)  # the map covers lat 4..10
        c = np.array([[10.0, 5.0], [10.0, 8.0]])
        km = edge_sea.distances(c, box, self.z, self.tf, 0.0, -1500.0, 2000.0)
        # Nearest off-map sea is the row at 2N: 3 and 6 degrees of latitude.
        self.assertAlmostEqual(km[0], 3 * 111.2, delta=2)
        self.assertAlmostEqual(km[1], 6 * 111.2, delta=2)

    def test_beyond_reach_or_no_sea_is_none(self):
        box = (0.0, 4.0, 20.0, 10.0)
        c = np.array([[10.0, 5.0], [10.0, 8.0]])
        km = edge_sea.distances(c, box, self.z, self.tf, 0.0, -1500.0, 400.0)
        self.assertEqual(list(km), [334, edge_sea.NONE])
        # A box that takes in the whole raster leaves nothing off the map.
        km = edge_sea.distances(c, (-1.0, -1.0, 21.0, 11.0), self.z, self.tf, 0.0, -1500.0, 2000.0)
        self.assertEqual(list(km), [edge_sea.NONE, edge_sea.NONE])


if __name__ == "__main__":
    unittest.main()
