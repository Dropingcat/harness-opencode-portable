#!/usr/bin/env python3
"""test_claim_classifier.py — реальные тесты классификатора claim-типов.

Использует реальные claims «Актуальности» (claims.json, 12 claims):
  - C9 (данные отсутствуют) и C11 (остаётся нерешённой задачей) → gap;
  - C3 (наблюдается ускорение) → attribute;
  - числовые claims → numeric.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from claim_classifier import classify

CLAIMS_PATH = Path("/tmp/abstract_test/compare/claims.json")
CLAIMS = {}
if CLAIMS_PATH.is_file():
    data = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    for c in data.get("claims", {}).get("validated", []):
        CLAIMS[str(c.get("original_index"))] = c.get("text", "")


def _claim(idx):
    return CLAIMS.get(str(idx), "")


def test_c11_is_gap():
    """C11 «остаётся нерешённой задачей» → gap."""
    assert _claim(11)
    res = classify(_claim(11))
    assert res["claim_class"] == "gap"
    assert any("нерешён" in m or "нерешен" in m or "задач" in m for m in res["markers_found"])


def test_c9_is_gap():
    """C9 «данные... отсутствуют» → gap."""
    assert _claim(9)
    res = classify(_claim(9))
    assert res["claim_class"] == "gap"
    assert any("отсутств" in m for m in res["markers_found"])


def test_c3_is_attribute():
    """C3 «наблюдается ускорение...» → attribute (эмпирическое наблюдение)."""
    assert _claim(3)
    res = classify(_claim(3))
    assert res["claim_class"] == "attribute"
    assert "наблюдается" in res["markers_found"]


def test_c4_is_attribute():
    """C4 «заложены в работах» → attribute (авторство)."""
    assert _claim(4)
    res = classify(_claim(4))
    assert res["claim_class"] == "attribute"


def test_numeric_claim():
    """Claim с числами (твёрдость HV) → numeric."""
    res = classify("Твёрдость азотированного слоя достигает 1000-1200 HV для легированных сталей.")
    assert res["claim_class"] == "numeric"
    assert res["has_numbers"] is True


def test_framing_claim():
    """C0 «фундаментальная задача» → framing (не gap)."""
    assert _claim(0)
    res = classify(_claim(0))
    assert res["claim_class"] == "framing"
    assert any("фундаментальная" in m for m in res["markers_found"])


def test_all_twelve_claims_classifiable():
    """Все 12 claims классифицируются без ошибок."""
    for idx in range(12):
        res = classify(_claim(idx))
        assert res["claim_class"] in ("gap", "attribute", "numeric", "framing")


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))