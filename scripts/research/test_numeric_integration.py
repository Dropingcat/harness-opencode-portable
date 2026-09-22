"""Интеграционные тесты: numeric_comparator + units + uncertainty + formulas."""
import json

import pytest

from numeric_comparator import (
    _normalize_groups,
    _extract_sources_index,
    _lookup_sources,
    extract_numbers,
    compare_single,
    compare_claim_sources,
)
from formulas import detect_formula


def test_extract_uncertainty():
    nums = extract_numbers("размер 77 ± 3 мм")
    assert nums
    assert nums[0]["uncertainty"] == pytest.approx(3.0)
    assert nums[0]["value"] == pytest.approx(77.0)


def test_compare_single_with_uncertainty():
    assert compare_single(77, 78, claim_unc=3, source_unc=1) == "match"


def test_compare_single_with_uncertainty_mismatch():
    assert compare_single(77, 65, claim_unc=3, source_unc=1) == "mismatch"


def test_integration_convertible_units():
    claim = {"claim_id": 1, "claim_text": "температура 540 °C"}
    source = {"title": "src", "numbers": [{"type": "single", "value": 813, "unit": "K", "raw": "813 K"}]}
    res = compare_claim_sources(claim, [source])
    assert res["status"] != "not_comparable"
    assert res["status"] in ("match", "partial_match")


def test_integration_dimension_mismatch():
    # Слой 3: разноразмерные пары (мм vs см²/с) → not_comparable, не dimension-вердикт
    claim = {"claim_id": 2, "claim_text": "размер 77 мм"}
    source = {"title": "src", "numbers": [{"type": "single", "value": 5, "unit": "см²/с", "raw": "5 см²/с"}]}
    res = compare_claim_sources(claim, [source])
    assert res["status"] == "not_comparable"


def test_formula_detection():
    assert detect_formula("по Шерреру") == "scherrer"


def test_formula_conflict_sets_mismatch():
    claim = {"claim_id": 3, "claim_text": "D = λ/(βcosθ), K=1 по Шерреру"}
    source = {"title": "src", "numbers": [{"type": "single", "value": 1, "unit": "", "raw": "1"}]}
    res = compare_claim_sources(claim, [source])
    assert res["formula"] is not None
    assert res["formula"]["name"] == "scherrer"
    assert res["formula"]["constant_check"] == "formula_conflict"
    assert res["status"] == "mismatch"


# ─────────────────── регрессия: нормализация входных групп ───────────────────

FLAT = [
    {"claim_id": 1, "claim_text": "температура 540 °C", "sources": []},
    {"claim_id": 2, "claim_text": "размер 77 ± 3 мм", "sources": []},
]


def test_normalize_flat_list():
    groups = _normalize_groups(FLAT)
    assert len(groups) == 2
    assert groups[0]["original_index"] is None
    assert groups[0]["claim_id"] == 1
    assert groups[0]["claims"] == ["температура 540 °C"]
    assert groups[0]["_flat_verdict"] is FLAT[0]


def test_normalize_dict_with_verdicts():
    groups = _normalize_groups({"status": "success", "verdicts": FLAT})
    assert len(groups) == 2
    assert groups[0]["claim_id"] == 1


def test_normalize_dict_with_groups():
    groups = _normalize_groups({"groups": [
        {"original_index": 5, "claims": ["10-50 hours"]},
        {"original_index": 17, "claims": ["77 кДж/моль"]},
    ]})
    assert len(groups) == 2
    assert groups[0]["original_index"] == 5
    assert groups[0]["claims"] == ["10-50 hours"]


def test_normalize_dict_without_verdicts_single_verdict():
    groups = _normalize_groups({"claim_id": 9, "claim_text": "0.3-0.6 мм"})
    assert len(groups) == 1
    assert groups[0]["claim_id"] == 9


def test_normalize_empty_and_none():
    assert _normalize_groups([]) == []
    assert _normalize_groups(None) == []
    assert _normalize_groups(123) == []
    assert _normalize_groups({"unrelated": "value"}) == []


# ─────────────────── регрессия: сопоставление источников ───────────────────


def test_sources_dict_form():
    index_dict, index_list = _extract_sources_index({"sources": {"7": {"sources": [{"t": 1}]}}})
    assert index_dict == {"7": {"sources": [{"t": 1}]}}
    assert index_list == []
    assert _lookup_sources(index_dict, index_list, 7, None) == [{"t": 1}]


def test_sources_list_form():
    index_dict, index_list = _extract_sources_index([{"original_index": 7, "sources": [{"t": 1}]}])
    assert index_dict == {}
    assert len(index_list) == 1
    assert _lookup_sources(index_dict, index_list, 7, None) == [{"t": 1}]


def test_sources_lookup_by_claim_id_fallback():
    index_dict, _ = _extract_sources_index({"1": {"sources": [{"t": "by_id"}]}})
    # original_index отсутствует (плоский вердикт) → ищем по claim_id
    assert _lookup_sources(index_dict, [], None, 1) == [{"t": "by_id"}]


def test_sources_missing_returns_empty():
    index_dict, index_list = _extract_sources_index({})
    assert _lookup_sources(index_dict, index_list, 1, None) == []


def test_sources_malformed_values():
    index_dict, _ = _extract_sources_index({"1": "не словарь"})
    assert _lookup_sources(index_dict, [], None, 1) == []


# ─────────────────── регрессия: цепочка нормализация → сравнение ───────────────────


def test_normalize_compare_chain_sources_by_claim_id(tmp_path, monkeypatch):
    """Полный цикл: плоский вердикт + sources по claim_id → не падает, есть результаты."""
    from numeric_comparator import main
    verdicts = tmp_path / "v.json"
    sources = tmp_path / "s.json"
    out = tmp_path / "o.json"
    verdicts.write_text(json.dumps([
        {"claim_id": 17, "claim_text": "Энергия активации 77 кДж/моль",
         "sources": []},
    ]), encoding="utf-8")
    sources.write_text(json.dumps({
        "17": {"sources": [{"title": "src", "text": "значение 77.5 кДж/моль"}]},
    }), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["numeric_comparator.py", str(verdicts), str(sources), str(out)])
    main()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["total_claims"] == 1
    assert data["groups"][0]["claim_id"] == 17
    assert data["groups"][0]["n_sources"] == 1
    assert data["status_counts"].get("no_data", 0) == 0


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))