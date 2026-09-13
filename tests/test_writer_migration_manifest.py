"""Fail-closed structural checks for the writer unification migration map."""

from __future__ import annotations

import json
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config" / "writer_migration_manifest.json"
CLASSIFICATIONS = {
    "ACTIVE_MOVE",
    "ACTIVE_ADAPTER",
    "KEEP_SHARED",
    "ARCHIVE_AFTER_MIGRATION",
    "GENERATED_CLEANUP",
    "DEFERRED",
}
SOURCE_STATES = {"present", "generated", "optional"}


def _parts(path: str) -> tuple[str, ...]:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path:
        raise AssertionError(f"path must be normalized and repository-relative: {path!r}")
    return pure.parts


def _contains(parent: str, child: str) -> bool:
    parent_parts = _parts(parent)
    child_parts = _parts(child)
    return child_parts[: len(parent_parts)] == parent_parts


class WriterMigrationManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_top_level_schema_is_versioned_and_fail_closed(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertTrue(self.manifest["fail_closed"])
        self.assertEqual(self.manifest["canonical_root"], "scripts/writer")
        self.assertEqual(self.manifest["legacy_root"], "легаси/writer")
        self.assertIsInstance(self.manifest["phases"], list)
        self.assertIsInstance(self.manifest["groups"], list)
        self.assertTrue(self.manifest["phases"])
        self.assertTrue(self.manifest["groups"])

    def test_phase_order_and_independent_gates(self) -> None:
        phases = self.manifest["phases"]
        ids = [phase["id"] for phase in phases]
        orders = [phase["order"] for phase in phases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(orders, list(range(1, len(phases) + 1)))
        for phase in phases:
            for key in (
                "name",
                "git_commit_boundary",
                "reviewer_gate",
                "tester_gate",
                "rollback",
            ):
                self.assertIsInstance(phase[key], str)
                self.assertTrue(phase[key].strip(), f"{phase['id']} missing {key}")
        self.assertEqual(phases[0]["runtime_moves"], False)

    def test_experiments_have_baseline_benchmark_metrics_and_stop_rule(self) -> None:
        experiments = self.manifest.get("experiments", [])
        self.assertEqual([item["id"] for item in experiments], ["extractor-consolidation"])
        for experiment in experiments:
            for key in ("design_choice", "baseline", "benchmark", "stop_rule"):
                self.assertIsInstance(experiment[key], str)
                self.assertTrue(experiment[key].strip())
            self.assertIsInstance(experiment["metrics"], list)
            self.assertTrue(experiment["metrics"])

    def test_group_schema_enums_and_unique_ids(self) -> None:
        groups = self.manifest["groups"]
        ids = [group["id"] for group in groups]
        self.assertEqual(len(ids), len(set(ids)))
        phase_ids = {phase["id"] for phase in self.manifest["phases"]}
        for group in groups:
            self.assertIn(group["classification"], CLASSIFICATIONS)
            self.assertIn(group["phase"], phase_ids)
            self.assertIn(group["source_state"], SOURCE_STATES)
            self.assertIsInstance(group["source"], list)
            self.assertTrue(group["source"])
            self.assertIn("target", group)
            self.assertIsInstance(group["owner"], str)
            self.assertTrue(group["owner"].strip())
            for key in ("preconditions", "acceptance", "rollback", "reference_updates"):
                self.assertIsInstance(group[key], list)
                self.assertTrue(group[key], f"{group['id']} missing {key}")

    def test_present_sources_exist_and_generated_or_optional_are_explicit(self) -> None:
        for group in self.manifest["groups"]:
            for source in group["source"]:
                _parts(source)
                exists = (ROOT / Path(*PurePosixPath(source).parts)).exists()
                if group["source_state"] == "present":
                    self.assertTrue(exists, f"missing source in {group['id']}: {source}")
                else:
                    self.assertTrue(group.get("optional", False), group["id"])

    def test_sources_do_not_overlap_across_groups(self) -> None:
        claimed: list[tuple[str, str]] = []
        for group in self.manifest["groups"]:
            for source in group["source"]:
                for prior_source, prior_group in claimed:
                    overlap = _contains(source, prior_source) or _contains(prior_source, source)
                    self.assertFalse(
                        overlap,
                        f"source overlap is not allowed: {group['id']}:{source} and "
                        f"{prior_group}:{prior_source}",
                    )
                claimed.append((source, group["id"]))

    def test_targets_are_contained_by_classification(self) -> None:
        canonical = self.manifest["canonical_root"]
        legacy = self.manifest["legacy_root"]
        for group in self.manifest["groups"]:
            target = group["target"]
            classification = group["classification"]
            if classification == "GENERATED_CLEANUP":
                self.assertIsNone(target)
                continue
            self.assertIsInstance(target, str)
            _parts(target)
            if classification == "ARCHIVE_AFTER_MIGRATION":
                self.assertTrue(_contains(legacy, target), group["id"])
            elif classification in {"ACTIVE_MOVE", "ACTIVE_ADAPTER", "DEFERRED"}:
                self.assertTrue(_contains(canonical, target), group["id"])

    def test_keep_shared_never_targets_legacy(self) -> None:
        legacy = self.manifest["legacy_root"]
        for group in self.manifest["groups"]:
            if group["classification"] == "KEEP_SHARED":
                self.assertFalse(_contains(legacy, group["target"]), group["id"])


if __name__ == "__main__":
    unittest.main()
