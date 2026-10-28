"""Read-only structured tracker context, including hostile/malformed fixtures."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_context_under_test", ROOT / "scripts/orchestration/project_context.py")
CONTEXT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTEXT)


class ProjectContextTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "config/development_tracker.json"
        self.path.parent.mkdir()
        self.data = json.loads((ROOT / "config/development_tracker.json").read_text(encoding="utf-8"))

    def write(self, data=None):
        self.path.write_text(json.dumps(self.data if data is None else data), encoding="utf-8")

    def legacy(self):
        (self.root / "IMPLEMENTATION_TRACKER.md").write_text(
            "### Old work\n- [ ] pending legacy\n- [x] done legacy\n", encoding="utf-8")

    def test_structured_source_counts_and_no_mutation(self):
        self.write()
        self.legacy()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = CONTEXT.tracker(self.root)
        self.assertEqual(result["source"], str(self.path))
        self.assertEqual(result["validation"], "PASS")
        self.assertTrue(result["legacy_present"])
        self.assertEqual(result["counts"], self.data["counts"])
        self.assertEqual(len(result["declared_items"]), 20)
        self.assertTrue(all(set(item) == {"ws", "item"} for item in result["open_items"]))
        self.assertNotIn("pending legacy", str(result["open_items"]))
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_historical_done_is_not_current_certification(self):
        self.write()
        result = CONTEXT.tracker(self.root)
        declared = {item["id"]: item for item in result["declared_items"]}
        readiness = result["current_host_readiness"]
        current = {item["id"]: item for item in readiness["items"]}
        for ident in ("DEV-03", "DEV-04"):
            self.assertEqual(declared[ident]["status"], "done")
            self.assertIn("1.18.30", declared[ident]["completion_scope"])
            self.assertNotEqual(current[ident]["certified"], "PASS")
            self.assertIn(ident, readiness["pending_ids"])
            self.assertTrue(any(item["ws"] == ident for item in result["open_items"]))
        self.assertIn("WS-57A", readiness["unassessed_ids"])
        self.assertEqual(readiness["host_versions"], ["2.0.29"])
        self.assertIn("not runtime certification", readiness["authority"])

    def test_legacy_fallback_only_when_structured_absent(self):
        self.legacy()
        result = CONTEXT.tracker(self.root)
        self.assertEqual(result["source_format"], "legacy_markdown")
        self.assertEqual(result["open_items"], [{"ws": "Old work", "item": "pending legacy"}])
        self.assertNotIn("counts", result)

    def test_no_source(self):
        result = CONTEXT.tracker(self.root)
        self.assertIn("error", result)
        self.assertFalse(result["legacy_present"])

    def test_invalid_structured_never_falls_back(self):
        self.legacy()
        mutations = [[], None, {"dev_items": {}}, {"dev_items": [None]},
                     {"dev_items": [], "workstreams": [], "counts": []}]
        for field, value in (("history", [None]), ("critical_path", "DEV-03")):
            data = copy.deepcopy(self.data)
            data[field] = value
            mutations.append(data)
        for field, value in (("certified", []), ("external_sources", "untrusted.json"),
                             ("scope", None)):
            data = copy.deepcopy(self.data)
            data["dev_items"][2]["current_readiness"][field] = value
            mutations.append(data)
        for field, value in (("id", []), ("status", "green"),
                             ("current_readiness", []), ("internal_refs", "DEV-03"),
                             ("production_ready", "true")):
            data = copy.deepcopy(self.data)
            data["dev_items"][0][field] = value
            mutations.append(data)
        duplicate = copy.deepcopy(self.data)
        duplicate["workstreams"][0]["id"] = "DEV-01"
        mutations.append(duplicate)
        bad_counts = copy.deepcopy(self.data)
        bad_counts["counts"]["dev_done"] += 1
        mutations.append(bad_counts)
        for data in mutations:
            with self.subTest(data=str(data)[:70]):
                self.path.write_text(json.dumps(data), encoding="utf-8")
                result = CONTEXT.tracker(self.root)
                self.assertIn("error", result)
                self.assertEqual(result["validation"], "FAIL")
                self.assertEqual(result["source"], str(self.path))
                self.assertTrue(result["legacy_present"])
                self.assertNotIn("open_items", result)
        self.path.write_text("{bad JSON", encoding="utf-8")
        self.assertEqual(CONTEXT.tracker(self.root)["validation"], "FAIL")

    def test_duplicate_json_keys_and_unreadable_source_fail_closed(self):
        self.legacy()
        self.path.write_text('{"dev_items": [], "dev_items": []}', encoding="utf-8")
        before = self.path.read_bytes()
        result = CONTEXT.tracker(self.root)
        self.assertEqual(result["validation"], "FAIL")
        self.assertIn("duplicate JSON key", result["error"])
        self.assertEqual(before, self.path.read_bytes())
        self.path.unlink()
        self.path.mkdir()
        result = CONTEXT.tracker(self.root)
        self.assertEqual(result["validation"], "FAIL")
        self.assertNotIn("open_items", result)

    def test_fixture_root_cannot_supply_validator_code(self):
        self.write()
        evil = self.root / "scripts/tools/check_development_tracker.py"
        evil.parent.mkdir(parents=True)
        evil.write_text("raise RuntimeError('fixture code executed')", encoding="utf-8")
        self.assertEqual(CONTEXT.tracker(self.root)["validation"], "PASS")

    def test_canonical_read_only_smoke_via_environment_root(self):
        canonical = Path("E:/opencode_harness_portable")
        self.assertTrue(canonical.is_dir(), "accepted canonical tracker must be available")
        paths = [canonical / "config/development_tracker.json", canonical / "IMPLEMENTATION_TRACKER.md"]
        before = {p: p.read_bytes() for p in paths if p.is_file()}
        with patch.dict(os.environ, {"OPENCODE_HARNESS_ROOT": str(canonical)}):
            result = CONTEXT.tracker(CONTEXT._harness_root())
        self.assertEqual(result["validation"], "PASS")
        self.assertEqual(result["counts"]["dev_done"], 3)
        self.assertIn("DEV-04", result["current_host_readiness"]["pending_ids"])
        self.assertEqual(before, {p: p.read_bytes() for p in paths if p.is_file()})


if __name__ == "__main__":
    unittest.main()
