from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from registry_loader import Registries  # noqa: E402
from rtt_compare import compare, compare_contract  # noqa: E402
from writer_core.factory_process import run_writer_cycle  # noqa: E402


class RoundTripFixtureTests(unittest.TestCase):
    def test_four_handoff_fixtures(self) -> None:
        fixture_dir = ROOT / "tests" / "fixtures" / "roundtrip"
        for path in sorted(fixture_dir.glob("*.yaml")):
            with self.subTest(path=path.name):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                result = compare_contract(data["contract_claim"], data["realization"])
                self.assertEqual(data["expected"]["verdict"], result.verdict)
                self.assertEqual(
                    data["expected"]["reason_codes"],
                    [reason.value for reason in result.reason_codes],
                )

    def test_selected_golden_traps_have_stable_codes(self) -> None:
        path = ROOT / "tests" / "fixtures" / "linguistics" / "golden_traps.yaml"
        fixtures = yaml.safe_load(path.read_text(encoding="utf-8"))["fixtures"]
        runnable = [case for case in fixtures if case.get("mutation")]
        for case in runnable:
            with self.subTest(case=case["id"]):
                codes = {reason.value for reason in compare(case["source"], case["mutation"]).reason_codes}
                self.assertIn(case["expected_issue"], codes)


class RegistryBoundaryTests(unittest.TestCase):
    def test_all_six_runtime_registries_load(self) -> None:
        registries = Registries()
        self.assertTrue(registries.lexicon)
        self.assertTrue(registries.connectives)
        self.assertTrue(registries.frames)
        self.assertTrue(registries.patterns)
        self.assertTrue(registries.actions)
        self.assertTrue(registries.valency)

    def test_duplicate_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "assets"
            shutil.copytree(ROOT / "linguistic_assets", target)
            path = target / "connective_registry.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["entries"].append(dict(data["entries"][0]))
            path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate form"):
                Registries(str(target))

    def test_missing_required_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "assets"
            shutil.copytree(ROOT / "linguistic_assets", target)
            path = target / "valency_registry.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            del data["entries"][0]["case"]
            path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing"):
                Registries(str(target))


class BoundedRepairTests(unittest.TestCase):
    @patch("writer_core.factory_process.apply_constrained_repair")
    @patch("writer_core.factory_process.draftcheck")
    def test_no_progress_stops_without_retry_loop(self, draftcheck, repair) -> None:
        draftcheck.return_value = {
            "verdict": "FAIL",
            "defects": [{"claim_id": "C1", "defect_type": "claim_omission", "span": None}],
        }
        repair.return_value = {"text": "draft", "applied": [], "skipped": []}
        result = run_writer_cycle("draft", [], max_iterations=5)
        self.assertEqual("REJECTED", result["verdict"])
        self.assertEqual("no_progress", result["stopped_reason"])
        self.assertEqual(1, draftcheck.call_count)

    @patch("writer_core.factory_process.draftcheck")
    def test_iteration_limit_is_bounded(self, draftcheck) -> None:
        draftcheck.return_value = {"verdict": "FAIL", "defects": []}
        result = run_writer_cycle("draft", [], max_iterations=0)
        self.assertEqual("iteration_limit", result["stopped_reason"])
        self.assertEqual(1, draftcheck.call_count)


if __name__ == "__main__":
    unittest.main()
