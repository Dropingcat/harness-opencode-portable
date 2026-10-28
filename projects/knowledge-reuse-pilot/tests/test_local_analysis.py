import tempfile
import unittest
from pathlib import Path

from knowledge_pilot.local_analysis import table_profile


class LocalAnalysisTests(unittest.TestCase):
    def test_csv_profile_is_local_bounded_and_does_not_mutate_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "measurements.csv"
            path.write_text("sample,value\nA,1\nB,3\nC,5\n", encoding="utf-8")
            before = path.read_bytes()
            result = table_profile(path, max_rows=2)
            self.assertEqual(result["rows_profiled"], 2)
            self.assertTrue(result["truncated"])
            self.assertEqual(result["numeric"]["value"]["mean"], 2.0)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
