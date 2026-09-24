"""TD-D8: тесты гейта check_evidence_levels (инварианты I1–I6, мутации)."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "tools" / "check_evidence_levels.py"
COMPAT = ROOT / "compatibility" / "opencode" / "1.18.30.json"

sys.path.insert(0, str(GATE.parent))
import check_evidence_levels as gate  # noqa: E402


def base_doc():
    return json.loads(COMPAT.read_text(encoding="utf-8"))


class TestGateOnRepo(unittest.TestCase):
    def test_gate_passes_on_repository(self):
        """Реальный compatibility-файл проходит гейт (exit 0)."""
        r = subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        self.assertIn("GATE PASS", r.stdout)

    def test_no_legacy_tokens_in_json(self):
        raw = COMPAT.read_text(encoding="utf-8")
        for tok in gate.LEGACY_TOKENS:
            self.assertNotIn(tok, raw, f"устаревший токен {tok!r} должен быть удалён (TD-D8)")

    def test_live_certified_subset_of_documented_probes(self):
        doc = base_doc()
        allowed = set(doc["evidence_scale"]["allowed_live_certified"])
        live = {k for k, v in doc["feature_probes"].items() if v["level"] == "LIVE_CERTIFIED"}
        self.assertTrue(live)
        self.assertLessEqual(live, allowed)
        # понижённые по ревью уровни:
        self.assertEqual(doc["feature_probes"]["SDK_CLIENT_AVAILABLE"]["level"], "TYPE_VERIFIED")
        self.assertEqual(doc["feature_probes"]["BRIDGE_FULL_DUPLEX"]["level"], "HOSTLESS_REPORTED")
        self.assertEqual(doc["semantic_status"], "NOT_CERTIFIED")


class TestMutations(unittest.TestCase):
    """Каждая мутация обязана порождать нарушение соответствующего инварианта."""

    def _errors(self, doc):
        return gate.check(doc, json.dumps(doc, ensure_ascii=False))

    def test_mutation_I1_string_probe(self):
        doc = base_doc()
        doc["feature_probes"]["PLUGIN_LOADED"] = "LIVE_VERIFIED style string"
        self.assertTrue(any(e.startswith("I1") for e in self._errors(doc)))

    def test_mutation_I2_unknown_level(self):
        doc = base_doc()
        doc["feature_probes"]["HOST_CONTEXT"]["level"] = "ALMOST_LIVE"
        self.assertTrue(any(e.startswith("I2") for e in self._errors(doc)))

    def test_mutation_I3_legacy_token(self):
        doc = base_doc()
        doc["notes"] = "previously LIVE_VERIFIED"
        self.assertTrue(any(e.startswith("I3") for e in self._errors(doc)))

    def test_mutation_I4_unapproved_live(self):
        doc = base_doc()
        doc["feature_probes"]["SESSION_CREATE"]["level"] = "LIVE_CERTIFIED"
        errs = self._errors(doc)
        self.assertTrue(any(e.startswith("I4") and "SESSION_CREATE" in e for e in errs))

    def test_mutation_I5_missing_evidence_file(self):
        doc = base_doc()
        doc["feature_probes"]["PLUGIN_LOADED"]["evidence"] = ["does/not/exist.md#anchor"]
        self.assertTrue(any(e.startswith("I5") for e in self._errors(doc)))

    def test_mutation_I5_live_without_evidence(self):
        doc = base_doc()
        doc["feature_probes"]["WORKSPACE_CONTEXT"]["evidence"] = []
        self.assertTrue(any(e.startswith("I5") for e in self._errors(doc)))

    def test_mutation_I6_semantic_consistency(self):
        doc = base_doc()
        doc["feature_probes"]["STRUCTURED_OUTPUT"]["level"] = "LIVE_CERTIFIED"
        doc["feature_probes"]["STRUCTURED_OUTPUT"]["evidence"] = [
            "packages/opencode-harness-plugin/P1_STATUS.md"
        ]
        doc["evidence_scale"]["allowed_live_certified"].append("STRUCTURED_OUTPUT")
        errs = self._errors(doc)
        self.assertTrue(any(e.startswith("I6") for e in errs), msg=str(errs))

    def test_clean_copy_has_no_errors(self):
        self.assertEqual(self._errors(copy.deepcopy(base_doc())), [])


if __name__ == "__main__":
    unittest.main()
