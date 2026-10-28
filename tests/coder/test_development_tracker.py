"""Offline reconciliation invariants; mutations must not be admitted."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tracker_validator", ROOT / "scripts/tools/check_development_tracker.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class DevelopmentTrackerTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "config/development_tracker.json").read_text(encoding="utf-8"))

    def reject(self, text):
        self.assertTrue(any(text in error for error in VALIDATOR.check(self.data)))

    def test_reconciled_tracker_passes_without_mutation(self):
        before = copy.deepcopy(self.data)
        self.assertEqual(VALIDATOR.check(self.data), [])
        self.assertEqual(self.data, before)

    def test_duplicate_ids(self):
        self.data["workstreams"][0]["id"] = "DEV-01"
        self.reject("duplicate")

    def test_wrong_counts(self):
        self.data["counts"]["dev_done"] += 1
        self.reject("counts")

    def test_dangling_critical_path(self):
        self.data["critical_path"].append("DEV-999")
        self.reject("reference")

    def test_dangling_structured_internal_reference(self):
        self.data["dev_items"][0]["internal_refs"] = ["WS-999"]
        self.reject("reference")

    def test_external_source_references_are_additive(self):
        self.data["dev_items"][0]["external_sources"] = ["external:future/report.json"]
        self.assertEqual(VALIDATOR.check(self.data), [])

    def test_v2_production_ready_without_certification(self):
        self.data["dev_items"][4]["production_ready"] = True
        self.reject("production_ready")

    def test_missing_history(self):
        self.data.pop("history")
        self.reject("history")

    def test_tampered_historical_evidence(self):
        self.data["history"][0]["snapshot"]["dev_items"][2]["evidence"] = "rewritten"
        self.reject("history")

    def test_missing_original_item(self):
        self.data["dev_items"].pop()
        self.reject("historical item")

    def test_changed_original_title(self):
        self.data["dev_items"][0]["title"] = "replacement"
        self.reject("historical item")

    def test_readiness_requires_all_four_dimensions(self):
        self.data["dev_items"][2]["current_readiness"].pop("certified")
        self.reject("readiness")


if __name__ == "__main__":
    unittest.main()
