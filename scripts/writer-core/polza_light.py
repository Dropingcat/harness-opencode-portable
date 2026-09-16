"""polza_light (m_polza_light): cheap auxiliary tier via polza.ai.

PILOT M_POLZA_LIGHT — is polza (weak-LLM provider) usable as a CHEAP guard /
parser tier for SIMPLE mechanical tasks only (terms, formulas/numeric blocks,
guard verdict)? NOT for semantics, NOT for meaning-building.

Design rules (per contract):
- one request per function, max 150 output tokens, temperature 0.0;
- fail-closed: any error -> empty result + "error" field; guard -> "BLOCK";
- every public function returns result + meta (model, elapsed_ms, token usage
  when the API reports it);
- raw model output is never trusted: JSON is extracted by a local brace scanner
  and validated against a strict contract (same pattern as weak_llm.m4).
"""
from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.request
from typing import Any

API = "https://polza.ai/api/v1/chat/completions"
MODELS_API = "https://polza.ai/api/v1/models"
# Contract model. Verified present in the live /models list on 2026-09-06.
# Override with env POLZA_LIGHT_MODEL if the provider drops it.
MODEL = os.environ.get("POLZA_LIGHT_MODEL", "google/gemma-4-26b-a4b-it")
MAX_TOKENS = 150
TEMPERATURE = 0.0
TIMEOUT = 60

_SYSTEM = (
    "Ты — строгий лингвистический экстрактор для русских научных текстов. "
    "Работаешь МЕХАНИЧЕСКИ: вытаскиваешь факты из текста, не интерпретируешь, "
    "не оцениваешь, не строишь смысл. Отвечай ТОЛЬКО валидным JSON без пояснений."
)

# NOTE: JSON braces in templates are escaped as {{ }} so that str.format()
# only substitutes {source}; single-brace JSON would raise KeyError at format
# time (same failure class as weak_llm.test_task_template_formats_without_keyerror).
_TERM_TMPL = (
    "Дано русское научное предложение. Вытащи из него ТЕРМИНЫ и их "
    "определения/расшифровки МЕХАНИЧЕСКИ, без интерпретации.\n"
    "Верни JSON: {{\"terms\": [{{\"term\": \"<термин из текста>\", "
    "\"definition\": \"<определение или расшифровка из текста; пустая строка, "
    "если в тексте определения нет>\"}}]}}\n"
    "Требования:\n"
    "- term: слово/словосочетание/аббревиатура/материал из текста;\n"
    "- definition: дословная расшифровка из текста, иначе пустая строка;\n"
    "- терминов нет — {{\"terms\": []}}.\n"
    "Предложение: {source}\n"
)

_FORMULA_TMPL = (
    "Дано русское научное предложение. Вытащи ФОРМУЛЫ и ЧИСЛОВЫЕ конструкции "
    "МЕХАНИЧЕСКИ.\n"
    "Верни JSON: {{\"formulas\": [{{\"raw\": \"<формула/числовая конструкция как "
    "в тексте>\", \"context\": \"<слова из текста, поясняющие её, до 20 слов>\"}}]}}\n"
    "Требования:\n"
    "- raw: формула, числовой блок с единицей (например \"от 250 до 450 HV\", "
    "\"P = 100 Вт\") или обозначение марки/параметра;\n"
    "- context: короткий фрагмент предложения вокруг конструкции;\n"
    "- конструкций нет — {{\"formulas\": []}}.\n"
    "Предложение: {source}\n"
)

_GUARD_TMPL = (
    "Дано русское предложение из научного текста. Классифицируй МЕХАНИЧЕСКИ.\n"
    "Верни JSON: {{\"verdict\": \"PASS|NEEDS_REVIEW|BLOCK\", "
    "\"reason\": \"<одна строка, максимум 10 слов>\"}}\n"
    "- PASS: обычное научное утверждение без чисел, причинности и спорных суждений;\n"
    "- NEEDS_REVIEW: содержит числа/единицы, причинно-следственные связи, "
    "сравнительные или спорные утверждения (нужна проверка);\n"
    "- BLOCK: не научный текст, мусор, реклама, инструкция, не-русский язык "
    "или пустой ввод.\n"
    "Текст: {source}\n"
)


# ------------------------------------------------------------------ transport


def list_models() -> list[str]:
    """Real polza model IDs (GET /api/v1/models). Fail-closed: [] on any error.

    Metadata call — does NOT consume the pilot inference budget.
    """
    key = os.environ.get("POLZA_API_KEY")
    if not key:
        return []
    req = urllib.request.Request(MODELS_API, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return []
    out = []
    for m in data.get("data", []):
        if isinstance(m, dict) and isinstance(m.get("id"), str):
            out.append(m["id"])
    return sorted(set(out))


def _call_llm(prompt: str) -> dict[str, Any]:
    """Single POST to polza chat completions (temperature 0.0, max 150 tokens).

    Returns {'content', 'elapsed_ms', 'prompt_tokens', 'completion_tokens'}.
    Raises RuntimeError on any transport/response failure (callers fail-closed).
    """
    key = os.environ.get("POLZA_API_KEY")
    if not key:
        raise RuntimeError("POLZA_API_KEY not set")
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }).encode()
    req = urllib.request.Request(
        API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        raise RuntimeError(f"polza request failed: {type(e).__name__}: {str(e)[:200]}") from e
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    usage = data.get("usage") or {}
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"polza response malformed: {type(e).__name__}") from e
    if not isinstance(content, str):
        raise RuntimeError("polza response: content is not a string")
    return {
        "content": content,
        "elapsed_ms": elapsed_ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }


