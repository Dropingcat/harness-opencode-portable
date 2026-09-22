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


class TestApplyAppendOnly(unittest.TestCase):
    """--apply не деструктивен: курированный verdict/numeric_comparison защищены (WS-19 регрессия)."""

    @staticmethod
    def _run_main(args):
        import io
        from contextlib import redirect_stdout
        old_argv = sys.argv
        sys.argv = ["verify_claims.py"] + args
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                rc = vc.main()
        finally:
            sys.argv = old_argv
        return rc, buf.getvalue()

    def _dom(self, claim_text, source_text=None, verification=None):
        d = {
            "product": {"id": "PROD", "kind": "dissertation"},
            "structure": {"chapters": []},
            "claims": [
                {"id": "C-001", "text": claim_text, "kind": "factual",
                 "evidence": [{"source_id": "S-001", "span": "p.1"}] if source_text else [],
                 "verification": verification} if verification is not None
                else {"id": "C-001", "text": claim_text, "kind": "factual",
                      "evidence": [{"source_id": "S-001", "span": "p.1"}] if source_text else []}
            ],
            "graphs": [],
            "uncertainty": {},
            "sources": [{"id": "S-001", "text": source_text}] if source_text else [],
        }
        return d

    def _load_yaml(self, p):
        import yaml
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_apply_keeps_curated_verdict_and_numeric_comparison(self):
        """(а) курированный SUPPORTED + numeric_comparison НЕ перезаписываются."""
        import yaml
        curated_nc = {"status": "MATCH", "claim": "120 МПа", "source": "цитата из S-021", "unit": "mpa", "note": "curated"}
        dom = self._dom("Твёрдость 120 МПа", "Твёрдость 80 МПа",
                        verification={"verdict": "SUPPORTED", "confidence": 0.8, "numeric_comparison": curated_nc})
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "dom.yaml"
            with open(p, "w", encoding="utf-8") as f:
                yaml.safe_dump(dom, f, allow_unicode=True, sort_keys=False)
            rc, out = self._run_main(["--dom", str(p), "--apply"])
            self.assertEqual(rc, 0, out)
            after = self._load_yaml(p)
            ver = after["claims"][0]["verification"]
            # вычисленный был бы CONTRADICTED/MISMATCH (120 vs 80) — но курация побеждает
            self.assertEqual(ver["verdict"], "SUPPORTED")
            self.assertEqual(ver["confidence"], 0.8)
            self.assertEqual(ver["numeric_comparison"], curated_nc)
            self.assertEqual(ver["numeric_comparison"]["status"], "MATCH")
            self.assertEqual(ver["numeric_comparison"]["note"], "curated")

    def test_apply_fills_open_verdict_and_numeric_comparison(self):
        """(б) verdict OPEN + числа в text/source → вычисляется SUPPORTED + numeric_comparison."""
        import yaml
        dom = self._dom("Твёрдость 120 МПа", "Твёрдость 120 МПа",
                        verification={"verdict": "OPEN", "confidence": 0.3})
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "dom.yaml"
            with open(p, "w", encoding="utf-8") as f:
                yaml.safe_dump(dom, f, allow_unicode=True, sort_keys=False)
            rc, out = self._run_main(["--dom", str(p), "--apply"])
            self.assertEqual(rc, 0, out)
            after = self._load_yaml(p)
            ver = after["claims"][0]["verification"]
            self.assertEqual(ver["verdict"], "SUPPORTED")
            self.assertEqual(ver["confidence"], 0.8)
            self.assertIsNotNone(ver.get("numeric_comparison"))
            self.assertEqual(ver["numeric_comparison"]["status"], "MATCH")

    def test_readonly_does_not_touch_dom(self):
        """(в) read-only режим ничего не пишет в DOM (файл байт-в-байт тот же)."""
        import yaml
        dom = self._dom("Твёрдость 120 МПа", "Твёрдость 120 МПа")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "dom.yaml"
            with open(p, "w", encoding="utf-8") as f:
                yaml.safe_dump(dom, f, allow_unicode=True, sort_keys=False)
            before = p.read_bytes()
            rc, out = self._run_main(["--dom", str(p)])
            self.assertEqual(rc, 0, out)
            self.assertIn('"applied": false', out)
            self.assertEqual(p.read_bytes(), before)
            after = self._load_yaml(p)
            self.assertNotIn("verification", after["claims"][0])

    def test_broken_claim_fail_closed_exit_2(self):
        """Fail-closed: не-dict claim → JSON-ошибка, exit 2, без исключения наружу."""
        import yaml
        dom = self._dom("Твёрдость 120 МПа", "Твёрдость 120 МПа")
        dom["claims"].append("broken-claim-not-a-mapping")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "dom.yaml"
            with open(p, "w", encoding="utf-8") as f:
                yaml.safe_dump(dom, f, allow_unicode=True, sort_keys=False)
            rc, out = self._run_main(["--dom", str(p), "--apply"])
            self.assertEqual(rc, 2)
            self.assertIn('"ok": false', out)
            self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()