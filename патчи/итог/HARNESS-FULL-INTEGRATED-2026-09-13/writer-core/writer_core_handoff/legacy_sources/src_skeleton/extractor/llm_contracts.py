"""LLM Contracts — единые JSON-схемы и fail-closed валидаторы для всех LLM-извлечений.

Закапсулированный блок: каждый LLM-вызов обязан соответствовать схеме; результат,
не прошедший схему, отбрасывается (не идёт в графы). Принцип: LLM ПРЕДЛАГАЕТ,
КОД ПРИНИМАЕТ.

Покрывает:
  - claims        (научные утверждения)
  - scope         (контекст: материал/условия/среда/метод)
  - objects       (числа/формулы/аббревиатуры)
  - language      (фигуры/хрия/акценты)
  - connectors    (связки — внутри language)

Схемы = data-driven (declarative), валидаторы = детерминированные.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Схемы-контракты (declarative)
# ---------------------------------------------------------------------------

CLAIM_KINDS = {
    "OBSERVATIONAL", "QUANTITATIVE", "MECHANISTIC", "RECOMMENDATION", "CAUSAL",
    "DEFINITIONAL", "METHODOLOGICAL", "SOURCE_BASED", "INTERPRETIVE",
}
CLAIM_ROLES = {"данные", "факт", "вывод", "рекомендация", "определение", "метод"}
CLAIM_STRENGTH = {"strong", "medium", "weak"}

SCOPE_DIMENSIONS = {"material", "environment", "condition", "method", "population"}

OBJECT_TYPES = {"number", "formula", "abbreviation", "term", "chemical", "steel"}

FIGURE_TYPES = {"repetition", "antithesis", "gradation", "inversion",
                "parcellation", "rhetorical_question", "enumeration"}
CHREIA_PARTS = {"preface", "thesis", "cause", "contrary", "analogy",
                "example", "evidence", "conclusion"}
EMPHASIS_TYPES = {"fronting", "repetition", "contrast_focus", "intensifier"}

# Минимальные обязательные поля каждого элемента по типу вызова
_REQUIRED = {
    "claim": ["text", "claim_kind", "role", "strength"],
    "scope": ["dimension", "value", "span"],
    "object": ["raw", "type"],
    "figure": ["type", "text"],
    "chreia": ["part", "text"],
    "emphasis": ["type", "text"],
}

_ENUM_MAP = {
    "claim_kind": CLAIM_KINDS, "role": CLAIM_ROLES, "strength": CLAIM_STRENGTH,
    "dimension": SCOPE_DIMENSIONS, "type": OBJECT_TYPES | FIGURE_TYPES | EMPHASIS_TYPES,
    "part": CHREIA_PARTS,
}

# ---------------------------------------------------------------------------
# Валидаторы (fail-closed, детерминированные)
# ---------------------------------------------------------------------------

def validate_item(item: Any, kind: str) -> dict | None:
    """Проверить один элемент контракта. Вернуть элемент (если ОК) или None."""
    if not isinstance(item, dict):
        return None
    # обязательные поля
    for field_name in _REQUIRED.get(kind, []):
        v = item.get(field_name)
        if not isinstance(v, str) or not v.strip():
            return None
    # enum-поля
    for field_name, allowed in _ENUM_MAP.items():
        if field_name in item:
            v = item[field_name]
            if isinstance(v, str) and v not in allowed:
                return None
    return item


def validate_collection(raw: Any, kind: str) -> list[dict]:
    """Провалидировать массив элементов контракта (fail-closed)."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        ok = validate_item(item, kind)
        if ok is not None:
            out.append(ok)
    return out


def validate_claims(raw: Any) -> list[dict]:
    return validate_collection(raw, "claim")

def validate_scope(raw: Any) -> list[dict]:
    return validate_collection(raw, "scope")

def validate_objects(raw: Any) -> list[dict]:
    return validate_collection(raw, "object")

def validate_figures(raw: Any) -> list[dict]:
    return validate_collection(raw, "figure")

def validate_chreia(raw: Any) -> list[dict]:
    return validate_collection(raw, "chreia")

def validate_emphasis(raw: Any) -> list[dict]:
    return validate_collection(raw, "emphasis")


# ---------------------------------------------------------------------------
# Унифицированный валидатор всего LLM-ответа
# ---------------------------------------------------------------------------

