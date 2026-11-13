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


class RuleMask(unittest.TestCase):
    def test_edge_noise_wanders_but_keeps_the_core(self):
        lon, lat = np.meshgrid(np.arange(20.0, 70.0, 0.5), np.arange(40.0, 65.0, 0.5))
        c = np.column_stack([lon.ravel(), lat.ravel()])
        rule = {"boxes": [[30.0, 46.0, 60.0, 55.0]], "edge_noise": {"amplitude": 1.5, "period": 5.0, "seed": 11}}
        m = compose.rule_mask(c, rule)
        plain = compose.in_boxes(c, rule["boxes"])
        far_in = (c[:, 0] > 33) & (c[:, 0] < 57) & (c[:, 1] > 48) & (c[:, 1] < 53)
        far_out = (c[:, 0] < 27) | (c[:, 0] > 63) | (c[:, 1] < 44) | (c[:, 1] > 57)
        self.assertTrue(m[far_in].all())
        self.assertFalse(m[far_out].any())
        self.assertGreater((m != plain).sum(), 0)          # the edge moves
        # Along 55°N the edge is not one straight row.
        row = (c[:, 0] > 35) & (c[:, 0] < 55)
        tops = [c[(c[:, 0] == x) & m, 1].max() for x in np.unique(c[row, 0])]
        self.assertGreater(len(set(tops)), 2)
        self.assertTrue(compose.rule_mask(c, {"boxes": rule["boxes"]}).tolist() == plain.tolist())
