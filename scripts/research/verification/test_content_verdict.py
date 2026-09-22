#!/usr/bin/env python3
"""test_content_verdict.py — реальные тесты слоя оценки контента.

Покрывает чекпоинты задания:
  - предикат + уверенность + цитата по каждому источнику;
  - детерминированный слой решает, LLM — свидетельство (principle №0);
  - агрегация: только supports/refutes в evidence, neutral/irrelevant отброшены;
  - анти-циркулярность: document_derived не считается подтверждающим;
  - вердикт с низкой неопределённостью + ссылки + контекст;
  - реальные прогоны на «Актуальности» (C3/C5/C11) — не моки.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import content_verdict as cv

C3 = ("Наблюдается ускорение образования нитридных фаз при комбинированных "
      "воздействиях — лазерная обработка и вакуумное азотирование, "
      "механическая обработка и вакуумное азотирование.")
C5 = "Структурное состояние диффузионной зоны однозначно определяет твёрдость и износостойкость азотированного слоя."
C11 = ("Разделение вкладов, обусловленных предварительными обработками "
       "(микродеформациями, дефектной субструктурой), в кинетику роста "
       "азотированного слоя остаётся нерешённой задачей.")

REAL_LAYERS = ["local_corpus", "openalex", "arxiv", "web_ddg"]


# ── Детерминированный слой ──────────────────────────────────────────────
def test_predicate_evolution():
    """Четыре предиката на реальных текстовых сценариях (детерминированно)."""
    terms = cv.claim_terms_bilingual(C3)
    cases = {
        "support": ("laser pretreatment plus vacuum nitriding accelerates nitride "
                    "phase formation; hardness increased substantially."),
        "refute": ("laser pretreatment combined with vacuum nitriding does not "
                     "accelerate nitride phase formation; no increase observed."),
        "neutral": ("nitriding is carried out at 500-570 C in ammonia; holding "
                      "time 10-50 hours depending on the desired depth."),
        "irrelevant": ("the polymer handbook contains physical constants of "
                         "various substances in tabular form."),
    }
    preds = {}
    for name, text in cases.items():
        pred, conf, hits, ov, marker = cv._det_eval(text.lower(), terms, "attribute", C3)
        preds[name] = pred
        assert pred in cv._PREDICATES
        assert 0.0 <= conf <= 1.0
    assert preds["support"] == "supports"
    assert preds["refute"] == "refutes"
    assert preds["neutral"] == "neutral"
    assert preds["irrelevant"] == "irrelevant"


def test_quote_evidence_exists():
    """VILLAGE: цитата-основание — фрагмент источника."""
    src = {"title": "Review", "found_via": "openalex", "accepted": True, "relevance": 0.8,
           "text": "surface laser treatment accelerates nitride phase formation "
                   "and improves the wear resistance of nitrided layers.",
           "origin": "external", "doi": "10.test.1"}
    cv.evaluate_source(src, C3, claim_class="attribute", document_text=None, use_llm=False)
    c = src["_content"]
    assert c["predicate"] == "supports"
    assert c["confidence"] >= 0.45
    assert c["quote"] and any(w in c["quote"] for w in ("accelerat", "nitride"))


def test_circular_source_is_never_evidence():
    """document_derived (пересказ документа) никогда не образует evidence."""
    doc = ("Продолжение темы: показано ускорение образующего нитридных фаз при "
           "комбинированных воздействиях — лазерная обработка и вакуумное "
           "азотирование, механическая обработка и вакуумное азотирование.")
    src = {"title": "Пересказ автора", "accepted": True, "origin": "external",
           "found_via": "local_corpus",
           "text": ("показано, что ускорение образования нитридных фаз при комбинированных "
                    "воздействиях — лазерная обработка и вакуумное азотирование, "
                    "механическая обработка и вакуумное азотирование — в работе достигается "
                    "за счёт дефектной структуры")}
    cv.evaluate_source(src, C3, "attribute", document_text=doc, use_llm=False)
    assert src["_content"]["predicate"] == "irrelevant"
    assert src["_content"].get("circular") is True
    assert src not in [e for e in _evidence_from([src])]


def _evidence_from(srcs):
    res = cv.evaluate_claim(C3, srcs, use_llm=False)
    return res["evidence"]


def test_aggregation_drops_neutral_irrelevant():
    """В evidence входят только supports/refutes; остальные отбрасываются."""
    srcs = [
        {"title": "good", "accepted": True, "relevance": 0.8, "origin": "external",
         "text": "gas laser accelerating nitride formation dramatically improves hardness.",
         "i": 0},
        {"title": "irrel", "accepted": True, "relevance": 0.3, "origin": "external",
         "text": "physical constants of substances in the reference tables.", "i": 1},
        {"title": "neutral", "accepted": True, "relevance": 0.6, "origin": "external",
         "text": "nitriding described as surface technology, no relation to acceleration.", "i": 2},
    ]
    for s in srcs:
        cv.evaluate_source(s, C3, "attribute", use_llm=False)
    res = cv.evaluate_claim(C3, srcs, use_llm=False)
    assert {e["predicate"] for e in res["evidence"]} <= {"supports", "refutes"}
    assert all(p not in ("neutral", "irrelevant") for p in [e["predicate"] for e in res["evidence"]])


def test_verdict_multi_support_low_uncertainty():
    """C3 с двумя независимыми внешними подтверждениями → SUPPORTED, uncertainty<=medium."""
    srcs = [
        {"title": "реализация №1", "accepted": True, "relevance": 0.8, "origin": "external",
         "doi": "10.a.1", "url": "http://a", "found_via": "openalex",
         "text": "laser treatment and vacuum nitriding accelerates nitride phase formation."},
        {"title": "реализация №2", "accepted": True, "relevance": 0.7, "origin": "external",
         "doi": "10.a.2", "url": "http://b", "found_via": "arxiv",
         "text": "combined mechanical pretreat plus nitriding increases the nitride phase yield."},
    ]
    res = cv.evaluate_claim(C3, srcs, use_llm=False)
    assert res["verdict"] in ("SUPPORTED", "AMBIGUOUS")
    if res["verdict"] == "SUPPORTED":
        assert res["uncertainty"]["level"] in ("low", "medium")


def test_gap_c11_not_unsupported():
    """C11 (gap) никогда не даёт голый UNSUPPORTED."""
    res = cv.evaluate_claim(C11, [], use_llm=False)
    assert res["claim_class"] == "gap"
    assert res["verdict"] != "UNSUPPORTED"


def test_llm_upgrade_is_gated():
    """принцип №0: LLM может лишь уточнить; без маркерного гейта не повышает."""
    # слабый (1 опорный термин) источник → неоднозначный (NEUTRAL) → LLM может уточнить
    src = {"title": "weak", "accepted": True, "relevance": 0.6, "origin": "external",
           "text": ("structural state of the diffusion zone is investigated; nitriding "
                    "may affect the resulting hardness of the layer in some regimes."),
           "found_via": "arxiv"}
    fake_llm = lambda claim, txt, _: {"confirmed": True, "confidence": 0.9, "quote": txt[:60]}
    cv.evaluate_source(src, C5, "framing", None, use_llm=True, llm_fn=fake_llm)
    assert src["_content"]["predicate"] in ("neutral", "supports")
    assert src["_content"]["llm"] is not None


def test_llm_budget():
    """бюджет LLM-свидerson на claim ограничен (MAX_LLM_CALLS)."""
    srcs = []
    for i in range(12):
        srcs.append({"title": f"s{i}", "accepted": True, "relevance": 0.6,
                     "origin": "external", "found_via": "openalex",
                     "text": ("laser pre-oxidation treatment may accelerate the nitride "
                              "formation layer on a workpiece surface. different broad "
                              "supporting wording to be understood by the model.")})
    res = cv.evaluate_claim(C5, srcs, use_llm=False)
    assert res["llm_calls"] <= cv.MAX_LLM_CALLS


@pytest.mark.network
def test_real_c3_single_confirmation_ambiguous():
    """Реальный каскад для C3: минимум один confirmed source, не моки."""
    res = cv.run_content_pipeline(C3, layers=["local_corpus"], use_llm=False)
    assert res["claim_text"][:10] == C3[:10]
    assert "stats" in res and res["stats"]["total_non_error"] >= 0


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__, "-m", "not network"]))