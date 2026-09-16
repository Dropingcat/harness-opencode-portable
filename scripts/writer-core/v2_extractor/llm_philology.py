"""LLM philology — gemma для лингвослоя, ЗАКАПСУЛИРОВАННЫЙ контрактами.

Схема: llm_contracts (figures/chreia/emphasis enum + обязательные поля).
Валидация: fail-closed (не-энум, пересказ, пустой — отброс).
QC: span_locate EXACT (фигура обязана быть точной цитатой).
Контекст: детерминированный харнесс (падежи/ЧР/связки) передаётся как справка.
"""

from __future__ import annotations

import json
from typing import Any

from llm_extractor import _call_llm, _extract_json
from llm_contracts import (
    build_prompt, validate_figures, validate_chreia, validate_emphasis,
)
from claim_qa import span_locate


def _validate_schema(data: dict) -> dict:
    """Fail-closed проверка всех секций через llm_contracts."""
    return {
        "figures": validate_figures(data.get("figures", [])),
        "chreia_parts": validate_chreia(data.get("chreia_parts", [])),
        "emphasis": validate_emphasis(data.get("emphasis", [])),
    }


def extract_language_llm(text: str, harness_context: dict | None = None,
                         max_tokens: int = 1200) -> dict:
    """gemma с контрактом + few-shot через build_prompt; harness как справка."""
    extra = f"Контекст от кода (НЕ трогай): POS {harness_context.get('pos_ratios', {}) if harness_context else {}}; связки: {[c['marker'] for c in harness_context['connectors']] if harness_context else []}"
    prompt = build_prompt("language", text, extra_context=extra)
    try:
        raw = _call_llm(prompt, max_tokens)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return {"error": "non-dict llm output"}
        return _validate_schema(data)
    except Exception as e:
        return {"error": str(e)}


def validate_language_llm(raw: dict, text: str) -> dict:
    """QC-подтверждение: только exact-цитаты (фигура = точная цитата)."""
    result = {"figures": [], "chreia_parts": [], "emphasis": []}
    if "error" in raw:
        result["error"] = raw["error"]
        return result
    for item in raw.get("figures", []):
        loc = span_locate(item.get("text", ""), text)
        if loc["method"] == "exact":
            result["figures"].append({**item, "start": loc["start"], "end": loc["end"], "qa_method": "exact"})
    for item in raw.get("chreia_parts", []):
        loc = span_locate(item.get("text", ""), text)
        if loc["method"] == "exact":
            result["chreia_parts"].append({**item, "start": loc["start"], "end": loc["end"]})
    for item in raw.get("emphasis", []):
        loc = span_locate(item.get("text", ""), text)
        if loc["method"] == "exact":
            result["emphasis"].append({**item, "start": loc["start"], "end": loc["end"]})
    return result


def enrich_language(text: str, harness_context: dict | None = None) -> dict:
    raw = extract_language_llm(text, harness_context)
    return validate_language_llm(raw, text)