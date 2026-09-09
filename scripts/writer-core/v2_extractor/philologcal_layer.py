"""Philological layer: морфология, стилистические фигуры, хрия-рубрикатор, акценты.

Детерминированный слой (pymorphy2 + словари маркеров) для обратного анализа
текста: раскладываем абзац на лингвистические и риторические составляющие.

Векторы:
  1) Лингвистический: лексика → морфология → синтаксис → фигуры → тропы
  2) Композиционный: хрия (8 частей) → акценты → последовательность подачи

Из docs/29 (philological layer). Без LLM — быстрый слой; gemma усиливает.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# pymorphy2 лениво (тяжёлый)
_morph = None


def _get_morph():
    global _morph
    if _morph is None:
        import pymorphy2
        _morph = pymorphy2.MorphAnalyzer()
    return _morph


# ------------------------- Хрия: 8 частей -------------------------

# Маркеры каждой части хрии (адаптировано для научного текста)
CHREIA_PARTS = {
    "preface": {  # 1. Приступ
        "markers": ["рассмотрим", "в данной", "настоящая", "цель данной", "введение", "рассмотрены"],
        "re": None,
    },
    "thesis": {  # 2. Тезис/парафразис
        "markers": ["заключается", "состоит в", "тезис", "суть", "представляет собой", "является"],
        "re": None,
    },
    "cause": {  # 3. Причина
        "markers": ["поскольку", "так как", "вследствие", "из-за", "обусловлен", "потому что", "причиной"],
        "re": None,
    },
    "contrary": {  # 4. Противное
        "markers": ["однако", "в отличие", "напротив", "вместе с тем", "но не", "в противоположность"],
        "re": None,
    },
    "analogy": {  # 5. Подобие
        "markers": ["аналогично", "подобно", "так же как", "таким же образом", "по аналогии"],
        "re": None,
    },
    "example": {  # 6. Пример
        "markers": ["например", "к примеру", "в частности", "иллюстрирует", "так, "],
        "re": None,
    },
    "evidence": {  # 7. Свидетельство (данные/источник)
        "markers": ["по данным", "согласно", "в работе", "исследовани", "показано", "установлено", "автор [", "[1"],
        "re": r"\d+[,.]\d+|\b(?:г\.|%|мг|мм|мкм|МПа)\b",
    },
    "conclusion": {  # 8. Заключение
        "markers": ["таким образом", "следовательно", "вывод", "итог", "в результате", "следовательно"],
        "re": None,
    },
}


def _detect_chreia(sentences: list[str]) -> list[dict]:
    """Обратный анализ: размечаем части хрии по маркерам."""
    parts = []
    for si, s in enumerate(sentences):
        low = s.lower()
        hit_part = None
        for part_name, cfg in CHREIA_PARTS.items():
            if cfg["re"] and re.search(cfg["re"], s):
                hit_part = part_name
                break
            if any(mk in low for mk in cfg["markers"]):
                hit_part = part_name
                break
        if hit_part:
            parts.append({"sentence_idx": si, "part": hit_part, "text": s.strip()[:80]})
    return parts


# ------------------------- Стилистические фигуры -------------------------

def _detect_figures(sentences: list[str]) -> list[dict]:
    figures = []
    for si, s in enumerate(sentences):
        # Антитеза: "не X, а Y" / "X, но Y"
        if re.search(r"\bне\b.+(?:,|$)\s*а\s+\w", s) or re.search(r"(?:—|–)\s*(?:не|а)\s+", s):
            figures.append({"type": "antithesis", "sentence_idx": si, "text": s.strip()[:80]})
        # Градация: перечисления с усилением (3+ однородных слова, не числа)
        if re.search(r"\w+,\s*\w+,\s*\w+(?:,\s*\w+)?", s) and len(re.findall(r",", s)) >= 2:
            _parts = [p for p in re.split(r"[,;]", s) if p.strip()]
            # первый элемент — слово (не число), и есть слово в перечислении
            _first_is_word = bool(re.search(r"[а-яёa-z]{4,}", _parts[0])) if _parts else False
            _has_words = sum(1 for p in _parts if re.search(r"[а-яёa-z]{4,}", p)) >= 2
            if _first_is_word and _has_words:
                figures.append({"type": "gradation_enumeration", "sentence_idx": si, "text": s.strip()[:80]})
        # Повтор: одинаковое слово 2+ раз (ТОЛЬКО слова, не числа/годы)
        words = re.findall(r"[а-яёa-z]{4,}", s.lower())
        from collections import Counter
        cnt = Counter(words)
        reps = [w for w, c in cnt.items() if c >= 2 and not w.isdigit() and not re.fullmatch(r"\d{4}", w)]
        if reps:
            figures.append({"type": "repetition", "words": reps[:3], "sentence_idx": si, "text": s.strip()[:80]})
        # Инверсия: наречие/дополнение в начале перед подлежащим (слабая эвристика)
        if re.match(r"^(?:важно|особенно|прежде всего|только|именно)", s.lower()):
            figures.append({"type": "fronting_emphasis", "sentence_idx": si, "text": s.strip()[:80]})
        # Парцелляция: короткое предложение (2-4 слова) ПОСЛЕ полного длинного,
        # с глаголом в фрагменте (docs/30 §5.1: «Вязкость разрушения» — НЕ фигура).
        if 2 <= len(s.split()) <= 4 and si > 0:
            prev = sentences[si - 1]
            prev_long = len(prev.split()) >= 6
            prev_has_verb = bool(re.search(r"\b(?:был|была|были|составляет|является|показывает|проявляет|имеет|обладает)\b", prev.lower()))
            frag_has_verb = bool(re.search(r"\b(?:есть|был|была|будет|значит|следует|является|представляет|обеспечивает|повышает|снижает|имеет|дает|позволяет|не) \b|\b(?:а|но|и)\b", s.lower()))
            if prev_long and (prev_has_verb or frag_has_verb):
                figures.append({"type": "parcellation", "sentence_idx": si, "text": s.strip()[:80]})
    return figures


# ------------------------- Морфология -------------------------

def _morph_stats(text: str) -> dict:
    """Части речи, залог, причастия — статистика по тексту.

    Суффиксные эвристики (без pymorphy2, несовместим с py3.12).
    Известные ловушки: генитив множественного числа рус. сущ. оканчивается на -в
    («свойств», «перспектив», «ионов»), НЕ является деепричастием.
    """
    words = re.findall(r"[а-яёa-z]+", text.lower())
    total = max(1, len(words))

    # СТОП-словарь существительных на -в (генитив мн.ч.), исключая их из деепричастий
    _NOUN_GENITIVE_EXCLUDE = {"свойств", "перспектив", "ионов", "образов", "уровней",
                              "результатов", "условий", "способов", "методов", "сталей",
                              "растворов", "кристаллов", "частиц", "полимеров", "оксидов",
                              "сульфидов", "карбидов", "нитридов", "силикатов"}

    def _is_gerund(w: str) -> bool:
        if w in _NOUN_GENITIVE_EXCLUDE:
            return False
        # деепричастия: (а|я|в|вши|ши) после глагольной основы
        # Формы: "повышая", "получая", "снижая", "показав", "установив", "изучив"
        if re.search(r"(?:ая|яв|ив|ав|вши|ши)$", w) and len(w) > 6:
            # исключить сущ. родительного падежа на -в/-ей без глагольного маркера
            if not re.search(r"(?:вая|ющая|яя|ая|ив$|вши$)", w):
                return False
            return True
        return False

    participle = sum(1 for w in words if re.search(r"(?:щий|вший|вшийся|нный|тый|емая|имый|ющий|аемый)$", w))
    passive_part = sum(1 for w in words if re.search(r"(?:нн(?:ый|ая|ое|ые)|енн(?:ый|ая|ое|ые)|т(?:ый|ая|ое|ые))$", w))
    gerund = sum(1 for w in words if _is_gerund(w))
    kantseliarit = sum(1 for w in words if re.search(r"(?:ение|ация|изация|ство|ость)$", w))
    function_words = sum(1 for w in words if w in _FUNCTION_WORDS)
    nouns_like = sum(1 for w in words if re.search(
        r"(?:ость|ение|ация|ция|мет|ность|сталь|азот|сплав|трещин|скорост|сопротив|закалк|раствор|нагрев|переход|данн|свойств|предел|прочност|температур|проход|осадк|вальц|деформац|содержа|структур|институт|образован|исследов|учрежд|организац)$", w))
    verbs_like = sum(1 for w in words if re.search(r"(?:ть|ется|ются|ил|ала|или|ено|ано|облада|составл|проявл|повыш|сниж|обеспеч|вызыва|привод|позволя|соответств)$", w))

    return {
        "word_count": total,
        "participle_ratio": round(participle / total, 3),
        "passive_participle_ratio": round(passive_part / total, 3),
        "gerund_ratio": round(gerund / total, 3),
        "kantseliarit_ratio": round(kantseliarit / total, 3),
        "function_word_ratio": round(function_words / total, 3),
        "noun_like_ratio": round(nouns_like / total, 3),
        "verb_like_ratio": round(verbs_like / total, 3),
    }

    return {
        "word_count": total,
        "participle_ratio": round(participle / total, 3),
        "passive_participle_ratio": round(passive_part / total, 3),
        "gerund_ratio": round(gerund / total, 3),
        "kantseliarit_ratio": round(kantseliarit / total, 3),   # канцелярит (отглаг. сущ.)
        "function_word_ratio": round(function_words / total, 3),
        "noun_like_ratio": round(nouns_like / total, 3),
        "verb_like_ratio": round(verbs_like / total, 3),
    }


_FUNCTION_WORDS = {
    "в", "на", "с", "по", "от", "для", "и", "а", "но", "или", "при", "к", "из",
    "до", "о", "об", "не", "же", "то", "бы", "ли", "если", "что", "когда",
    "как", "так", "уже", "еще", "только", "все", "это", "его", "ее", "их",
}


# ------------------------- Коннекторы/переходы -------------------------

_CONNECTORS = ["однако", "таким образом", "кроме того", "следовтельно", "поэтому",
               "в то время как", "в частност", "то есть", "в свою очередь", "венместе с тем",
               "вместе с тем", "при этом", "вследствие", "в связи с", "поскольку",
               "несмотря на", "в отличие от", "наряду с", "следовательно", "итак",
               "например", "напротив", "тогда как", "чем", "либо", "а также", "или"]
def _detect_connectors(sentences: list[str]) -> list[dict]:
    res = []
    for si, s in enumerate(sentences):
        low = s.lower()
        for c in _CONNECTORS:
            if c in low:
                res.append({"связка": c, "sentence_idx": si})
                break
    return res


# ------------------------- Сборка -------------------------

@dataclass
class PhilologicalResult:
    morphology: dict = field(default_factory=dict)
    figures: list[dict] = field(default_factory=list)
    chreia: list[dict] = field(default_factory=list)
    connectors: list[dict] = field(default_factory=list)
    emphasis: list[dict] = field(default_factory=list)


def analyze(text: str) -> PhilologicalResult:
    from c1_c2_structure import _split_sentences
    sentences = _split_sentences(text)
    res = PhilologicalResult()
    res.morphology = _morph_stats(" ".join(sentences))
    res.figures = _detect_figures(sentences)
    res.chreia = _detect_chreia(sentences)
    res.connectors = _detect_connectors(sentences)
    # акценты = fronting/emphasis фигуры + повтор
    res.emphasis = [f for f in res.figures if f["type"] in ("fronting_emphasis", "repetition")]
    return res


def to_yaml(res: PhilologicalResult) -> str:
    import yaml
    return yaml.dump({
        "morphology": res.morphology,
        "figures": res.figures,
        "chreia_parts": res.chreia,
        "connectors": res.connectors,
        "emphasis": res.emphasis,
    }, allow_unicode=True, sort_keys=False, default_flow_style=False)


if __name__ == "__main__":
    import sys
    txt = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else "Однако сталь не проявляет склонности к МКК после закалки, поскольку образуется аустенитная структура."
    r = analyze(txt)
    print(to_yaml(r))