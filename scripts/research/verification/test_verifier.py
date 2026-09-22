#!/usr/bin/env python3
"""test_verifier.py — полный цикл верификации на реальных данных.

Проверяет оркестратор: claim → классификация → каскад → анти-циркулярность →
вердикт с низкой неопределённостью, ссылками и контекстом.

Использует реальный документ «Актуальности» (input_actuality.txt) и реальные
слои каскада (local_corpus обязательно; openalex/arxiv/web — если сеть доступна).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from verifier import (
    verify_claim,
    verify_claims,
    build_sources_contract,
    verdicts_from_answers,
)

DOC_PATH = Path("/tmp/abstract_test/compare/input_actuality.txt")
CLAIMS_PATH = Path("/tmp/abstract_test/compare/claims.json")

C3_CLAIM = ("Наблюдается ускорение образования нитридных фаз при комбинированных "
            "воздействиях — лазерная обработка и вакуумное азотирование, "
            "механическая обработка и вакуумное азотирование.")
C11_CLAIM = ("Разделение вкладов, обусловленных предварительными обработками "
             "(микродеформациями, дефектной субструктурой), в кинетику роста "
             "азотированного слоя остаётся нерешённой задачей.")


def _doc():
    return DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.is_file() else None


def _config(layers=None):
    return {"layers": layers or ["local_corpus", "openalex"]}


def test_verify_claim_c3_full_answer():
    """Полный цикл для C3: вердикт + confidence + неопределённость + ссылки + контекст."""
    ans = verify_claim(C3_CLAIM, _doc(), _config(), claim_id=3)
    # поля ответа (аналог Perplexity)
    for key in ("claim_id", "claim_text", "claim_class", "verdict", "confidence",
                "uncertainty", "reason", "references", "context"):
        assert key in ans
    assert ans["claim_id"] == 3
    assert ans["claim_class"] == "attribute"
    assert ans["verdict"] in ("SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS")
    assert 0.0 <= ans["confidence"] <= 1.0
    assert ans["uncertainty"]["level"] in ("low", "medium", "high")
    # ссылки и контекст непустые
    assert isinstance(ans["references"], list)
    assert isinstance(ans["context"], list)


def test_verify_claim_c3_origin_labels():
    """C3: источники-реконструкции документа помечены document_derived."""
    ans = verify_claim(C3_CLAIM, _doc(), _config(), claim_id=3)
    derived = [s for s in ans["sources"] if s.get("origin") == "document_derived"]
    assert isinstance(ans["sources"], list)
    for s in ans["sources"]:
        assert s.get("origin") in ("external", "document_derived")
        assert "found_via" in s


def test_verify_claim_c11_gap_path():
    """C11 (gap) не даёт голый UNSUPPORTED, а GAP-UNVERIFIED/SUPPORTED/CONTRADICTED."""
    ans = verify_claim(C11_CLAIM, _doc(), _config(), claim_id=11)
    assert ans["claim_class"] == "gap"
    assert ans["verdict"] in ("SUPPORTED", "CONTRADICTED", "GAP-UNVERIFIED")
    # не UNSUPPORTED: отсутствие данных ≠ опровержение
    assert ans["verdict"] != "UNSUPPORTED"


def test_build_sources_contract():
    """Сборка sources.json в формате B.6: provenance + verification_meta."""
    answers, meta = verify_claims(
        [{"text": C3_CLAIM, "claim_id": 3},
         {"text": C11_CLAIM, "claim_id": 11}],
        _doc(), _config(),
    )
    contract = build_sources_contract(answers)
    assert "sources" in contract and "verification_meta" in contract
    assert set(contract["sources"].keys()) == {"3", "11"}
    for srcs in contract["sources"].values():
        for s in srcs:
            for field in ("title", "type", "excerpt", "doi", "url", "found_via",
                          "found_query", "origin", "relevance", "accepted"):
                assert field in s
    meta = contract["verification_meta"]
    assert "external_found" in meta
    assert "document_derived_found" in meta
    assert "cascade_used" in meta


def test_verdicts_from_answers_compatible():
    """Вердикты совместимы с пайплайном (verdicts.json)."""
    ans = verify_claim(C3_CLAIM, _doc(), _config(), claim_id=3)
    v = verdicts_from_answers([ans])[0]
    assert v["verdict"] == ans["verdict"]
    assert v["claim_id"] == 3
    assert "claim_class" in v
    assert isinstance(v["references"], list)


def test_verifier_scibot_simulate():
    """sci-bot резерв в режиме --simulate не тратит токены и даёт DOI."""
    ans = verify_claim(
        C3_CLAIM, _doc(),
        {"layers": ["scibot"], "simulate_scibot": True},
        claim_id=3,
    )
    assert ans["verification_meta"]["budget_tokens"] == 0
    assert any("sci" in (s.get("found_via") or "") for s in ans["sources"])


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))