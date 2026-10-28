import tempfile
import unittest
from pathlib import Path

from knowledge_pilot.extract import extract


class ExtractTests(unittest.TestCase):
    def test_local_extraction_is_bounded_and_redacts_obvious_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text("API_KEY=private-value\n" + "x" * 200, encoding="utf-8")
            result = extract(path, max_chars=100)
            self.assertEqual(result.status, "partial")
            self.assertNotIn("private-value", result.text)
            self.assertLessEqual(len(result.text), 100)

    def test_unsupported_is_not_success(self):
        result = extract(Path("scan.opaque"))
        self.assertEqual(result.status, "unsupported")

    def test_json_credentials_are_not_returned_in_source_fragments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"api_key": "dont-store-this", "password": "also-private"}', encoding="utf-8")
            result = extract(path)
            self.assertNotIn("dont-store-this", result.text)
            self.assertNotIn("also-private", result.text)


if __name__ == "__main__":
    unittest.main()
