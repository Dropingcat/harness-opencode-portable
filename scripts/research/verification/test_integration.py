#!/usr/bin/env python3
"""test_integration.py — сквозной пайплайн каскад → слой оценки → вердикты.

Тесты контрактов интеграции (без сети, детерминированно):
  - cascade_integration: sources.json в формате B.6 (found_via/origin/excerpt/relevance);
  - verdict_integration: verdicts.json обратно совместим с evidence_contract/
    numeric_comparator/post_processor (верхний уровень ключей);
  - GAP-UNVERIFIED из content_verdict переживает post_processor (не сворачивается
    в UNSUPPORTED для gap-claims);
  - run_content_pipeline_sections: независимые куски → артефакты.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

import pytest

import cascade_integration as ci
import verdict_integration as vi

from post_processor import post_process_verdict

GAP_CLAIM = ("Разделение вкладов, обусловленных предварительными обработками "
             "(микродеформациями, дефектной субструктурой), в кинетику роста "
             "азотированного слоя остаётся нерешённой задачей.")


def _claims(*texts):
    return [{"original_index": i, "text": t} for i, t in enumerate(texts)]


# ── cascade_integration ───────────────────────────────────────────────
def test_sources_contract_local_corpus():
    """sources.json построен каскадом: формат B.6 (found_via/relevance/excerpt)."""
    claims = _claims("Наблюдается ускорение образования нитридных фаз при "
                     "комбинированных воздействиях.")
    out = ci.build_sources(claims, ["local_corpus"])
    assert out["status"] == "ok"
    srcs = out["sources"].get("0", [])
    assert isinstance(srcs, list)
    for s in srcs:
        assert s.get("found_via") == "local_corpus"
        assert "relevance" in s and "excerpt" in s and "accepted" in s
    assert "verification_meta" in out
    assert out["verification_meta"]["claims_processed"] == 1


def test_sources_empty_claims_no_crash():
    """Пустой список claims → пустой sources.json, без падений."""
    out = ci.build_sources([], ["local_corpus", "openalex"])
    assert out["status"] == "ok"
    assert out["sources"] == {}


# ── verdict_integration: обратная совместимость ───────────────────────
def test_verdict_backcompat_top_level_keys():
    """Верхний уровень verdict: ключи, которые читают evidence_contract/numeric/
    post_processor — на месте."""
    claims = _claims(GAP_CLAIM)
    vs, stats = vi.build_verdicts(claims, {"0": []}, use_llm=False)
    assert stats["total"] == 1
    v = vs[0]
    for key in ("claim_id", "claim_text", "verdict", "confidence", "reason",
                "caveats", "sources"):
        assert key in v, f"нет ключа {key}"
    # богатое представление слоя
    assert "content_verdict" in v
    cvr = v["content_verdict"]
    for key in ("evidence", "per_source", "stats", "uncertainty", "claim_class"):
        assert key in cvr


def test_gap_verdict_survives_post_processor():
    """GAP-UNVERIFIED (gap-claim) не сворачивается в UNSUPPORTED пост-процессором."""
    claims = _claims(GAP_CLAIM)
    vs, stats = vi.build_verdicts(claims, {"0": []}, use_llm=False)
    v = vs[0]
    assert v["verdict"] == "GAP-UNVERIFIED"
    # эмуляция полного вердикта с content_verdict
    verdict = dict(v)
    rules = __import__("yaml").safe_load(
        Path("/home/orangepi/.hermes/profiles/resercher/rules.yaml").read_text(encoding="utf-8"))
    pv = post_process_verdict(dict(verdict), rules)
    assert pv["verdict"] == "GAP-UNVERIFIED", "gap-claim не должен стать UNSUPPORTED"
    assert not pv.get("problematic"), "gap-claim не должен быть problematic автоматом"


def test_verdict_non_gap_collapses_to_unsupported():
    """НЕ-gap claim с низкой уверенностью → UNSUPPORTED (как раньше)."""
    verdict = {
        "claim_id": 9, "claim_text": "обычный claim", "verdict": "AMBIGUOUS",
        "confidence": 0.55, "caveats": [], "reason": "r", "sources": [],
        "content_verdict": {"claim_class": "framing"},
    }
    rules = __import__("yaml").safe_load(
        Path("/home/orangepi/.hermes/profiles/resercher/rules.yaml").read_text(encoding="utf-8"))
    pv = post_process_verdict(dict(verdict), rules)
    assert pv["verdict"] == "UNSUPPORTED"


# ── run_content_pipeline_sections ─────────────────────────────────────
def test_runner_generates_artifacts(tmp_path):
    """Прогон куска → claims/sources/verdicts/summary на диске."""
    import run_content_pipeline_sections as r
    res = r.run_section("actuality", r.SECTIONS["actuality"], tmp_path, use_llm=False)
    ws = Path(res["ws"])
    for f in ("claims.json", "sources.json", "verdicts.json"):
        assert (ws / f).is_file(), f"нет {f}"
    assert res["claims"] >= 1


def test_runner_section_isolation():
    """Кусочки независимы: у каждого свой workspace."""
    import run_content_pipeline_sections as r
    assert set(r.SECTIONS) == {"actuality", "novelty", "positions"}


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))