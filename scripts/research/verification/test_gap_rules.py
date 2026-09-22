#!/usr/bin/env python3
"""test_gap_rules.py — реальные тесты gap-правил.

Проверяет (verification-plan.md B.4/A.2):
  - gap-claim: UNSUPPORTED НЕ становится problematic автоматом;
  - gap-claim: UNSUPPORTED (низкая уверенность) → GAP-UNVERIFIED;
  - gap-claim: внешние источники подтверждают пробел → SUPPORTED(gap);
  - gap-claim: внешний источник опровергает пробел → CONTRADICTED;
  - UNSUPPORTED + confidence>0.6 → cap до 0.5 (unsupported_conf_contradiction);
  - non-gap claim: cap-правило тоже применяется, gap-конверсия — нет.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from gap_rules import (
    cap_unsupported_high_conf,
    decide_gap_verdict,
    apply_gap_policy,
    is_gap_supported_by_source,
    is_gap_contradicted_by_source,
)

C11 = ("Разделение вкладов, обусловленных предварительными обработками "
       "(микродеформациями, дефектной субструктурой), в кинетику роста "
       "азотированного слоя остаётся нерешённой задачей.")


def _mk(verdict="UNSUPPORTED", conf=0.3):
    return {"claim_id": 11, "claim_text": C11, "verdict": verdict, "confidence": conf}


def test_gap_claim_not_problematic():
    """gap-claim: verdict_unsupported→problematic не применяется автоматом."""
    v = _mk()
    v["problematic"] = True
    v["_problematic_reason"] = "verdict_unsupported"
    out, changes = apply_gap_policy(v, "gap")
    assert out.get("problematic") is not True
    assert any("problematic" in c for c in changes)


def test_gap_claim_unsupported_becomes_gap_unverified():
    """gap-claim: UNSUPPORTED с низкой уверенностью → GAP-UNVERIFIED."""
    v = _mk("UNSUPPORTED", 0.3)
    out, changes = apply_gap_policy(v, "gap")
    assert out["verdict"] == "GAP-UNVERIFIED"
    assert out.get("_gap_claim") is True
    assert any("GAP-UNVERIFIED" in c for c in changes)


def test_unsupported_high_conf_capped():
    """UNSUPPORTED + confidence 0.9 → cap 0.5 (unsupported_conf_contradiction)."""
    v = _mk("UNSUPPORTED", 0.9)
    out, capped = cap_unsupported_high_conf(v, threshold=0.6, cap_value=0.5)
    assert capped is True
    assert out["confidence"] == 0.5
    assert out["_capped_by"] == "unsupported_conf_contradiction"
    assert out["_original_confidence"] == 0.9


def test_unsupported_high_conf_via_policy_gap():
    """Полный цикл для gap: UNSUPPORTED 0.9 → cap 0.5 + GAP-UNVERIFIED (не 0.9)."""
    v = _mk("UNSUPPORTED", 0.9)
    out, changes = apply_gap_policy(v, "gap")
    assert out["confidence"] == 0.5
    assert out["_capped_by"] == "unsupported_conf_contradiction"
    assert out["verdict"] == "GAP-UNVERIFIED"
    # пара UNSUPPORTED/0.9 снята: уверенность не выше 0.5
    assert out["confidence"] <= 0.5


def test_gap_supported_by_external():
    """Внешний источник подтверждает пробел → SUPPORTED(gap)."""
    res = decide_gap_verdict(
        [{"title": "review"}],
        gap_support_hits=1,
        gap_contradictions=0,
    )
    assert res["verdict"] == "SUPPORTED"
    assert res["gap_supported"] is True


def test_gap_contradicted_by_external():
    """Внешний источник прямо утверждает решение → CONTRADICTED."""
    res = decide_gap_verdict(
        [{"title": "paper"}],
        gap_support_hits=0,
        gap_contradictions=1,
    )
    assert res["verdict"] == "CONTRADICTED"
    assert res["gap_contradicted"] is True


def test_gap_unverified_when_no_sources():
    """Ничего не найдено → GAP-UNVERIFIED (НЕ голый UNSUPPORTED)."""
    res = decide_gap_verdict([], gap_support_hits=0, gap_contradictions=0)
    assert res["verdict"] == "GAP-UNVERIFIED"
    assert res["reason"]  # причина объясняет различие с UNSUPPORTED


def test_gap_marker_sources():
    """Реальные фразы: обзор про нерешённую задачу поддерживает пробел."""
    assert is_gap_supported_by_source(
        "Разделение вкладов остаётся нерешённой задачей, требуются дальнейшие исследования"
    ) is True
    assert is_gap_contradicted_by_source(
        "Данная задача полностью решена в работах 2023 года"
    ) is True


def test_non_gap_claim_not_converted():
    """non-gap: UNSUPPORTED 0.3 остаётся UNSUPPORTED (без GAP-конверсии)."""
    v = _mk("UNSUPPORTED", 0.3)
    out, changes = apply_gap_policy(v, "framing")
    assert out["verdict"] == "UNSUPPORTED"
    assert not any("GAP-UNVERIFIED" in c for c in changes)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))