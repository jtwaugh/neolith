import unittest

import numpy as np

from pipeline import compose


class Reinterpret(unittest.TestCase):
    def test_box_and_years(self):
        centres = np.array([[40.0, 45.0], [30.0, 10.0], [40.0, 45.0]])
        t = np.array(["Savannah", "Savannah", "Chaparral"], dtype=object)
        rules = [{"from": "Savannah", "to": "Grassland", "box": [-17, 30, 66.5, 76.5]},
                 {"from": "Chaparral", "to": "Grassland", "box": [26, 39, 66.5, 76.5], "years": [-9000, -8000]}]
        out, n = compose.reinterpret(t, centres, rules, -9000)
        self.assertEqual(list(out), ["Grassland", "Savannah", "Grassland"])   # the Sahel's savanna stays
        self.assertEqual(n, {0: 1, 1: 1})
        out, n = compose.reinterpret(t, centres, rules, -5000)
        self.assertEqual(list(out), ["Grassland", "Savannah", "Chaparral"])   # outside the rule's years
        self.assertEqual(t[0], "Savannah")                                  # input untouched


if __name__ == "__main__":
    unittest.main()
