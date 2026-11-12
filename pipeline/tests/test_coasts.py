import os
import tempfile
import unittest

import numpy as np

from pipeline import coasts
from pipeline.raster import Affine
from pipeline.tests.test_pipeline import make_grid


class Coasts(unittest.TestCase):
    def test_stage_turns_hexes_to_water_for_its_years(self):
        g = make_grid(6, 4, w=0.1, h=0.1 * np.sqrt(3) / 2)
        tf = Affine(0.01, -0.01, -0.5, 1.0)
        arr = np.zeros((200, 200), dtype=np.float32)
        years = [-8000, -6000, -4000]
        terrain = {y: np.array(["Plains"] * len(g), dtype=object) for y in years}
        c = g.centres
        x0, x1 = c[:, 0].min(), c[:, 0].max()
        y0, y1 = c[:, 1].min(), c[:, 1].max()
        mid = (x0 + x1) / 2
        poly = [[float(x), float(y)] for x, y in ((x0 - 0.1, y0 - 0.1), (mid, y0 - 0.1), (mid, y1 + 0.1), (x0 - 0.1, y1 + 0.1))]
        cat = ('[[coast]]\nkey = "c"\nname = "C"\n[[coast.stage]]\nfrom = -6000\nto = -4000\n'
               f'polygon = {poly}\n')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "coasts.toml")
            with open(path, "w") as f:
                f.write(cat)
            cfg = {"coasts": {"catalogue": path, "hex_fraction": 0.5}}
            out, cs = coasts.build(cfg, g, terrain, arr, tf, years, log=lambda m: None)
        west = c[:, 0] < mid - 0.06
        east = c[:, 0] > mid + 0.06
        self.assertTrue((out[-6000][west] == "Water").all())
        self.assertTrue((out[-6000][east] == "Plains").all())
        # Outside the stage's years the terrain is untouched.
        self.assertTrue((out[-8000] == "Plains").all())
        self.assertTrue((out[-4000] == "Plains").all())
        self.assertEqual(cs[0]["stages"][0]["hexes"], int((out[-6000] == "Water").sum()))


if __name__ == "__main__":
    unittest.main()
