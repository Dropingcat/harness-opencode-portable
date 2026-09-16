"""Linguo harness — детерминированный разбор падежей, частей речи, связок.

Код (не LLM): базовый лингвистический слой, который ВСЕГДА работает.
LLM получает эти результаты как контекст и только ДОПОЛНЯЕТ семантику
(фигуры/хрия), не угадывая базовое.

Заполняет: G10 (vocabulary), G11 (morphology/forensics), G3 (связки).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ------------------------- Части речи (суффиксные эвристики) -------------------------

# Словари суффиксов для русского существительного по падежам
# (для металловедческого корпуса)
_NOUN_SUFFIXES = {
    "nom": r"(?:ость|ение|ация|ство|мет|мость|ность|з)$",     # прочность, закалка(а), метод
    "gen": r"(?:а|ы|ей|ов|ев|ий)$",                            # стали, методы, свойств => см. exclude
    "dat": r"(?:у|ам|ям)$",
    "acc": r"(?:у|ю|ы)$",
    "instr": r"(?:ой|ом|ами|ями)$",
    "prep": r"(?:е|ах|ях)$",
}

_NOUN_GENITIVE_EXCLUDE = {  # уже не деепричастия (см. philologcal)
    "свойств", "перспектив", "ионов", "образов", "уровней", "результатов", "условий",
    "способов", "методов", "сталей", "растворов", "кристаллов", "частиц", "полимеров",
    "оксидов", "сульфидов", "карбидов", "нитридов", "силикатов",
}

# Суффиксы глаголов (инфинитив, личные формы)
_VERB_SUFFIX = r"(?:ть|ться|ит|ат|ят|ут|ют|ил|ала|или|ено|ано|еть|ует|ает|ет|ирует)"
# Причастия/деепричастия
_PARTICIPLE_SUFFIX = r"(?:щий|вший|вшийся|нный|тый|емая|имый|ующий|аемый)"
_ADJECTIVE_SUFFIX = r"(?:ый|ой|ая|ое|ые|ий|ого|ому|ым|ими)"
_ADVERB_SUFFIX = r"(?:но|чески|о|е)$"
_PRONOUNS = {"это","этот","эта","эти","он","она","они","его","её","ее","их","свой","своей","такой","такую"}


def pos_of(word: str) -> str:
    """Определить часть речи по суффиксам (русский, научный корпус)."""
    w = word.lower()
    if w in _PRONOUNS:
        return "pron"
    if re.search(_PARTICIPLE_SUFFIX, w):
        return "participle"
    if re.search(_VERB_SUFFIX, w):
        return "verb"
    if re.search(_ADJECTIVE_SUFFIX, w):
        return "adj"
    if re.search(r"(?:на|по|к|из|от|о|об|при|до|с|в|у|за|над|под|без|для|между)$|^(?:и|а|но|или|не|же|ли|что)$", w):
        return "func"
    if re.search(r"(?:ость|ение|ация|ция|ство|мет|мость|ность|а|ы|и|й|о|е|у|ом|ами|ей|ев|ов)$", w):
        return "noun"
    return "unknown"


def padezh(word: str) -> str | None:
    """Определить падеж существительного по суффиксу (грубо, научный корпус).

    НЕ точная лингвистика: только для статистики G11, не для семантики."""
    w = word.lower()
    if w in _NOUN_GENITIVE_EXCLUDE:
        return "gen"
    for case, rx in _NOUN_SUFFIXES.items():
        if re.search(rx, w):
            return case
    return None


# ------------------------- Связки (пары/предлоги/союзы) -------------------------

# Сильные связки: причинно-следственные, противопоставительные, временные, выводные
_CONNECTOR_CAUSAL = ("поскольку", "так как", "вследствие", "благодаря", "из-за", "в силу", "потому что")
_CONNECTOR_CONTRAST = ("однако", "но", "вместе с тем", "в отличие от", "напротив", "тогда как", "хотя")
_CONNECTOR_ADDITIVE = ("кроме того", "при этом", "также", "в том числе", "в частности", "наряду с")
_CONNECTOR_TEMPORAL = ("после", "до", "в течение", "при", "во время", "после того как")
_CONNECTOR_CONCLUSIVE = ("таким образом", "следовательно", "итак", "в результате", "в итоге", "значит")
_CONNECTOR_COMPARATIVE = ("чем", "как", "подобно", "аналогично", "так же как")

def detect_connector(text: str) -> list[dict]:
    """Детерминированный словарь связок: (marker, type, span)."""
    res = []
    low = text.lower()
    groups = [
        ("causal", _CONNECTOR_CAUSAL), ("contrast", _CONNECTOR_CONTRAST),
        ("additive", _CONNECTOR_ADDITIVE), ("temporal", _CONNECTOR_TEMPORAL),
        ("conclusive", _CONNECTOR_CONCLUSIVE), ("comparative", _CONNECTOR_COMPARATIVE),
    ]
    for ctype, markers in groups:
        for m in markers:
            idx = low.find(m)
            if idx >= 0:
                res.append({"marker": m, "type": ctype, "start": idx, "end": idx + len(m)})
                break  # одна связка типа на абзац (sparsify)
    return res


# ------------------------- Статистика по ЧР/падежам -------------------------

@dataclass
class LinguoHarnessResult:
    pos_counts: dict = field(default_factory=dict)
    padezh_counts: dict = field(default_factory=dict)
    connectors: list = field(default_factory=list)
    sentence_count: int = 0


def harness_analyze(text: str) -> LinguoHarnessResult:
    from c1_c2_structure import _split_sentences
    sentences = _split_sentences(text)
    words = re.findall(r"[а-яёa-z]+", text.lower())
    res = LinguoHarnessResult(sentence_count=len(sentences))
    for w in words:
        p = pos_of(w)
        res.pos_counts[p] = res.pos_counts.get(p, 0) + 1
        if p == "noun":
            case = padezh(w)
            if case:
                res.padezh_counts[case] = res.padezh_counts.get(case, 0) + 1
    res.connectors = detect_connector(text)
    return res


def to_dict(res: LinguoHarnessResult) -> dict:
    total = max(1, sum(res.pos_counts.values()))
    return {
        "pos_ratios": {k: round(v / total, 3) for k, v in sorted(res.pos_counts.items(), key=lambda x: -x[1])},
        "padezh_counts": res.padezh_counts,
        "connectors": res.connectors,
        "sentence_count": res.sentence_count,
    }