"""Supplementary genomes (published, not in AADR) reach the sample layers but
never the ancestry model."""
import inspect
import unittest

from isostyle import ancestry, people


class Supplementary(unittest.TestCase):
    def test_entries_are_complete_and_sourced(self):
        d = people.load_supplementary()
        self.assertGreater(len(d), 0)
        for _, g in d.iterrows():
            self.assertTrue(g["individual"] and g["publication"], g["individual"])
            self.assertTrue(-90 <= g["lat"] <= 90 and -180 <= g["lon"] <= 180, g["individual"])
            self.assertGreater(g["bp"], 0, g["individual"])
            self.assertGreater(g["sd"], 0, g["individual"])
        self.assertIn("TKH001", set(d["individual"]))

    def test_ancestry_reads_only_aadr(self):
        # The qpAdm table needs AADR genotypes; supplementary rows have none.
        self.assertNotIn("load_supplementary", inspect.getsource(people.load_aadr))
        self.assertNotIn("load_supplementary", inspect.getsource(ancestry))


if __name__ == "__main__":
    unittest.main()
