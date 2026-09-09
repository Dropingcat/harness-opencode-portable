"""Claim QA — контроль качества извлечённых клаймов.

Задача: гарантировать, что извлечённые claims НЕ галлюцинация, и точную сортировку.

Три механизма:
  1. SPAN-GROUNDING — каждое извлечённое утверждение обязано реально присутствовать
     в исходном тексте (normalized substring/fuzzy). Не найден -> UNGROUNDED -> rejected.
  2. АНТИХРУПКОСТЬ — fuzzy-нормализация (типогр. единицы, дефисы, цифры) перед сравнением,
     чтобы не отбрасывать верное из-за «0,1 – 0,4» vs «0,1-0,4».
  3. ТИПИЗАЦИЯ — детерминированная классификация claim по уровням (A/B/C/D)
     и strength/role НЕ на слово LLM, а по правилам поверх извлечённого.

Принцип (инвариант): LLM ПРЕДЛАГАЕТ, код ПРИНИМАЕТ/ОТКЛОНЯЕТ.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ------------------------- нормализация (антихрупкость) -------------------------

_NUM_TYPO = {  # типографические эквиваленты
    "–": "-", "—": "-", "−": "-", " ": "",
    ",": ".", "·": ".", "х": "x", "×": "x",
    "о": "o",  # in "оС" -> "oC"? careful: keep ru words; только в числе-контексте
}


def _norm_with_offsets(s: str) -> tuple[str, list[int]]:
    """Нормализация + соответствие каждый символ норм.строки → смещение в оригинале.

    Возвращает (норм_строка, карта_оффсетов), где карта_оффсетов[i] = смещение
    в оригинале символа норм_строки[i] (для букв/цифр). Пробелы не включены
    в карту (они «невидимы»).
    """
    out_chars: list[str] = []
    offsets: list[int] = []
    prev_space = False
    for i, ch in enumerate(s.lower()):
        # диапазоны: замена тире на - и убрать пробелы вокруг
        if ch in "–—−":
            # убрать незакрытый пробел перед дефисом
            if out_chars and out_chars[-1] == " ":
                out_chars.pop()
                offsets.pop()
            out_chars.append("-")
            offsets.append(i)
            prev_space = False
            continue
        if ch in " \t\n\r\u00a0\u2009\u202f":
            # переносы строк/неразрывные пробелы (OCR-абзацы!) = обычный пробел,
            # чтобы дословный claim с нормализованными пробелами находился в источнике
            if out_chars and out_chars[-1] == "-":
                continue  # "0,1-0,4" (без пробела после дефиса)
            if out_chars and not prev_space and out_chars[-1] not in "-":
                out_chars.append(" ")
                offsets.append(i)
            prev_space = True
            continue
        prev_space = False
        out_chars.append(ch)
        offsets.append(i)
    return "".join(out_chars), offsets


def _norm(s: str) -> str:
    """Обёртка: нормализация (без оффсетов) для быстрых проверок."""
    return _norm_with_offsets(s)[0]


def _un_norm_offset(original: str, norm_position: int) -> int:
    """Обратный маппинг: позиция в норм.строке -> смещение в оригинале (по карте)."""
    if norm_position is None:
        return None
    _, offsets = _norm_with_offsets(original)
    # norm_position может указывать на 1 за концом
    if norm_position < len(offsets):
        return offsets[norm_position]
    return len(original)


def _norm_range(original: str, start_pos: int, end_pos: int) -> tuple[int, int]:
    """Прямой маппинг диапазона оригинал -> норм (для fast substring)."""
    # упрощение: используем индекс символа как есть (релевантно при наличии пробелов)
    _, offsets = _norm_with_offsets(original)
    # ищем ближайший оффсет >= start в карте
    s = next((j for j, off in enumerate(offsets) if off >= start_pos), 0)
    e = next((j for j, off in enumerate(offsets) if off >= end_pos), len(offsets))
    return s, e


def _strip_units(s: str) -> str:
    """Нормализовать числа: к канонической форме (не стирать числа!).
    Типографика единиц: «мг/м²ч» == «мг/м2ч», оС == °C, % не стираем.
    Пробелы СХЛОПЫВАЕМ в один, но НЕ удаляем — иначе токены склеиваются
    через границы слов/предложений и token-покрытие падает."""
    s = re.sub(r"\s+", " ", s)
    s = s.replace(",", ".")
    s = s.replace("²", "2").replace("³", "3")
    s = s.replace("°с", "°c").replace("оС", "°c").replace("ос", "°c")
    # единицы с «/»: нормализуем separator
    s = s.replace("/", "/")
    return s.lower()


def _tok(s: str) -> set[str]:
    return set(w for w in re.findall(r"[а-яёa-z0-9./%°-]+", s.lower()))


def _at_word_boundary(ns: str, start: int, end: int) -> bool:
    """Совпадение не «разрезает» слово: слева/справа пробел или край строки."""
    left_ok = start == 0 or ns[start - 1] in " \t"
    right_ok = end >= len(ns) or ns[end] in " \t"
    return left_ok and right_ok


def span_grounded(claim_text: str, source_text: str, threshold: float = 0.7) -> bool:
    """Проверка: ядро claim-текста реально присутствует в источнике."""
    loc = span_locate(claim_text, source_text, threshold)
    return loc["method"] != "none"


def span_locate(claim_text: str, source_text: str, threshold: float = 0.7) -> dict:
    """Найти ТОЧНЫЙ span (start/end) claim в источнике + способ (exact|fuzzy|none)."""
    ns, offsets = _norm_with_offsets(source_text)
    nc, _ = _norm_with_offsets(claim_text)

    # 1) exact substring в нормализованной строке (с границами слов)
    #    -> маппинг оффсетов через карту. Дословное предложение = exact.
    if nc in ns:
        n_start = ns.find(nc)
        n_end = n_start + len(nc)
        if _at_word_boundary(ns, n_start, n_end):
            start = offsets[n_start] if n_start < len(offsets) else 0
            end = offsets[n_end - 1] + 1 if n_end - 1 < len(offsets) and n_end - 1 >= 0 else len(source_text)
            return {"start": start, "end": end, "method": "exact", "confidence": 1.0}

    # 2) fuzzy: high token coverage
    ct = _tok(_strip_units(nc))
    st = _tok(_strip_units(ns))
    if len(ct) < 5:
        return {"start": None, "end": None, "method": "none", "confidence": 0.0}
    hit = sum(1 for t in ct if t in st)
    ratio = hit / len(ct)
    if ratio >= threshold:
        # найдём первое вхождение для старта и оффсет конца
        idxs = [ns.find(t) for t in ct if t in st]
        idxs = [i for i in idxs if i >= 0]
        if idxs:
            s_pos = min(idxs)
            e_pos = max(ns.rfind(t) + len(t) for t in ct if t in st and ns.rfind(t) >= 0)
            start = offsets[s_pos] if s_pos < len(offsets) else 0
            end = offsets[e_pos - 1] + 1 if 0 < e_pos <= len(offsets) else len(source_text)
            return {"start": start, "end": end, "method": "fuzzy", "confidence": round(ratio, 2)}
    return {"start": None, "end": None, "method": "none", "confidence": round(ratio, 2)}


# ------------------------- типизация (детерминированная) -------------------------

_ROLE_RULES = [
    (re.compile(r"\b(составля|равен|равна|достиг|показ|оказал|определен|выявлен|установлен)\b"), "данные"),
    (re.compile(r"\b(обеспечив|повыш|сниж|увелич|улучш|возраст)\b"), "факт"),
    (re.compile(r"\b(следует|рекоменд|целесообразн|необходимо|предлагает)\b"), "рекомендация"),
    (re.compile(r"\b(таким образом|следовательно|значит|вывод|итог)\b"), "вывод"),
]

_KIND_RULES = [
    (re.compile(r"\b(средня|скорост|предел|прочност|температур|толщин|концентрац|доз|расход)\b"), "QUANTITATIVE"),
    (re.compile(r"\b(образует|образован|распад|превращен|выделен)\b"), "MECHANISTIC"),
    (re.compile(r"\b(рекоменд|следует|необходимо|целесообраз)\b"), "RECOMMENDATION"),
    (re.compile(r"\b(по данным|согласно|в работе|исследован)\b"), "SOURCE_BASED"),
    (re.compile(r"\b(является|представляет собой|определяется как)\b"), "DEFINITIONAL"),
]


def _default_if_empty(v, default):
    return default if not v else v


def classify_claim(text: str, fallback_kind: str = "OBSERVATIONAL") -> dict:
    """Детерминированная типизация claims (не полагаемся на LLM)."""
    low = text.lower()
    role = None
    for rx, r in _ROLE_RULES:
        if rx.search(low):
            role = r
            break
    role = role or "факт"

    kind = None
    for rx, k in _KIND_RULES:
        if rx.search(low):
            kind = k
            break
    kind = kind or fallback_kind
    return {"role": role, "kind": kind}


# ------------------------- результат QA -------------------------

@dataclass
class QAVerdict:
    index: int                 # индекс исходного claim
    text: str
    grounded: bool
    role: str                  # данные/факт/рекомендация/вывод/стилистика
    kind: str
    status: str                # GROUNDED | UNGROUNDED | STYLE
    confidence: float          # 0..1 (доля токенов, если fuzzy)
    reason: str = ""


def qa_claims(claims: list[dict], source_text: str) -> tuple[list[QAVerdict], list[dict]]:
    """Пропустить claims через QC. Вернуть (verdicts, keep_only_grounded)."""
    verdicts: list[QAVerdict] = []
    keep: list[dict] = []
    for i, c in enumerate(claims):
        text = c.get("text", "") or c.get("proposition", "")
        grounded = span_grounded(text, source_text)
        cls = classify_claim(text, c.get("fallback_kind", "OBSERVATIONAL"))
        # количество слов в тексте для confidence
        words = len(re.findall(r"[а-яёa-z]+", text))
        conf = min(1.0, words / 8.0) if words else 0
        # role: если это стилистика (из филологической ветки) - пометить
        is_style = "стилистика" in str(c.get("role", "")).lower() or c.get("level") == "D"
        status = "UNGROUNDED" if not grounded else ("STYLE" if is_style else "GROUNDED")
        verdicts.append(QAVerdict(
            index=i, text=text[:80], grounded=grounded,
            role=cls["role"], kind=cls["kind"], status=status, confidence=round(conf, 2),
        ))
        # сохраняем ТОЛЬКО grounded (научные) + style-помечаем, но не в "научные"
        if grounded and not is_style:
            keep.append({**c, "role": cls["role"], "kind": cls["kind"], "qa_status": "GROUNDED"})
    return verdicts, keep


def qa_objects(objects: list[dict], source_text: str) -> list[dict]:
    """QC объектов: каждый raw обязан присутствовать в тексте (нормализованно)."""
    ok = []
    for o in objects:
        raw = o.get("raw", "")
        if not raw:
            continue
        # числа: значение (без единицы) в тексте есть? используем значение
        val = o.get("value_lower")
        probe = str(val).replace(".", ",") if val is not None else raw
        grounded = _norm(probe) in _norm(source_text) or _norm(raw) in _norm(source_text)
        if grounded:
            ok.append(o)
    return ok


def to_yaml(verdicts: list[QAVerdict], keep: list[dict]) -> str:
    import yaml
    return yaml.dump({
        "verdicts": [{"idx": v.index, "status": v.status, "role": v.role, "kind": v.kind,
                      "confidence": v.confidence, "text": v.text} for v in verdicts],
        "kept_grounded": keep,
    }, allow_unicode=True, sort_keys=False, default_flow_style=False)