from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from researcher_core.policy import PolicyConfigurationError, compute_policy_hash_for_text, load_policy, lint_policy_text


class PolicyProdTests(unittest.TestCase):
    def test_policy_loads_real_file_returns_hash_and_reason_codes(self) -> None:
        policy = load_policy(Path.cwd())
        self.assertTrue(policy.policy_hash.startswith("sha256:"))
        self.assertIn("CLAIM_EVIDENCE_UPDATED", policy.reason_codes)
        self.assertIn("debt.scan.default_fail_on", policy.heuristics)
        self.assertEqual(policy.debt_fail_on, "critical")
        self.assertIn("debt-report.json", policy.debt_excluded_files)

    def test_policy_hash_is_stable_for_same_content(self) -> None:
        text = (Path.cwd() / "config" / "research_policy.yaml").read_text(encoding="utf-8")
        first = compute_policy_hash_for_text(text)
        second = compute_policy_hash_for_text(text)
        self.assertEqual(first, second)
        policy = load_policy(Path.cwd())
        self.assertEqual(policy.policy_hash, first)

    def test_policy_rejects_missing_heuristic_field(self) -> None:
        text = (
            "schema_version: research-policy/0.1\n"
            "policy_id: test\n"
            "policy_version: 0.1.0\n"
            "reason_codes:\n"
            "  CLAIM_EVIDENCE_UPDATED:\n"
            "    description: ok\n"
            "    owner: test\n"
            "    tests: [t]\n"
            "heuristics:\n"
            "  debt.scan.default_fail_on:\n"
            "    value:\n"
            "      - critical\n"
            "    unit: severity_list\n"
            "    applies_to: [developer_workflow]\n"
            "    reason: test\n"
            "    introduced_in: 0.0.1\n"
            "    review_after: {runs: 20}\n"
            "    failure_if_wrong: [x]\n"
            "    tests: [t]\n"
        )
        with self.assertRaises(PolicyConfigurationError):
            lint_policy_text(text)

    def test_bootstrap_still_exposes_debt_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "config"
            config_dir.mkdir()
            source = (Path.cwd() / "config" / "research_policy.yaml").read_text(encoding="utf-8")
            (config_dir / "research_policy.yaml").write_text(source, encoding="utf-8")
            policy = load_policy(root)
            self.assertEqual(policy.debt_fail_on, "critical")
            self.assertGreater(len(policy.debt_excluded_dirs), 1)


if __name__ == "__main__":
    unittest.main()
