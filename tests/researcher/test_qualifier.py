from __future__ import annotations

import unittest

from researcher_core.qualifier import compare_qualifiers, extract_qualifier


class QualifierAdapterTests(unittest.TestCase):
    def test_extract_qualifier_universal(self) -> None:
        self.assertIn("universal", extract_qualifier("Для всех сталей"))
        self.assertIn("standard_mode", extract_qualifier("в стандартном режиме"))

    def test_extract_qualifier_unspecified(self) -> None:
        self.assertEqual(extract_qualifier("обычный текст"), ("unspecified",))

    def test_extract_up_to(self) -> None:
        self.assertIn("up_to", extract_qualifier("до 500 МПа"))

    def test_compare_qualifiers_match(self) -> None:
        self.assertEqual(compare_qualifiers(("universal",), ("universal",)), "match")
        self.assertEqual(compare_qualifiers(("typical",), ("typical",)), "match")

    def test_compare_qualifiers_mismatch(self) -> None:
        self.assertEqual(compare_qualifiers(("universal",), ("unspecified",)), "qualifier_mismatch")
        self.assertEqual(compare_qualifiers(("standard_mode",), ("unspecified",)), "qualifier_mismatch")
        self.assertEqual(compare_qualifiers(("universal",), ("up_to",)), "qualifier_mismatch")


if __name__ == "__main__":
    unittest.main()
