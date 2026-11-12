import unittest

import numpy as np

from pipeline import report
from pipeline.tests.test_pipeline import make_grid


def site(name, hex_id, founding=None, abandoned=None):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            "properties": {"name": name, "hex": hex_id, "founding": founding, "abandoned": abandoned}}


class SettlementWater(unittest.TestCase):
    def setUp(self):
        self.g = make_grid(5, 5)
        n = len(self.g)
        land = np.full(n, "Temperate Forest", dtype=object)
        self.centre = 13                                 # an interior hex (index 12)
        i = self.centre - 1
        early, late = land.copy(), land.copy()
        late[i] = "Water"                                # drowned in the later year, neighbours still land
        sea = np.full(n, "Water", dtype=object)          # everything drowned
        self.terrain = {-6000: early, -5000: late, -4000: sea}

    def section(self, sites):
        return "\n".join(report.settlement_water_section(self.g, self.terrain, sites))

    def test_counts_only_years_alive(self):
        txt = self.section([site("Alive", self.centre, -6000, -4900), site("Gone", self.centre, -6000, -5500),
                            site("Dry", 1, -6000, -5000)])
        self.assertIn("1 of 3 settlements", txt)
        self.assertIn("| Alive |", txt)
        self.assertNotIn("Gone", txt)

    def test_coastal_vs_offshore(self):
        txt = self.section([site("Late", self.centre, -6000)])
        # On Water in -5000 (coastal: neighbours land) and -4000 (offshore: all water).
        self.assertIn("| Late | 0.00, 0.00 | 2000 / 3000 | -5000…-4000 | 1000 |", txt)
        self.assertIn("| on Water | 0 | 1 | 1 |", txt)

    def test_unknown_hex_and_no_hits(self):
        txt = self.section([site("Nowhere", 9999), site("Dry", 1, abandoned=-5000)])
        self.assertIn("0 of 2 settlements", txt)
        self.assertNotIn("| on Water |", txt)


if __name__ == "__main__":
    unittest.main()
