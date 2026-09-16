# -*- coding: utf-8 -*-
"""writer_core.canon — разделение канона на ДАННЫЕ и ЗНАНИЯ.

Замечание пользователя: article-writer получал «канон» как кашу (лингво+структура+
данные+знания в одном DOM). Разделяем:

  canon_data      — числа/единицы/условия/формулы-константы/evidence-spans
                    (то, что НЕЛЬЗЯ менять/выдумывать). Проверяет verify_claims
                    (numeric_comparison, unit-range).
  canon_knowledge — разрешённые утверждения + вердикты + неопределённость + хеджи
                    (то, ЧТО можно писать и КАК — READY/PROVISIONAL).

Выход обоих — JSON для брифа article-writer: он знает «это число нельзя менять»
(данные) и «это утверждение можно писать только так» (знания).
"""
from __future__ import annotations

import re
from typing import Any

# --- маркеры чисел в тексте claim (единицы физики конденсированного состояния) ---
_UNIT_RE = re.compile(
    r"\d+[.,]?\d*\s*(?:%|°С|°C|нм|мкм|мм|см|МПа|ГПа|HV|ч|мин|с|К|кДж/м2|м2/г|"
    r"ат\.?%|мас\.?%|об\.?%)"
)


def split_dom(dom: dict) -> dict:
    """DOM -> {canon_data, canon_knowledge} (детерминированно).

    canon_data:
      data_entries: [ {claim_id, numbers:[raw], source_id, unit_checks:[] } ]
      numeric_compare: из claims[].verification.numeric_comparison
      formulas: из verification.formula
    canon_knowledge:
      claims: [ {id, text, kind, verdict, confidence, level, allowed_text_mode} ]
      hedges: {claim_id: разрешённая хедж-фраза}
      research_requests: из uncertainty_bridge
    """
    claims = dom.get("claims") or []
    uncertainty = dom.get("uncertainty") or {}

    canon_data = {
        "data_entries": [],
        "numeric_compare": [],
        "formulas": [],
        "sources": dom.get("sources") or [],
    }
    canon_knowledge = {
        "claims": [],
        "hedges": {},
        "research_requests": [],
    }

    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "")
        text = str(c.get("text") or "")
        ver = c.get("verification") or {}
        unc = uncertainty.get(cid) or {}
        level = unc.get("level") if isinstance(unc, dict) else str(unc) if unc else "medium"

        # --- данные ---
        nums = _UNIT_RE.findall(text)
        if nums:
            canon_data["data_entries"].append({
                "claim_id": cid,
                "numbers": nums,
                "source_id": ((c.get("evidence") or [{}])[0].get("source_id")
                              if c.get("evidence") else None),
            })
        if isinstance(ver, dict) and ver.get("numeric_comparison"):
            canon_data["numeric_compare"].append({
                "claim_id": cid,
                "comparison": ver["numeric_comparison"],
            })
        if isinstance(ver, dict) and ver.get("formula"):
            canon_data["formulas"].append({
                "claim_id": cid,
                "formula": ver["formula"],
            })

        # --- знания ---
        verdict = ver.get("verdict") if isinstance(ver, dict) else "OPEN"
        ready = (level == "low" and verdict in ("SUPPORTED", "OPEN"))
        canon_knowledge["claims"].append({
            "id": cid,
            "text": text,
            "kind": c.get("kind"),
            "verdict": verdict,
            "confidence": ver.get("confidence") if isinstance(ver, dict) else None,
            "level": level,
            "allowed_text_mode": "tentative_only" if not ready else "direct",
            "readiness": "READY" if ready else "PROVISIONAL",
        })
        # хеджи из uncertainty_bridge (tentative_only -> фраза)
        if not ready:
            from writer_core.uncertainty_bridge import TENTATIVE_PHRASES
            canon_knowledge["hedges"][cid] = (
                TENTATIVE_PHRASES.get("high" if level == "high" else "medium", ""))

    return {"canon_data": canon_data, "canon_knowledge": canon_knowledge}


def canon_brief(dom: dict) -> dict:
    """Сводка канонов для брифа article-writer (что нельзя менять / что можно писать)."""
    s = split_dom(dom)
    cd, ck = s["canon_data"], s["canon_knowledge"]
    return {
        "schema": "writer_core.canon_brief.v1",
        "canon_data": {
            "n_data_entries": len(cd["data_entries"]),
            "n_numeric_compare": len(cd["numeric_compare"]),
            "n_formulas": len(cd["formulas"]),
            "sample_numbers": [e["numbers"][:3] for e in cd["data_entries"][:5]],
            "rule": "Числа/единицы/формулы из canon_data НЕЛЬЗЯ менять и выдумывать; "
                     "проза обязана не противоречить numeric_compare.",
        },
        "canon_knowledge": {
            "n_claims": len(ck["claims"]),
            "n_ready": sum(1 for c in ck["claims"] if c["readiness"] == "READY"),
            "n_provisional": sum(1 for c in ck["claims"] if c["readiness"] == "PROVISIONAL"),
            "rule": "Только claims из canon_knowledge можно писать; PROVISIONAL — "
                     "только с хеджом из hedges[] (tentative_only).",
        },
    }