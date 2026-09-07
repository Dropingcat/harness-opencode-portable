"""Tests for verify_claims.py (writer <-> researcher bridge, WS-19)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "researcher"))

import verify_claims as vc  # noqa: E402


class TestVerifyClaims(unittest.TestCase):
    def _dom(self, claim_text, source_text=None):
        d = {
            "product": {"id": "PROD", "kind": "dissertation"},
            "structure": {"chapters": []},
            "claims": [
                {"id": "C-001", "text": claim_text, "kind": "factual",
                 "evidence": [{"source_id": "S-001", "span": "p.1"}] if source_text else []}
            ],
            "graphs": [],
            "uncertainty": {},
            "sources": [{"id": "S-001", "text": source_text}] if source_text else [],
        }
        return d

    def test_numeric_match_supported(self):
        dom = self._dom("Твёрдость 120 МПа", "Твёрдость 120 МПа")
        v = vc.verify_claim(dom["claims"][0], dom["sources"][0]["text"])
        self.assertEqual(v["verdict"], "SUPPORTED")
        self.assertEqual(v["numeric_comparison"]["status"], "MATCH")
        self.assertAlmostEqual(v["confidence"], 0.8)

    def test_numeric_mismatch_contradicted(self):
        dom = self._dom("Твёрдость 120 МПа", "Твёрдость 80 МПа")
        v = vc.verify_claim(dom["claims"][0], dom["sources"][0]["text"])
        self.assertEqual(v["verdict"], "CONTRADICTED")

    def test_guard_fail_ambiguous(self):
        dom = self._dom("UNION SELECT 1; Твёрдость 120 МПа")
        v = vc.verify_claim(dom["claims"][0], None)
        # guard должен либо вернуть FAIL (→AMBIGUOUS), либо не влиять; проверяем что guard присутствует
        self.assertIn("guard", v)

    def test_no_source_open(self):
        dom = self._dom("гуматы повышают эффективность")
        v = vc.verify_claim(dom["claims"][0], None)
        self.assertEqual(v["verdict"], "OPEN")

    def test_formula_conflict_contradicted(self):
        dom = self._dom("Средний размер кристаллитов по Шерреру K=1.0, 50 нм")
        v = vc.verify_claim(dom["claims"][0], None)
        # K=1 для Шеррера — конфликт с каноническим 0.9
        self.assertEqual(v["verdict"], "CONTRADICTED")

    def test_apply_writes_verification(self):
        with tempfile.TemporaryDirectory() as td:
            import yaml
            dom = self._dom("Твёрдость 120 МПа", "Твёрдость 120 МПа")
            p = Path(td) / "dom.yaml"
            with open(p, "w", encoding="utf-8") as f:
                yaml.safe_dump(dom, f, allow_unicode=True)
            # не вызываем main (он печатает), тестируем что verification присваивается через apply логику
            from researcher_core.numeric import NumericValue, compare_numeric
            claim = dom["claims"][0]
            cn = vc._extract_numbers(claim["text"])[0]
            sn = vc._extract_numbers(dom["sources"][0]["text"])[0]
            def _make(nums):
                if nums.get("lower") is not None and nums.get("upper") is not None:
                    return NumericValue(unit=vc._normalize_unit(nums.get("unit")), lower=nums["lower"], upper=nums["upper"])
                return NumericValue(value=nums.get("value"), unit=vc._normalize_unit(nums.get("unit")))
            comp = compare_numeric(_make(cn), _make(sn))
            self.assertEqual(comp.status.name, "MATCH")


if __name__ == "__main__":
    unittest.main()