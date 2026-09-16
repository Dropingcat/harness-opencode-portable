"""LLM extractor — gemma для claims/scope/objects, ЗАКАПСУЛИРОВАННЫЙ с контрактами.

Все LLM-вызовы:
  1. промпт строится из llm_contracts.build_prompt (схема контракта вшита)
  2. ответ проходит через llm_contracts.validate_* (fail-closed)
  3. span-координаты вычисляет КОД (не LLM): текст → find в оригинале

Принцип: LLM ПРЕДЛАГАЕТ по схеме, КОД принимает/отклоняет.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.request
from typing import Any

from llm_contracts import (
    build_prompt, validate_claims, validate_scope, validate_objects,
)

_MODEL = "google/gemma-4-26b-a4b-it"
_API = "https://polza.ai/api/v1/chat/completions"


def _call_llm(prompt: str, max_tokens: int = 1500, temperature: float = 0.0) -> str:
    key = os.environ.get("POLZA_API_KEY")
    if not key:
        raise RuntimeError("POLZA_API_KEY not set")
    payload = json.dumps({
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        _API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


def _extract_json(content: str) -> Any:
    start = content.find("{")
    end = content.rfind("}") + 1
    if start < 0 or end <= 0:
        start = content.find("[")
        end = content.rfind("]") + 1
    if start < 0 or end <= 0:
        raise ValueError(f"no JSON in LLM output: {content[:200]}")
    return json.loads(content[start:end])


def _attach_span(collection: list[dict], text: str, field: str) -> list[dict]:
    """Код вычисляет span: find фрагмента в тексте (не LLM)."""
    for item in collection:
        frag = item.get(field, "")
        if not frag:
            item["start"] = item["end"] = None
            continue
        idx = text.lower().find(frag.lower())
        if idx >= 0:
            item["start"] = idx
            item["end"] = idx + len(frag)
        else:
            item["start"] = item["end"] = None  # QC отбросит
    return collection


def extract_claims_llm(text: str, max_tokens: int = 1500) -> list[dict]:
    prompt = build_prompt("claims", text)
    try:
        raw = _call_llm(prompt, max_tokens)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return []
        claims = validate_claims(data.get("claims", []))  # fail-closed
        return _attach_span(claims, text, "text")
    except Exception as e:
        return [{"error": str(e)}]


def extract_scope_llm(text: str, max_tokens: int = 800) -> list[dict]:
    prompt = build_prompt("scope", text)
    try:
        raw = _call_llm(prompt, max_tokens)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return []
        scope = validate_scope(data.get("scope", []))
        return _attach_span(scope, text, "span")
    except Exception:
        return []


def extract_objects_llm(text: str, max_tokens: int = 800) -> list[dict]:
    prompt = build_prompt("objects", text)
    try:
        raw = _call_llm(prompt, max_tokens)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return []
        objs = validate_objects(data.get("objects", []))
        return _attach_span(objs, text, "raw")
    except Exception:
        return []


def enrich(text: str) -> dict:
    result = {}
    result["claims"] = extract_claims_llm(text)
    result["scope"] = extract_scope_llm(text)
    result["llm_objects"] = extract_objects_llm(text)
    return result