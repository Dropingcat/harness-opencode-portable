from __future__ import annotations

import unittest
from decimal import Decimal

from researcher_core.uncertainty import compare_with_uncertainty, parse_uncertainty, values_overlap


class UncertaintyAdapterTests(unittest.TestCase):
    def test_parse_uncertainty_pm(self) -> None:
        self.assertEqual(parse_uncertainty("12.5 ± 0.3"), (Decimal("12.5"), Decimal("0.3")))
        self.assertEqual(parse_uncertainty("12±0.3"), (Decimal("12"), Decimal("0.3")))

    def test_parse_uncertainty_range(self) -> None:
        self.assertEqual(parse_uncertainty("[10.0 - 12.0, 11 ± 0.5]"), (Decimal("10.0"), Decimal("12.0")))

    def test_parse_none(self) -> None:
        self.assertIsNone(parse_uncertainty("no numbers"))

    def test_values_overlap(self) -> None:
        self.assertTrue(values_overlap(Decimal("10"), Decimal("1"), Decimal("11"), Decimal("1")))
        self.assertFalse(values_overlap(Decimal("10"), Decimal("0.4"), Decimal("11"), Decimal("0.4")))

    def test_compare_with_uncertainty(self) -> None:
        self.assertEqual(compare_with_uncertainty(Decimal("10"), Decimal("1"), Decimal("10.5"), Decimal("1")), "MATCH")
        self.assertEqual(compare_with_uncertainty(Decimal("10"), Decimal("0.2"), Decimal("11"), Decimal("0.2")), "MISMATCH")
        self.assertEqual(compare_with_uncertainty(Decimal("10"), None, Decimal("10"), Decimal("1")), "NO_DATA")


if __name__ == "__main__":
    unittest.main()
