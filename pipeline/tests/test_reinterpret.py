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


class Misdated(unittest.TestCase):
    def test_box_years_and_keep(self):
        from pipeline import compose
        centres = np.array([[0.0, 50.0], [1.0, 50.0], [0.5, 20.0], [0.2, 50.2]])
        t = np.array(["Boreal Forest", "Water", "Chaparral", "Ice"], dtype=object)
        rules = [{"name": "x", "years": [-8000], "boxes": [[-1, 40, 2, 60]]}]
        out, n = compose.misdated(t, centres, rules, -8000)
        # Ice in the box becomes a gap too (the model's ice replaces it); Water stays.
        self.assertEqual(out.tolist(), ["Land", "Water", "Chaparral", "Land"])
        self.assertEqual(n, {0: 2})
        self.assertEqual(t[0], "Boreal Forest")          # the input is left alone
        same, n = compose.misdated(t, centres, rules, -7000)
        self.assertIs(same, t)
        self.assertEqual(n, {})
        kept, _ = compose.misdated(t, centres, [{**rules[0], "keep": ["Water", "Ice"]}], -8000)
        self.assertEqual(kept[3], "Ice")

    def test_in_boxes_unions(self):
        from pipeline import compose
        c = np.array([[0.0, 0.0], [5.0, 5.0], [9.0, 9.0]])
        self.assertEqual(compose.in_boxes(c, [[-1, -1, 1, 1], [8, 8, 10, 10]]).tolist(), [True, False, True])