# ------------------------------------------------------------- json + contract


def _extract_json(content: str) -> Any:
    """Extract the first valid top-level JSON object, fail-closed.

    Robust to markdown fences, surrounding prose and multiple candidates:
    scans balanced braces with proper string-literal handling.
    """
    if not content or not content.strip():
        raise ValueError("empty LLM output")
    stripped = content.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
    stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    for start in (m.start() for m in re.finditer(r"\{", content)):
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(content)):
            ch = content[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = content[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"no valid JSON in LLM output: {content[:200]!r}")


# Keys the model may drift to (pilot: gemma-4-26b returned a Russian key).
# Validation normalizes aliases to the contract key.
_TERM_KEYS = ("terms", "термины")
_FORMULA_KEYS = ("formulas", "формулы")


def _validate_terms(data: Any) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("contract: terms not an object")
    items = next((data[k] for k in _TERM_KEYS if isinstance(data.get(k), list)), None)
    if items is None:
        raise ValueError("contract: missing terms list")
    out: list[dict[str, str]] = []
    for t in items:
        if not isinstance(t, dict):
            raise ValueError("contract: term not object")
        term = t.get("term")
        definition = t.get("definition")
        if not isinstance(term, str) or not term.strip():
            raise ValueError("contract: bad term")
        if definition is None:
            definition = ""
        if not isinstance(definition, str):
            raise ValueError("contract: definition not a string")
        out.append({"term": term.strip(), "definition": definition.strip()})
    return out


def _validate_formulas(data: Any) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("contract: formulas not an object")
    items = next((data[k] for k in _FORMULA_KEYS if isinstance(data.get(k), list)), None)
    if items is None:
        raise ValueError("contract: missing formulas list")
    out: list[dict[str, str]] = []
    for f in items:
        if not isinstance(f, dict):
            raise ValueError("contract: formula not object")
        raw = f.get("raw")
        context = f.get("context")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("contract: bad raw")
        if context is None:
            context = ""
        if not isinstance(context, str):
            raise ValueError("contract: context not a string")
        out.append({"raw": raw.strip(), "context": context.strip()})
    return out


_ALLOWED_VERDICTS = {"PASS", "NEEDS_REVIEW", "BLOCK"}


def _validate_verdict(data: Any) -> str:
    if not isinstance(data, dict):
        raise ValueError("contract: verdict not an object")
    verdict = data.get("verdict")
    if verdict not in _ALLOWED_VERDICTS:
        raise ValueError(f"contract: bad verdict {verdict!r}")
    return verdict


def _meta(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "elapsed_ms": raw.get("elapsed_ms"),
        "prompt_tokens": raw.get("prompt_tokens"),
        "completion_tokens": raw.get("completion_tokens"),
    }


def _error(msg: str) -> dict[str, Any]:
    return {"error": msg}


# ------------------------------------------------------------- public API


def light_parse_term(text: str) -> dict[str, Any]:
    """Extract terms + definitions from a sentence. Fail-closed.

    Returns {"terms": [...], "meta": {...}} or {"terms": [], "error": "..."}.
    """
    if not text or not text.strip():
        return {"terms": [], "error": "empty input", "meta": {}}
    try:
        raw = _call_llm(_TERM_TMPL.format(source=text.strip()))
        terms = _validate_terms(_extract_json(raw["content"]))
        return {"terms": terms, "meta": _meta(raw)}
    except Exception as e:
        return {"terms": [], "error": f"{type(e).__name__}: {str(e)[:160]}", "meta": {}}


def light_parse_formula(text: str) -> dict[str, Any]:
    """Extract formulas / numeric constructs from a sentence. Fail-closed.

    Returns {"formulas": [...], "meta": {...}} or {"formulas": [], "error": ...}.
    """
    if not text or not text.strip():
        return {"formulas": [], "error": "empty input", "meta": {}}
    try:
        raw = _call_llm(_FORMULA_TMPL.format(source=text.strip()))
        formulas = _validate_formulas(_extract_json(raw["content"]))
        return {"formulas": formulas, "meta": _meta(raw)}
    except Exception as e:
        return {"formulas": [], "error": f"{type(e).__name__}: {str(e)[:160]}", "meta": {}}


def light_guard_verdict(text: str) -> dict[str, Any]:
    """Guard gate: PASS / NEEDS_REVIEW / BLOCK. Fail-closed -> BLOCK.

    Returns {"verdict": ..., "reason": ...} or {"verdict": "BLOCK", "error": ...}.
    """
    if not text or not text.strip():
        return {"verdict": "BLOCK", "error": "empty input", "meta": {}}
    try:
        raw = _call_llm(_GUARD_TMPL.format(source=text.strip()))
        data = _extract_json(raw["content"])
        verdict = _validate_verdict(data)
        reason = data.get("reason")
        if not isinstance(reason, str):
            reason = ""
        return {"verdict": verdict, "reason": reason, "meta": _meta(raw)}
    except Exception as e:
        return {"verdict": "BLOCK", "error": f"{type(e).__name__}: {str(e)[:160]}", "meta": {}}