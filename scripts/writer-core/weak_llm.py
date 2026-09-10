"""Weak-LLM layer: google/gemma-4-26b-a4b-it via polza.ai, fail-closed.

Principle: LLM PROPOSES (variants with declared intent), CODE ACCEPTS/REJECTS
(span-grounding + RTT comparison). Raw model output is never trusted.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.request
from typing import Any

MODEL = "google/gemma-4-26b-a4b-it"
API = "https://polza.ai/api/v1/chat/completions"

# Auto-calibrated grounding threshold (m_gemma_calib). Read once at import;
# refresh with reload_default_threshold() after a new calibration run.
_CALIBRATION_PATH = os.path.join(
    os.environ.get("WRITER_RUNS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")),
    "gemma_calibration.json",
)


def _load_default_threshold(path: str | None = None) -> float:
    """Read the calibrated grounding threshold from the calibration JSON.

    Falls back to 0.4 when the file is missing, malformed, or carries a null
    threshold (no separation found -> keep the conservative default).
    """
    p = path or _CALIBRATION_PATH
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        t = data.get("threshold")
        if isinstance(t, (int, float)) and 0.0 <= float(t) <= 1.0:
            return float(t)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return 0.4


DEFAULT_THRESHOLD = _load_default_threshold()


def reload_default_threshold() -> float:
    """Re-read the calibration file and refresh DEFAULT_THRESHOLD in place."""
    global DEFAULT_THRESHOLD
    DEFAULT_THRESHOLD = _load_default_threshold()
    return DEFAULT_THRESHOLD

_SYSTEM = (
    "Ты — лингвистический ассистент для анализа русских научных текстов. "
    "Отвечай ТОЛЬКО валидным JSON без пояснений."
)

_TASK_TMPL = (
    "Дано русское научное предложение. Верни JSON:\n"
    "{{\"variants\": [{{\"intent\": \"SAFE_PARAPHRASE|MODALITY_UPGRADE|SCOPE_EXPANSION|"
    "QUALIFIER_LOSS|CAUSALITY_UPGRADE\", \"text\": \"<перефразированное предложение>\"}}]}}\n"
    "Требования:\n"
    "- variants: ровно 2: один SAFE_PARAPHRASE (максимально близкий по смыслу), "
    "один с намеренным семантическим дрейфом (усиление модальности, расширение области, "
    "потеря квалификатора или усиление причинности).\n"
    "- текст на русском, сохрани числа и единицы измерения.\n"
    "Предложение: {source}\n"
)


def _call_llm(prompt: str, max_tokens: int = 900, temperature: float = 0.2) -> str:
    key = os.environ.get("POLZA_API_KEY")
    if not key:
        raise RuntimeError("POLZA_API_KEY not set")
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


def _extract_json(content: str) -> Any:
    """Extract the first valid top-level JSON object, fail-closed.

    Robust to markdown fences (```json ... ```), surrounding prose and
    multiple candidate objects: scans balanced braces with proper
    string-literal handling and returns the first parseable object.
    """
    if not content or not content.strip():
        raise ValueError("empty LLM output")
    # Fast path: whole output is clean JSON (optionally inside a code fence).
    stripped = content.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
    stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass  # fall through to brace scanning
    # Slow path: find first balanced top-level object, ignoring braces in strings.
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
                        break  # invalid object -> try next '{'
    raise ValueError(f"no valid JSON in LLM output: {content[:200]!r}")


_ALLOWED_INTENTS = {"SAFE_PARAPHRASE", "MODALITY_UPGRADE", "SCOPE_EXPANSION",
                    "QUALIFIER_LOSS", "CAUSALITY_UPGRADE"}


def _validate_variants(data: dict[str, Any]) -> list[dict[str, str]]:
    """Fail-closed contract validation."""
    if not isinstance(data, dict) or not isinstance(data.get("variants"), list):
        raise ValueError("contract: missing variants list")
    out: list[dict[str, str]] = []
    for v in data["variants"]:
        if not isinstance(v, dict):
            raise ValueError("contract: variant not object")
        intent = v.get("intent")
        text = v.get("text")
        if intent not in _ALLOWED_INTENTS:
            raise ValueError(f"contract: bad intent {intent!r}")
        if not isinstance(text, str):
            raise ValueError("contract: text not a string")
        text = text.strip()
        if len(text) < 10:
            raise ValueError(f"contract: text too short ({len(text)} chars)")
        out.append({"intent": intent, "text": text})
    if len(out) < 1:
        raise ValueError("contract: no variants")
    return out


def propose_variants(source: str) -> list[dict[str, str]]:
    """Return validated variants. Fail-closed: on any failure returns a single
    ERROR-sentinel variant (intent "ERROR"), never a partially-trusted list."""
    try:
        raw = _call_llm(_TASK_TMPL.format(source=source))
        data = _extract_json(raw)
        variants = _validate_variants(data)
    except Exception as e:
        return [{"intent": "ERROR", "text": f"LLM_FAIL: {type(e).__name__}: {str(e)[:160]}"}]
    return variants


# Non-capturing group so findall() returns full "number + unit" matches,
# not just the unit (capturing group would silently drop the digit).
_NUM_RE = re.compile(r"\d+[.,]?\d*\s*(?:%|°С|°C|нм|мкм|мм|МПа|ч|мин|с)?")


def _norm_number(m: str) -> str:
    """Canonical form for number comparison: lowercase, no internal spaces."""
    return re.sub(r"\s+", "", m.lower())


def ground_span(source: str, variant: str | dict[str, str],
                threshold: float | None = None) -> dict[str, Any]:
    """Span grounding: CODE computes overlap, never the LLM.

    Accepts either the variant text or a variant dict from propose_variants().
    threshold=None uses the module-level DEFAULT_THRESHOLD, which is
    auto-calibrated from gemma_calibration.json when that file exists and
    carries a numeric threshold (else the conservative 0.4).
    Returns token overlap, number-preservation check and a grounded verdict.
    """
    thr = DEFAULT_THRESHOLD if threshold is None else float(threshold)
    variant_text = variant["text"] if isinstance(variant, dict) else variant
    src_toks = set(re.findall(r"[а-яёa-zA-Z0-9]+", source.lower()))
    var_toks = set(re.findall(r"[а-яёa-zA-Z0-9]+", variant_text.lower()))
    common = src_toks & var_toks
    overlap = len(common) / max(1, len(var_toks))
    src_nums = {_norm_number(m) for m in _NUM_RE.findall(source)}
    var_nums = {_norm_number(m) for m in _NUM_RE.findall(variant_text)}
    # Vacuously true when source has no numbers (nothing to preserve),
    # matching RTT comparator semantics (only drift on non-empty source set).
    num_kept = (not src_nums) or (src_nums & var_nums) == src_nums
    return {
        "token_overlap": round(overlap, 3),
        "numbers_preserved": num_kept,
        "grounded": overlap >= thr,
        "threshold_used": thr,
    }