def validate_llm_response(raw: dict) -> dict:
    """Валидировать полный ответ LLM (все секции). Fail-closed."""
    return {
        "claims": validate_claims(raw.get("claims", [])),
        "scope": validate_scope(raw.get("scope", [])),
        "objects": validate_objects(raw.get("objects", [])),
        "figures": validate_figures(raw.get("figures", [])),
        "chreia_parts": validate_chreia(raw.get("chreia_parts", [])),
        "emphasis": validate_emphasis(raw.get("emphasis", [])),
    }


# ---------------------------------------------------------------------------
# Промпт-контракты (вставляются в каждый LLM-вызов)
# ---------------------------------------------------------------------------

CLAIM_PROMPT_SCHEMA = """Строгий JSON, без пояснений:
{"claims": [
  {"text": "<ТОЧНАЯ непрерывная цитата из текста, не пересказ>",
   "claim_kind": "OBSERVATIONAL|QUANTITATIVE|MECHANISTIC|RECOMMENDATION|CAUSAL|DEFINITIONAL|METHODOLOGICAL",
   "role": "данные|факт|вывод|рекомендация|определение|метод",
   "strength": "strong|medium|weak"}
]}
text — дословно из текста; ничего не выдумывай."""

SCOPE_PROMPT_SCHEMA = """Строгий JSON, без пояснений:
{"scope": [
  {"dimension": "material|environment|condition|method|population",
   "value": "<краткое значение>",
   "span": "<ТОЧНАЯ цитата из текста>"}
]}
span — дословно из текста."""

OBJECT_PROMPT_SCHEMA = """Строгий JSON, без пояснений:
{"objects": [
  {"raw": "<ТОЧНЫЙ фрагмент из текста>",
   "type": "number|formula|abbreviation|term|chemical|steel"}
]}
raw — дословно из текста; не выдумывай."""

LANGUAGE_PROMPT_SCHEMA = """Строгий JSON, без пояснений:
{"figures": [{"type": "repetition|antithesis|gradation|inversion|parcellation|rhetorical_question|enumeration", "text": "<точная цитата>"}],
 "chreia_parts": [{"part": "preface|thesis|cause|contrary|analogy|example|evidence|conclusion", "text": "<точная цитата>"}],
 "emphasis": [{"type": "fronting|repetition|contrast_focus|intensifier", "text": "<точная цитата>"}]}
text — дословно; пустое [] если явления нет."""

_FEWSHOT_LANG = """ПРИМЕР:
Текст: «Однако сталь не проявляет склонности к МКК после закалки и имеет высокое сопротивление.»
Ответ: {"figures":[{"type":"antithesis","text":"не проявляет склонности к МКК после закалки"}],
  "chreia_parts":[{"part":"contrary","text":"не проявляет склонности к МКК после закалки"},{"part":"thesis","text":"имеет высокое сопротивление"}],
  "emphasis":[{"type":"contrast_focus","text":"не проявляет склонности к МКК"}]}"""

_ASSEMBLE_CLAIM_EXAMPLE = """ПРИМЕР:
Текст: «Средняя скорость коррозии составляла 0,1–0,4 мг/м2ч. Сталь не проявляет склонности к МКК.»
Ответ: {"claims":[
 {"text":"средняя скорость коррозии составляла 0,1–0,4 мг/м2ч","claim_kind":"QUANTITATIVE","role":"данные","strength":"strong"},
 {"text":"Сталь не проявляет склонности к МКК","claim_kind":"OBSERVATIONAL","role":"факт","strength":"strong"}]}"""


def build_prompt(task: str, text: str, extra_context: str = "") -> str:
    """Собрать промпт для LLM по типу задачи (единый фасад)."""
    schemas = {
        "claims": CLAIM_PROMPT_SCHEMA + "\n" + _ASSEMBLE_CLAIM_EXAMPLE,
        "scope": SCOPE_PROMPT_SCHEMA,
        "objects": OBJECT_PROMPT_SCHEMA,
        "language": LANGUAGE_PROMPT_SCHEMA + "\n" + _FEWSHOT_LANG,
    }
    task_desc = {
        "claims": "Извлеки научные утверждения (facts/results) из текста.",
        "scope": "Определи научный контекст/scope (материал, условия, среда, метод).",
        "objects": "Найди все количественные данные и хим. обозначения в тексте.",
        "language": "Найди риторические приёмы (фигуры, хрия, акценты) в тексте.",
    }
    return f"""{task_desc[task]}
{extra_context}
{schemas[task]}

Текст:
\"\"\"{text}\"\"\""""