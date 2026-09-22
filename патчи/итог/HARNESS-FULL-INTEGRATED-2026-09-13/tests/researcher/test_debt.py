from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from researcher_core.debt import build_report, iter_files, scan_paths
from researcher_core.policy import PolicyConfigurationError, lint_policy_text, load_bootstrap_policy


class DebtScannerTests(unittest.TestCase):
    def test_debt_scan_detects_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.py"
            sample.write_text(
                "def unfinished():\n"
                f"    # {'TO' + 'DO'}: document policy key\n"
                "    pass\n"
                "def heuristic():\n"
                "    return 5\n",
                encoding="utf-8",
            )

            findings = scan_paths([sample], root)
            kinds = {finding.kind for finding in findings}

            self.assertIn("todo_marker", kinds)
            self.assertIn("pass_statement", kinds)
            self.assertIn("possible_magic_number", kinds)

    def test_debt_report_counts_by_severity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.md"
            sample.write_text(f"{'FIX' + 'ME'}: shortcut simplification\n", encoding="utf-8")

            report = build_report(root, scan_paths([sample], root))

            self.assertGreaterEqual(report["total"], 1)
            self.assertTrue(report["counts"])

    def test_debt_config_excludes_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "debt-report.json"
            report.write_text(f"{'TO' + 'DO'}: old finding\n", encoding="utf-8")

            files = list(iter_files(root, excluded_files=frozenset({"debt-report.json", "artifact-gap-report.json"})))

            self.assertEqual(files, [])

    def test_debt_config_excludes_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preprint = root / "preprint"
            preprint.mkdir()
            sample = preprint / "build_appendix.py"
            sample.write_text("font_size = 9\n", encoding="utf-8")

            files = list(iter_files(root, excluded_dirs=frozenset({"preprint"})))

            self.assertEqual(files, [])

    def test_missing_policy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PolicyConfigurationError):
                load_bootstrap_policy(Path(tmp))

    def test_policy_lint_requires_heuristic_metadata(self) -> None:
        text = "heuristics:\n  debt.scan.default_fail_on:\n    value:\n      - critical\n"

        with self.assertRaises(PolicyConfigurationError):
            lint_policy_text(text)

    def test_limits_and_timeouts_are_policy_debt_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.py"
            sample.write_text("max_sources_limit = 20\ntimeout_seconds = 30\n", encoding="utf-8")

            findings = scan_paths([sample], root)

            self.assertEqual(len(findings), 2)  # debt-scan: ignore-line -- bubble test expects two policy-debt findings.


if __name__ == "__main__":
    unittest.main()
