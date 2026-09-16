"""Extraction engine: извлекает ВСЮ возможную информацию из абзаца
и сортирует по классам. Остаток (предлоги/дефисы/союзы) — хвост.

Классы извлечения (уровни A-D):
  A) Научные claims-кандидаты
  B) Объекты: числа+единицы, формулы, химия, термины, аббревиатуры
  C) Дискурс: роли (метод/результат/вывод), модальность, Toulmin-роли
  D) Лингво-стиль: хеджинг, пассив, связки, жанровые маркеры
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from c5_number import extract_quantities


# ------------------------- B: объекты -------------------------

# Химические формулы: простые и сложные паттерны
_CHEM_SYM = r"(?:[A-Z][a-z]?\d*|[А-ЯЁ]{1,3}\d?)"
_CHEM_RE = re.compile(
    r"\b(?:"
    + _CHEM_SYM + r"(?:" + r"-" + _CHEM_SYM + r"){1,4}"      # Fe-Cr-Mn
    + r"|" + _CHEM_SYM + _CHEM_SYM                         # Cr23C6, VN, NbN
    + r")\b"
)

# Русская сталь: 12Х18Н10Т, 05Х22АГ15Н8МФ, 09Х19АГ10Н6М
_STEEL_RE = re.compile(
    r"\b\d{1,2}[А-ЯЁA-Z]{1,2}\d{1,3}[А-ЯЁA-Z]{1,3}"
    r"(?:\d{1,2}[А-ЯЁA-Z]{1,3})?\d{0,2}[А-ЯЁA-Z]{0,3}\b"
)

# Аббревиатуры в скобках после полного имени: "стали (ВАС)"
_ABBR_DEF_RE = re.compile(r"([А-ЯЁ][а-яё]+(?:\s[а-яё]+){0,3})\s*\(([А-ЯЁA-Z]{2,8})\)")

# Аббревиатуры-одиночки (заглавные 2+)
_ABBR_STANDALONE_RE = re.compile(r"\b([А-ЯЁA-Z]{2,8})\b")

# Термины: в кавычках или дефисные, не начало предложения
_TERM_RE = re.compile(r"«([А-ЯЁ][а-яё]+(?:[-\s][а-яёА-ЯЁ]+){0,2})»|([А-ЯЁ][а-яё]+(?:[-][а-яё]+){1,2})")

# Годы: 2018 г.
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\s*г\.")


# ------------------------- C: дискурс -------------------------

_METHOD_MARKERS = ("исследован", "разработана", "разработан", "метод", "проведен", "использован")
_RESULT_MARKERS = ("показано", "установлено", "получено", "определено", "достиж", "выявлено")
_CONCLUSION_MARKERS = ("таким образом", "следовательно", "заключает", "вывод")
_LIMITATION_MARKERS = ("огранич", "недостат", "не удалось")
_RECOMMENDATION_MARKERS = ("рекоменд", "следует", "целесообразно", "необходимо")

_HEDGE_WORDS = ("вероятно", "можно предположить", "по-видимому", "предположительно", "возможно", "как правило")
_STRONG_MODALITY = ("составляет", "является", "установлено", "доказано", "подтверждено")
_WEAK_MODALITY = ("может", "вероятно", "должен", "могло", "видимо", "возможно")

_PASSIVE_RE = re.compile(r"\b(?:был|была|были|было|является|являются|рассматривается|выполняется)\b")

_CONNECTORS = ("таким образом", "однако", "кроме того", "вместе с тем", "следовательно",
               "поэтому", "в том числе", "в частности", "то есть")
_GENRE_MARKERS = ("автореферат", "диссертация", "работа", "защита")


# ------------------------- datatypes -------------------------

@dataclass
class ExtractionResult:
    claims: list[dict] = field(default_factory=list)
    objects: list[dict] = field(default_factory=list)
    discourse: list[dict] = field(default_factory=list)
    style: list[dict] = field(default_factory=list)
    tail: list[str] = field(default_factory=list)   # остаток: предлоги, дефисы, частицы


# ------------------------- extraction -------------------------

def _sentences(text: str) -> list[str]:
    from c1_c2_structure import _split_sentences
    return _split_sentences(text)


def extract_object_b(text: str, para_id: str, si: int) -> list[dict]:
    objs = []

    # числа (C5) — с координатами start/end (позиция в тексте)
    qs = extract_quantities([text])
    for q in qs:
        objs.append({
            "class": "B_number", "id": f"{para_id}_Q{len(objs)}",
            "raw": q.raw, "value_lower": q.value_lower, "value_upper": q.value_upper,
            "unit": q.unit, "dimension": q.dimension,
            "start": q.position, "end": q.position + len(q.raw)},
        )

    # русская сталь
    for m in _STEEL_RE.finditer(text):
        objs.append({"class": "B_steel", "id": f"{para_id}_S{len(objs)}", "raw": m.group(0),
                     "start": m.start(), "end": m.end()})

    # химия
    for m in _CHEM_RE.finditer(text):
        raw = m.group(0)
        if raw and not raw.isdigit() and " " not in raw:
            objs.append({"class": "B_chemical", "id": f"{para_id}_F{len(objs)}", "raw": raw,
                         "start": m.start(), "end": m.end()})

    # годы
    for m in _YEAR_RE.finditer(text):
        objs.append({"class": "B_year", "id": f"{para_id}_Y{len(objs)}", "value": m.group(1),
                     "start": m.start(), "end": m.end()})

    # аббревиатуры с расшифровкой
    for m in _ABBR_DEF_RE.finditer(text):
        objs.append({"class": "B_abbr_def", "id": f"{para_id}_A{len(objs)}",
                     "abbr": m.group(2), "expansion": m.group(1).strip(),
                     "start": m.start(), "end": m.end()})

    # термины
    seen_t = set()
    for m in _TERM_RE.finditer(text):
        w = m.group(1) or m.group(2)
        if w and w not in seen_t and len(w) > 3:
            seen_t.add(w)
            objs.append({"class": "B_term", "id": f"{para_id}_T{len(objs)}", "term": w})

    return objs


def extract_discourse_c(text: str) -> list[dict]:
    res = []
    low = text.lower()
    if any(m in low for m in _RESULT_MARKERS):
        res.append({"class": "C_discourse", "role": "result", "marker": next(m for m in _RESULT_MARKERS if m in low)})
    if any(m in low for m in _METHOD_MARKERS):
        res.append({"class": "C_discourse", "role": "method", "marker": next(m for m in _METHOD_MARKERS if m in low)})
    if any(m in low for m in _CONCLUSION_MARKERS):
        res.append({"class": "C_discourse", "role": "conclusion", "marker": next(m for m in _CONCLUSION_MARKERS if m in low)})
    if any(m in low for m in _LIMITATION_MARKERS):
        res.append({"class": "C_discourse", "role": "limitation", "marker": next(m for m in _LIMITATION_MARKERS if m in low)})
    if any(m in low for m in _RECOMMENDATION_MARKERS):
        res.append({"class": "C_discourse", "role": "recommendation", "marker": next(m for m in _RECOMMENDATION_MARKERS if m in low)})
    # модальность
    if any(m in text for m in _STRONG_MODALITY):
        res.append({"class": "C_modality", "kind": "strong_assertive"})
    if any(m in text for m in _WEAK_MODALITY):
        res.append({"class": "C_modality", "kind": "weak_hedged"})
    return res


def extract_style_d(text: str) -> list[dict]:
    res = []
    low = text.lower()
    for h in _HEDGE_WORDS:
        if h in low:
            res.append({"class": "D_hedging", "marker": h})
            break
    if _PASSIVE_RE.search(text):
        res.append({"class": "D_passive", "marker": "passive_voice"})
    for c in _CONNECTORS:
        if c in low:
            res.append({"class": "D_connector", "marker": c})
            break
    for g in _GENRE_MARKERS:
        if g in low:
            res.append({"class": "D_genre_marker", "marker": g})
            break
    return res


def extract_claims_a(text: str, para_id: str = "PAR_000") -> list[dict]:
    """Грубая эвристика claim-кандидатов (уровень A). Полная — LLM-капсула.
    Каждый claim несёт АБСОЛЮТНЫЕ координаты: span (start/end) в байтах/символах
    исходного текста + page (если известна), sentence_idx.
    """
    claims = []
    sentences = _sentences(text)
    offset = 0
    for si, s in enumerate(sentences):
        low = s.lower()
        idx = text.lower().find(s.lower())
        start = text.lower().find(s.lower(), offset) if idx >= 0 else offset
        # надёжный поиск span: от текущего offset
        found = text.lower().find(s.lower(), offset)
        s_start = found if found >= 0 else offset
        s_end = s_start + len(s) if s_start >= 0 else offset + len(s)
        offset = s_end

        # матч по КОРНЮ глагола (флексии: повышает/повысить/повышена)
        _PRED_ROOTS = ("составл", "явля", "следу", "показ", "установл", "обеспеч", "повыш",
                       "проявл", "вынос", "вызыв", "раствор", "достиг", "заключа", "связа",
                       "позволя", "сниж", "возраст", "определя", "облада", "превыш",
                       "получен", "обусловл", "привод", "характер", "присутств", "свойств")
        _has_pred = any(root in low for root in _PRED_ROOTS)
        # сравнение: «X быстрее/выше... чем Y» — сравнительный факт
        _is_cmp = bool(re.search(r"\b(быстрее|выше|ниже|больше|меньше|лучше|хуже|превосходит)\b.+\bчем\b", low))
        # хеджинг: «предположительно/по-видимому/вероятно» + факт-слово
        _is_hedged = any(h in low for h in ("предположительно", "по-видимому", "вероятно", "возможно"))
        if _has_pred or _is_cmp:
            claims.append({
                "class": "A_claim_candidate",
                "text": s.strip()[:120],
                "start": s_start,
                "end": s_end,
                "sentence_idx": si,
                "raw_span": s.strip(),
                "hedged": _is_hedged or None,
            })
    return claims


# ------------------------- main -------------------------

def extract_all(text: str, para_id: str = "PAR_000", page: int | None = None) -> ExtractionResult:
    res = ExtractionResult()
    res.claims = extract_claims_a(text, para_id)
    # добавить page координату каждому claim
    if page is not None:
        for c in res.claims:
            c["page"] = page
    res.objects = extract_object_b(text, para_id, 0)
    res.discourse = extract_discourse_c(text)
    res.style = extract_style_d(text)
    res.tail = _compute_tail(text, res)
    return res


def _compute_tail(text: str, res: ExtractionResult) -> list[str]:
    """Остаток: слова, не попавшие в извлечение (предлоги, дефисы, союзы, частицы).

    Простая эвристика: ищем короткие служебные слова (<5 букв) и не буквенные хвосты
    (дефисы, точки, скобки), не поглощённые выше.
    """
    tail = []
    # слова из 1-4 букв (предлоги/союзы/частицы)
    for m in re.finditer(r"\b(?:в|на|с|по|от|для|и|а|но|или|при|к|из|до|о|об|не|же|то|бы|ли)\b", text, re.I):
        tail.append(("particle", m.group(0)))
    # одиночные точки/дефисы/скобки (не в числах)
    for m in re.finditer(r"[\.—–\-]{1,3}|[()]|[:,;]", text):
        tail.append(("symbol", m.group(0)))
    # дедупликация порядка (сохранить порядок)
    seen = set()
    dedup = []
    for t, w in tail:
        key = (t, w)
        if key not in seen:
            seen.add(key)
            dedup.append({"class": t, "raw": w})
    return dedup[:30]


def to_yaml(res: ExtractionResult) -> str:
    import yaml
    return yaml.dump({
        "claims": res.claims,
        "objects": res.objects,
        "discourse": res.discourse,
        "style": res.style,
        "tail": res.tail,
    }, allow_unicode=True, sort_keys=False, default_flow_style=False)


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        txt = open(sys.argv[1], encoding="utf-8").read()
    else:
        txt = "Пример: сталь 12Х18Н10Т после закалки при 1100°С показывает высокое сопротивление."
    r = extract_all(txt, "DEMO")
    print(to_yaml(r))