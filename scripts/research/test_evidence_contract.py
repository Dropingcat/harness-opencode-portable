"""Тесты Evidence Contract (У2): evidence_contract + интеграция в post_processor."""
import json
import pytest
from pathlib import Path

from evidence_contract import (
    TYPE_TO_TRUST_MAP,
    SPAN_MAX_LEN,
    _slugify,
    build_evidence,
    build_all_evidence,
    load_rules,
    load_verdicts,
)
from post_processor import check_source_trust, check_evidence_trust, post_process_verdict

RULES_PATH = 'testdata/rules.yaml'
EXP1_PATH = str(Path(__file__).resolve().parent / "testdata" / "exp1_verdicts_processed.json")


@pytest.fixture(scope="module")
def rules():
    return load_rules(RULES_PATH)


def golden_claim():
    return {
        "claim_id": 1,
        "claim_text": "Nitriding of steels is a process of surface hardening.",
        "verdict": "SUPPORTED",
        "confidence": 0.95,
        "sources": [
            {"title": "Steels Handbook", "type": "textbook", "trust": 0.9, "excerpt": "textbook excerpt"},
            {"title": "Wikipedia — Nitriding", "type": "encyclopedia", "trust": 0.85,
             "excerpt": "Nitriding is a heat treating process that diffuses nitrogen."},
            {"title": "Journal of Materials", "type": "journal_article", "trust": 0.85,
             "excerpt": "Gas nitriding is a surface hardening process."},
        ],
        "caveats": [],
        "reason": "Confirmed.",
        "numeric_comparison": {},
    }


def test_slugify():
    assert _slugify("Wikipedia — Nitriding") == "wikipedia_nitriding"
    assert _slugify("OpenAlex — Surface Hardening of Steels: Understanding the Basics (ASM, 2003)") == \
        "openalex_surface_hardening_of_steels_understanding_the_basics_asm_2003"
    assert _slugify("  Leading-Trailing  ") == "leading_trailing"
    assert _slugify("") == ""
    assert _slugify(None) == ""


def test_type_to_trust_map_has_expected_values():
    assert TYPE_TO_TRUST_MAP["textbook"] == 0.9
    assert TYPE_TO_TRUST_MAP["encyclopedia"] == 0.6
    assert TYPE_TO_TRUST_MAP["journal_article"] == 0.75


def test_golden_evidence(rules):
    claim = golden_claim()
    ev = build_evidence(claim, rules.get("source_trust"))
    assert ev["status"] == "ok"
    assert ev["claim_id"] == 1
    assert len(ev["evidence"]) == 3

    by_type = {e["type"]: e for e in ev["evidence"]}
    assert by_type["textbook"]["trust"] == 0.9
    assert by_type["encyclopedia"]["trust"] == 0.6
    assert by_type["journal_article"]["trust"] == 0.75
    assert by_type["encyclopedia"]["source_id"] == "wikipedia_nitriding"

    for e in ev["evidence"]:
        assert set(e.keys()) == {"source_id", "span", "trust", "type"}


def test_no_sources_empty_evidence(rules):
    claim = {"claim_id": 2, "claim_text": "x", "sources": []}
    ev = build_evidence(claim, rules.get("source_trust"))
    assert ev["status"] == "ok"
    assert ev["evidence"] == []

    claim_no_key = {"claim_id": 3, "claim_text": "y"}
    ev = build_evidence(claim_no_key, rules.get("source_trust"))
    assert ev["evidence"] == []


def test_unknown_type_falls_back_to_source_trust(rules):
    claim = {"claim_id": 4, "sources": [{"title": "Handbook X", "type": "handbook", "trust": 0.82}]}
    ev = build_evidence(claim, rules.get("source_trust"))
    assert ev["evidence"][0]["trust"] == 0.82


def test_unknown_type_without_trust_falls_back_to_default(rules):
    claim = {"claim_id": 5, "sources": [{"title": "Ref Y", "type": "reference"}]}
    ev = build_evidence(claim, rules.get("source_trust"))
    assert ev["evidence"][0]["trust"] == 0.5


def test_span_truncated_to_500(rules):
    long_excerpt = "a" * 1000
    claim = {"claim_id": 6, "sources": [{"title": "Long", "type": "textbook", "excerpt": long_excerpt}]}
    ev = build_evidence(claim, rules.get("source_trust"))
    span = ev["evidence"][0]["span"]
    assert len(span) == SPAN_MAX_LEN
    assert span == long_excerpt[:SPAN_MAX_LEN]


