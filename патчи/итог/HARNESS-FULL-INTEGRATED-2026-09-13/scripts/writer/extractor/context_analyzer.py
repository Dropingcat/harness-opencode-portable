"""Context analyzer — исследование ОКРЕСТНОСТЕЙ (как в researcher EvidenceSpan).

Вместо жёстких отрубов по одному маркеру:
  - смотрим context_before / context_after для каждого кандидата
  - принимаем решение по окружению (слова до/после, секция, предложение)
  - возвращаем вердикт + обоснование (почему принято/отклонено)

Паттерн заимствован у researcher_core: EvidenceSpan(exact_text, locator) + guard.
Применяется к нашим 4 проблемам:
  1. repetition — проверка: реальная риторика (анафора/эпифора) или терминология?
  2. evidence-хрия — только при источнике по близости (context_after «[12]»/«по данным»)
  3. padezh/pos — решение по слову+окрестности (согласование)
  4. connectors — границы по контексту (не substring внутри слова)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ------------------------- Окрестности -------------------------

@dataclass
class Context:
    """Окрестность вокруг span: слова/токены до и после."""
    before: list[str] = field(default_factory=list)   # слова до (до 5)
    after: list[str] = field(default_factory=list)    # слова после (до 5)
    sentence: str = ""
    full_text: str = ""
    position: int = 0


def get_context(text: str, start: int, end: int, window: int = 5) -> Context:
    """Собрать окрестность span (как context_before/after в EvidenceSpan)."""
    words_pos = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"[\w\-]+|[.,;:!?()\[\]]", text)]
    before, after = [], []
    for ws, we, w in words_pos:
        if we <= start:
            before.append(w)
        elif ws >= end:
            after.append(w)
            if len(after) >= window:
                break
    return Context(before=before[-window:], after=after[:window],
                   sentence=_sentence_at(text, start, end), full_text=text, position=start)


def _sentence_at(text: str, start: int, end: int) -> str:
    """Найти предложение, содержащее span (не резать по десятичной точке)."""
    # границы: предложения разделяются ". " (точка+пробел/заглавная) или \n, ;
    # но НЕ "0.5" (точка внутри числа)
    s0 = start
    while s0 > 0:
        ch = text[s0 - 1]
        if ch in "\n;":
            break
        if ch == ".":
            # точка — граница, если после неё пробел и НЕ цифра/буква числа
            nxt = text[s0] if s0 < len(text) else ""
            if nxt in " \t" or nxt in ")\"'":
                # проверим, что до точки не цифра (число 0.5)
                prev = text[s0 - 2] if s0 >= 2 else ""
                if not prev.isdigit() and not (nxt.isdigit()):
                    break
        s0 -= 1
    e0 = end
    while e0 < len(text):
        ch = text[e0]
        if ch in "\n;":
            break
        if ch == ".":
            prev = text[e0 - 1] if e0 > 0 else ""
            nxt = text[e0 + 1] if e0 + 1 < len(text) else ""
            if not prev.isdigit() and not nxt.isdigit():
                break
        e0 += 1
    return text[s0:e0].strip()


def has_marker_in_window(ctx: Context, markers: tuple[str, ...], window: int = 5) -> str | None:
    """Есть ли источник/маркер в ОКРЕСТНОСТИ (before+after слова, не всё предложение)."""
    near = " ".join(ctx.before + ctx.after).lower()
    for m in markers:
        if m in near:
            return m
    return None


# ------------------------- 1. Repetition: риторика vs терминология -------------------------

_STOP_TERMS = {  # частые термины главы — НЕ риторический повтор
    "азотирован", "стале", "сталь", "поверхност", "азот", "скорост", "рисунок",
    "обработк", "структур", "свойств", "метод", "результат", "данн", "инструмент",
    "температур", "слоя", "фаз", "сплав", "образц", "прочност", "механизм", "стадия",
    "процесс", "схема", "переход", "образован", "раствор", "закалк", "термическ",
}

_RHETORIC_REPEAT = [  # анафора/эпифора/немедленный повтор
    re.compile(r"\b(\w{4,})\b\s+\b\1\b"),                     # слово слово (немедленно)
    re.compile(r"^\s*(\w{4,})\b.+\b\1\b[,.]", re.M),          # начало предложения повтор
]

def is_rhetorical_repetition(word: str, sentence: str, ctx: Context) -> bool:
    """Проверить, реальный ли риторический повтор ИМЕННО этого слова (не чужой)."""
    w = word.lower()
    # 1) стоп-термины технического словаря
    if w in _STOP_TERMS or any(w.startswith(st) for st in _STOP_TERMS):
        return False
    low = sentence.lower()
    # 2) именно ЭТО слово повторено (не другой токен)
    occ = len(re.findall(r"\b" + re.escape(w) + r"\b", low))
    if occ < 2:
        return False
    # 3) немедленный повтор «W W»
    if re.search(r"\b" + re.escape(w) + r"\b\s+\b" + re.escape(w) + r"\b", low):
        return True
    # 4) анафора: слово в начале двух клауз (после запятой/точки)
    if re.search(r"(?:^|[.,;:])\s*" + re.escape(w) + r"\b[^.,;:]*[.,;:]\s*" + re.escape(w) + r"\b", low):
        return True
    return False


# ------------------------- 2. Evidence-хрия: требовать источник близко -------------------------

_SOURCE_MARKERS = ("по данным", "согласно", "в работе", "автор", "[", "по результатам",
                   "показано", "установлено", "в статье", "исследование показало", "по сообщению")

def evidence_is_supported(ctx: Context, has_number: bool) -> bool:
    """Evidence-часть ХРИИ обоснована, если рядом источник (не просто число)."""
    m = has_marker_in_window(ctx, _SOURCE_MARKERS)
    if m:
        return True
    # число — только с источником, иначе это данные/измерение, а не "свидетельство"
    if has_number and not m:
        return False
    return False


# ------------------------- 3. Падеж/ЧР: контекст-согласование -------------------------

_PREP_TO_CASE = {  # предлоги, требующие падежа
    "к": "dat", "по": "dat", "до": "gen", "из": "gen", "от": "gen",
    "с": "gen", "в": "acc", "на": "acc", "за": "acc", "при": "prep",
    "о": "prep", "об": "prep", "между": "instr", "над": "instr", "перед": "instr",
}

def infer_case_from_context(word: str, ctx: Context) -> str | None:
    """Падеж по предлогу/следующему слову в окрестности (согласование), не по суффиксу."""
    for prep in ctx.before:
        p = prep.lower().rstrip(",")
        if p in _PREP_TO_CASE:
            return _PREP_TO_CASE[p]
    return None  # нет предлога — неопределённо (не выдаём ложное)


# ------------------------- 4. Connector: границы по контексту -------------------------

def connector_clean(ctx: Context, marker: str) -> bool:
    """Проверить, что маркер связки — настоящее слово (не внутри «карбидов»)."""
    # слово-кандидат должно быть изолировано пробелами/пунктуацией
    low_sent = ctx.sentence.lower()
    return bool(re.search(r"(?<![а-яёa-z])" + re.escape(marker) + r"(?![а-яёa-z])", low_sent))


# ------------------------- Вердикт -------------------------

@dataclass
class ContextVerdict:
    accept: bool
    reason: str
    context: Context | None = None