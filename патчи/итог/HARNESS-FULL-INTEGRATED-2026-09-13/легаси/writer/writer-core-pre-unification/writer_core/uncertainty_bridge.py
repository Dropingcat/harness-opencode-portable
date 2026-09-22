# -*- coding: utf-8 -*-
"""writer_core.uncertainty_bridge — мост «неопределённость → исследовательский запрос».

Research debt (кодекр): claim с высокой неопределённостью НЕ выдумывает уверенность —
он становится PROVISIONAL с allowed_text_mode="tentative_only" и порождает
research_request (что нужно закрыть, чтобы понизить неопределённость).

Детерминированно сканирует DOM:
  claims[] (kind, text, verification.verdict, uncertainty[].level) ->
  research_requests[] + status_map{claim_id: PROVISIONAL/READY}

Пороги (по контракту writer-traceability + RTT):
  level=high  или (level=medium и verdict!=SUPPORTED)  -> PROVISIONAL + tentative_only
  level=low  и verdict in (SUPPORTED, OPEN)             -> READY (можно писать твёрдо)
  иначе                                                -> PROVISIONAL
"""
from __future__ import annotations

from typing import Any

READY = "READY"
PROVISIONAL = "PROVISIONAL"

TENTATIVE_PHRASES = {
    "high": "Имеющиеся данные позволяют предположить",
    "medium": "По имеющимся данным можно говорить",
    "low": "",  # твёрдая формулировка
}


def _claim_level(dom: dict, cid: str) -> str | None:
    unc = dom.get("uncertainty") or {}
    entry = unc.get(cid) or {}
    if isinstance(entry, dict):
        return entry.get("level")
    if isinstance(entry, str):
        return entry
    return None


def _claim_verdict(claim: dict) -> str | None:
    v = claim.get("verification") or {}
    return v.get("verdict") if isinstance(v, dict) else None


def analyze_uncertainty(dom: dict) -> dict:
    """DOM -> {status_map, research_requests, tentative_phrases} (детерминированно).

    status_map:     {claim_id: READY|PROVISIONAL}
    research_requests: [ {claim_id, missing, level, verdict, allowed_text_mode} ]
    tentative_phrases: {claim_id: фраза для текста если PROVISIONAL}
    """
    claims = dom.get("claims") or []
    status_map: dict[str, str] = {}
    research_requests: list[dict] = []
    tentative_phrases: dict[str, str] = {}

    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "")
        if not cid:
            continue
        text = str(c.get("text") or "")
        level = _claim_level(dom, cid) or "medium"
        verdict = _claim_verdict(c) or "OPEN"

        if level == "low" and verdict in ("SUPPORTED", "OPEN"):
            status_map[cid] = READY
        elif level == "high":
            status_map[cid] = PROVISIONAL
            research_requests.append({
                "claim_id": cid,
                "missing": f"источник/эксперимент для claim «{text[:80]}…»",
                "level": level,
                "verdict": verdict,
                "allowed_text_mode": "tentative_only",
            })
            tentative_phrases[cid] = TENTATIVE_PHRASES["high"]
        elif level == "medium" and verdict != "SUPPORTED":
            status_map[cid] = PROVISIONAL
            research_requests.append({
                "claim_id": cid,
                "missing": f"подтверждение (SUPPORTED) для claim «{text[:80]}…»",
                "level": level,
                "verdict": verdict,
                "allowed_text_mode": "tentative_only",
            })
            tentative_phrases[cid] = TENTATIVE_PHRASES["medium"]
        else:
            status_map[cid] = PROVISIONAL
            tentative_phrases[cid] = TENTATIVE_PHRASES["medium"]

    return {
        "status_map": status_map,
        "research_requests": research_requests,
        "tentative_phrases": tentative_phrases,
        "n_readiness": {"READY": sum(1 for v in status_map.values() if v == READY),
                        "PROVISIONAL": sum(1 for v in status_map.values() if v == PROVISIONAL)},
    }


def report_uncertainty(dom: dict, out_path: str | None = None) -> dict:
    """Обёртка: анализ + (опц.) сохранение JSON-отчёта."""
    r = analyze_uncertainty(dom)
    r["schema"] = "writer_core.uncertainty_bridge.v1"
    if out_path:
        import json
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=2)
    return r