def test_build_all_evidence_mutates_verdicts(rules):
    verdicts = [golden_claim(), {"claim_id": 7, "sources": []}]
    out = build_all_evidence(verdicts, rules.get("source_trust"))
    assert len(out) == 2
    assert all("evidence" in v for v in out)
    assert out[0]["evidence"][0]["source_id"] == "steels_handbook"


def test_check_evidence_trust_low_trust(rules):
    verdict = {
        "claim_id": 8,
        "confidence": 0.9,
        "verdict": "SUPPORTED",
        "sources": [{"title": "B", "type": "blog", "trust": 0.3}],
        "evidence": [{"source_id": "b", "span": "s", "trust": 0.3, "type": "blog"}],
    }
    assert check_evidence_trust(verdict) == "low_trust_only"
    pv = post_process_verdict(dict(verdict), rules)
    assert pv["confidence"] <= 0.5
    assert pv.get("_capped_by") == "low_trust_sources_only"


def test_check_evidence_trust_high_trust(rules):
    verdict = {
        "claim_id": 9,
        "evidence": [{"source_id": "a", "span": "s", "trust": 0.9, "type": "textbook"}],
    }
    assert check_evidence_trust(verdict) is None


def test_evidence_precedence_over_sources(rules):
    verdict = {
        "claim_id": 10,
        "confidence": 0.9,
        "verdict": "SUPPORTED",
        "sources": [{"title": "A", "type": "textbook", "trust": 0.9}],
        "evidence": [{"source_id": "a", "span": "s", "trust": 0.3, "type": "blog"}],
    }
    assert check_source_trust(verdict) is None
    assert check_evidence_trust(verdict) == "low_trust_only"
    pv = post_process_verdict(dict(verdict), rules)
    assert pv.get("_capped_by") == "low_trust_sources_only"


def test_backward_compat_check_evidence_falls_back_to_sources():
    verdict_no_evidence_low = {
        "claim_id": 11,
        "sources": [{"title": "B", "type": "blog", "trust": 0.3}],
    }
    verdict_no_evidence_high = {
        "claim_id": 12,
        "sources": [{"title": "T", "type": "textbook", "trust": 0.9}],
    }
    assert check_evidence_trust(verdict_no_evidence_low) == check_source_trust(verdict_no_evidence_low) == "low_trust_only"
    assert check_evidence_trust(verdict_no_evidence_high) == check_source_trust(verdict_no_evidence_high) is None


def test_backward_compat_post_process_without_evidence(rules):
    low = {
        "claim_id": 13,
        "claim_text": "Low trust claim",
        "verdict": "SUPPORTED",
        "confidence": 0.95,
        "sources": [{"title": "B", "type": "blog", "trust": 0.3}],
        "caveats": [],
        "reason": "r",
        "numeric_comparison": {},
    }
    high = {
        "claim_id": 14,
        "claim_text": "High trust claim",
        "verdict": "SUPPORTED",
        "confidence": 0.95,
        "sources": [{"title": "T", "type": "textbook", "trust": 0.9}],
        "caveats": [],
        "reason": "r",
        "numeric_comparison": {},
    }
    pv_low = post_process_verdict(dict(low), rules)
    assert pv_low.get("_capped_by") == "low_trust_sources_only"
    assert pv_low["confidence"] <= 0.5

    pv_high = post_process_verdict(dict(high), rules)
    assert pv_high["confidence"] == 0.95
    assert pv_high["verdict"] == "SUPPORTED"
    assert not pv_high.get("problematic")


def test_exp1_real_data(rules):
    verdicts = load_verdicts(EXP1_PATH)
    assert len(verdicts) == 20
    out = build_all_evidence(verdicts, rules.get("source_trust"))
    assert len(out) == 20
    assert all("evidence" in v for v in out)
    assert all(isinstance(v["evidence"], list) for v in out)
    for v in out:
        for e in v["evidence"]:
            assert set(e.keys()) == {"source_id", "span", "trust", "type"}
        post_process_verdict(v, rules)


def test_exp1_evidence_types_mapped(rules):
    verdicts = load_verdicts(EXP1_PATH)
    for v in verdicts:
        for s in v.get("sources", []):
            src_type = s.get("type", "")
            if src_type in ("textbook", "journal_article", "encyclopedia"):
                ev_map = build_evidence(v, rules.get("source_trust"))["evidence"]
                for e in ev_map:
                    if e["type"] == src_type:
                        if src_type == "journal_article":
                            assert e["trust"] == 0.75
                        elif src_type == "encyclopedia":
                            assert e["trust"] == 0.6


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
