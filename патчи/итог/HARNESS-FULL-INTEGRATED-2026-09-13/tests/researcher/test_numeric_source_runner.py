from __future__ import annotations

import unittest

from researcher_core.numeric_source_runner import compare_claim_sources_json, numeric_value_from_json


class NumericSourceRunnerTests(unittest.TestCase):
    def test_numeric_value_from_json_scalar_and_range(self) -> None:
        self.assertIsNotNone(numeric_value_from_json({"value": "12", "unit": "%"}))
        self.assertIsNotNone(numeric_value_from_json({"lower": "1", "upper": "2", "unit": "um"}))
        self.assertIsNotNone(numeric_value_from_json({"range": {"low": "1", "high": "2"}, "unit": "um"}))
        self.assertIsNone(numeric_value_from_json({"text": "no value"}))

    def test_compare_claim_sources_json_match_via_unit_conversion(self) -> None:
        result = compare_claim_sources_json(
            {"claim_id": "c1", "claim_text": "size 1000 nm", "value": "1000", "unit": "nm"},
            [{"title": "src1", "text": "size 1 um", "value": "1", "unit": "um"}],
        )
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["results"][0]["source_status"], "match")

    def test_compare_claim_sources_json_qualifier_mismatch(self) -> None:
        result = compare_claim_sources_json(
            {"claim_id": "c1", "claim_text": "для всех сталей 1000 nm", "value": "1000", "unit": "nm"},
            [{"title": "src1", "text": "до 1 um", "value": "1", "unit": "um"}],
        )
        self.assertEqual(result["status"], "qualifier_mismatch")

    def test_compare_claim_sources_json_formula_conflict_forces_mismatch(self) -> None:
        result = compare_claim_sources_json(
            {"claim_id": "c1", "claim_text": "Scherrer K=1.0 gives 1000 nm", "value": "1000", "unit": "nm"},
            [{"title": "src1", "text": "1 um", "value": "1", "unit": "um"}],
        )
        self.assertEqual(result["formula"]["constant_check"], "formula_conflict")
        self.assertEqual(result["status"], "mismatch")

    def test_compare_claim_sources_json_no_numbers(self) -> None:
        result = compare_claim_sources_json({"claim_id": "c1", "claim_text": "no numeric claim"}, [])
        self.assertEqual(result["status"], "no_numbers_in_claim")


if __name__ == "__main__":
    unittest.main()
