#!/usr/bin/env python3
"""numeric_comparator.py — детерминированное сравнение чисел claim vs source.

4-слойный гибрид (см. numeric-layer-solutions.md):
  Слой 0 — реестр единиц (units.py) + размерности.
  Слой 1 — токенизатор: запятая-десятичный + классификатор классов
           (FORMULA / GRADE / MILLER / SCIENTIFIC / UNIT_VALUE / RANGE /
            PERCENT / PLAIN).
  Слой 2 — локальная иерархия разрешения конфликтов (per-token признаки).
  Слой 3 — парное выравнивание вместо cross-product + not_comparable
           вместо dimension-вердикта.

Использование:
    1. Как модуль: from numeric_comparator import compare_claim_sources
    2. Как скрипт: python3 numeric_comparator.py <claim.json> <sources.json> <output.json>
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import re
from pathlib import Path

import units
from units import convert as units_convert, dimension as units_dimension
from uncertainty import parse_uncertainty, compare_with_uncertainty
from formulas import detect_formula, check_constant

# ──────────────────────────── Слой 0: единицы ────────────────────────────
# Сырые единицы (как они встречаются в тексте) → канон units.py.
_UNIT_MAP = {
    "кДж": "kJ/mol", "kJ": "kJ/mol",
    "моль": "mol", "mol": "mol",
    "см": "cm", "cm": "cm",
    "мм": "mm", "mm": "mm",
    "nm": "nm", "нм": "nm",
    "мкм": "um", "µm": "um", "μm": "um",
    "Å": "angstrom", "ангстрем": "angstrom",
    "HV": "hv",
    "Н": "N", "N": "N",
    "°C": "celsius", "C": "celsius",
    "час": "hour", "hour": "hour", "ч": "hour", "h": "hour", "мин": "min",
    "Вт": "watt", "W": "watt", "кВт": "kW",
    "кПа": "kpa", "КПа": "kpa", "МПа": "mpa", "ГПа": "gpa", "кгс": "kgf",
    "рад": "rad", "rad": "rad", "°": "deg",
    "%": "percent", "раз": "ratio", "раза": "ratio", "times": "ratio",
}


def _normalize_unit(unit):
    """Маппит сырую единицу на словарь units.py; неизвестные — как есть."""
    if not unit:
        return unit
    if unit in _UNIT_MAP:
        return _UNIT_MAP[unit]
    try:
        return units.normalize_unit(unit)
    except ValueError:
        return unit


# ────────────────── Слой 1: классификатор классов (токенизация) ──────────────────

_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")

_ELEM = r"(?:[A-ZА-ЯЁ][a-zа-яё]?|[A-ZА-ЯЁ])"


def _find_formula_spans(text):
    """Химические формулы (стехиометрия): Fe2-3N, Fe₄N, Cr₂₃C₆, Fe₃O₄, ε-Fe₂₋₃N.

    Признаки: юникод-подстрочники ИЛИ паттерн элемент-цифра-элемент
    (≤2 символа элемент, периодическая таблица).
    """
    spans = []
    # юникод-подстрочники: слово из элементов с цифрами-подстрочниками
    for m in re.finditer(r"(?:[αβγεδ]'?[-–—])?" + _ELEM + r"(?:\d*[₀-₉]+)+" + _ELEM + r"\d*[₀-₉]*", text):
        spans.append(m.span())
    # стехиометрия с обычными цифрами: элемент-цифра-(-цифра)-элемент
    for m in re.finditer(
            r"(?<![A-Za-zА-Яа-я0-9])" + _ELEM + r"\d+[₀-₉]*"
            r"(?:[-–—₋]\d+[₀-₉]*)?"
            r"(" + _ELEM + r")\d*[₀-₉]*(?:[-–—₋]\d+[₀-₉]*)?", text):
        spans.append(m.span())
    return _merge_spans(spans)


def _find_grade_spans(text):
    """Марки сплавов/сталей: ВКС-10, ВКС‑10 (U+2011), ВКС10, Р18, Р6М5, 08Х18Н10Т."""
    spans = []
    # кириллическая буквенная группа + цифры (с дефисом или без): ВКС-10, Р18, Р6М5
    for m in re.finditer(
            r"(?<![A-Za-zА-Яа-я0-9])([А-ЯЁ]{1,3})[‑\-]?\d+"
            r"(?:[‑\-]?\d*[А-ЯЁ]{0,2}[а-яё]*\d*)*", text):
        spans.append(m.span())
    # цифра-буква-цифра-буква: 08Х18Н10Т
    for m in re.finditer(r"(?<![A-Za-zА-Яа-я0-9])\d{2}[А-ЯЁ]\d+[А-ЯЁ]\d+", text):
        spans.append(m.span())
    return _merge_spans(spans)


def _find_miller_spans(text):
    """Индексы Миллера: (220), (311), (222), β(110), [220], (110)α."""
    spans = []
    # β/d(число) — рефлекс
    for m in re.finditer(r"[ββdD]\s*\(\s*(\d{1,3})\s*\)", text):
        spans.append(m.span())
    # скобки сразу после слов отражени/рефлекс/плоскост/индекс
    for m in re.finditer(
            r"(?:отражени|рефлекс|плоскост|индекс)[^\d()]{0,20}\(\s*\d{1,3}\s*\)", text):
        spans.append(m.span())
    # трёхзначные числа в круглых/квадратных скобках (индексы решётки)
    for m in re.finditer(r"\((\d{3})\)", text):
        # не часть формулы (Fe,Cr)3W3C — там нет трёхзначного числа в скобках
        spans.append(m.span())
    for m in re.finditer(r"\[(\d{3})\]", text):
        spans.append(m.span())
    # (110)α / (111)γ — индекс + фаза
    for m in re.finditer(r"\(\s*(\d{1,3})\s*\)[αβγεδ]?", text):
        # отсекаем 1-2 значные, не являющиеся рефлексами (кроме β/d-контекста выше)
        n = m.group(1)
        if len(n) == 3:
            spans.append(m.span())
    return _merge_spans(spans)


def _merge_spans(spans):
    spans = sorted(spans)
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _in_spans(pos, spans):
    for s, e in spans:
        if s <= pos < e:
            return True
        if pos < s:
            return False
    return False


# единицы, которые могут идти СРАЗУ после числа (без пробела): 2000Вт, 540°C
_UNIT_TOKEN = (
    r"(?:кгс/мм²|кгс/мм2|кДж/моль|эВ/атом|eV/atom|см²/с|м²/с|см2/с|м2/с|"
    r"мкм|µm|μm|нм|nm|мм|mm|см|cm|м⁻²|м-2|м|m|кгс|кПа|КПа|МПа|ГПа|кВт|Вт|W|Å|"
    r"мин|min|час|часов|рад|rad|мас\.?\s*%|вес\.?\s*%|об\.?\s*%|"
    r"°C|°К|HV|°|%|раз|раза|times|ч|h|K|N|Н|C|мм/с|мм/мин|см²/с)"
)
_UNIT_TOKEN_NOSPACE = re.compile(r"(" + _UNIT_TOKEN + r")")
# единица с возможным пробелом; без \b — чтобы матчился и в конце строки (°, %)
_UNIT_AFTER = re.compile(r"\s*(" + _UNIT_TOKEN + r")(?![A-Za-zА-Яа-яЁё0-9])")
_RANGE_SEP = r"[-–—−]"


def _to_float(s):
    return float(s)


def _parse_scientific(mant, exp):
    if exp is None:
        return None
    exp = exp.translate(_SUPERSCRIPT).replace(" ", "")
    if exp.startswith("^"):
        exp = exp[1:]
    return mant * (10.0 ** float(exp))


def _detect_scientific(text, start, num):
    """Пытается распознать научную нотацию сразу после числа. Возвращает (value, span_end) или (None, start)."""
    m = re.match(r"\s*[×·xX*]\s*10\s*(\^?[-−]?\d+|[-−]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)", text[start:])
    if m:
        val = _parse_scientific(num, m.group(1))
        if val is not None:
            return val, start + m.end()
    return None, start


def _classify_numeric(text, excluded):
    """Сканирует числа и классифицирует их. Возвращает список dict-чисел."""
    numbers = []
    i = 0
    n = len(text)
    while i < n:
        if _in_spans(i, excluded) or not (text[i].isdigit()):
            i += 1
            continue
        # пропускаем многозначное число
        m = re.match(r"\d+(?:\.\d+)?", text[i:])
        if not m:
            i += 1
            continue
        raw = m.group(0)
        val = _to_float(raw)
        num_end = i + len(raw)

        # научная нотация: 1.2×10¹⁵
        sci_val, sci_end = _detect_scientific(text, num_end, val)
        if sci_val is not None:
            # единица после (м⁻²)
            unit_end = _UNIT_AFTER.match(text, sci_end)
            unit = ""
            if unit_end:
                unit = unit_end.group(1)
                sci_end = unit_end.end()
            numbers.append({"type": "scientific", "value": sci_val,
                            "unit": unit, "raw": text[i:sci_end]})
            i = sci_end
            continue

        # диапазон: low–high [unit] или "low to high" / "low до high"
        range_m = re.match(
            r"(?:\s*[-–—−]\s*|\s+to\s+|\s+до\s+|\s*→\s*)(\d+(?:\.\d+)?)", text[num_end:])
        if range_m:
            high_val = _to_float(range_m.group(1))
            after_high = num_end + range_m.end()
            unit_end = _UNIT_AFTER.match(text, after_high)
            unit = ""
            rng_end = after_high
            if unit_end:
                unit = unit_end.group(1)
                rng_end = unit_end.end()
            # пропускаем ГОСТ/номерные диапазоны
            if not _is_standard_range(val, high_val):
                numbers.append({"type": "range", "low": val, "high": high_val,
                                "unit": unit, "raw": text[i:rng_end]})
            i = rng_end
            continue

        # процент/раз (до единиц — это percent-класс, не UNIT_VALUE)
        # "мас. %", "вес. %", "об. %" — процент с квалификатором
        wpct = re.match(r"\s*(?:мас|вес|об|ат|мол)\.?\s*%", text[num_end:])
        if wpct:
            pct_end = num_end + wpct.end()
            numbers.append({"type": "percent", "value": val, "unit": "%",
                            "raw": text[i:pct_end]})
            i = pct_end
            continue
        pct_m = re.match(r"\s*(%|раз|раза|times|x)(?!\s*10)", text[num_end:])
        if pct_m:
            unit = pct_m.group(1)
            pct_end = num_end + pct_m.end()
            numbers.append({"type": "percent", "value": val, "unit": unit,
                            "raw": text[i:pct_end]})
            i = pct_end
            continue

        # единица сразу после числа без пробела: 2000Вт, 540°C, 10кПа
        ns = _UNIT_TOKEN_NOSPACE.match(text, num_end)
        if ns:
            unit = ns.group(1)
            uend = num_end + len(unit)
            numbers.append({"type": "single", "value": val, "unit": unit,
                            "raw": text[i:uend]})
            i = uend
            continue

        # единица с пробелом: 540 °C, 2–6 мкм, 10 кПа, 0,05°
        unit_end = _UNIT_AFTER.match(text, num_end)
        if unit_end:
            unit = unit_end.group(1)
            uend = unit_end.end()
            numbers.append({"type": "single", "value": val, "unit": unit,
                            "raw": text[i:uend]})
            i = uend
            continue

        # неопределённость: 77 ± 3
        pm_m = re.match(r"\s*[±]\s*(\d+(?:\.\d+)?)", text[num_end:])
        if pm_m:
            unc = _to_float(pm_m.group(1))
            after = num_end + pm_m.end()
            unit_end = _UNIT_AFTER.match(text, after)
            unit = ""
            if unit_end:
                unit = unit_end.group(1)
                after = unit_end.end()
            numbers.append({"type": "single", "value": val, "unit": unit,
                            "uncertainty": unc, "raw": text[i:after]})
            i = after
            continue

        # голое число (fallback) с фильтрами
        if _is_noise_number(raw, val, text, i, num_end):
            i = num_end
            continue
        # ведущий коэффициент у греческой буквы (2θ, 1,5 раза уже выше)
        if re.match(r"\s*[αβγδεθΩω]", text[num_end:]):
            i = num_end
            continue
        numbers.append({"type": "single", "value": val, "unit": "",
                        "raw": raw})
        i = num_end
    return numbers


def _is_standard_range(low, high):
    """ГОСТ/номерные диапазоны (90005-91, 2.45-2012) — не физические числа."""
    if low >= 10000 and high >= 10000:
        return True
    if low >= 10000 and high < 100:
        return True
    if low < 100 and high >= 10000:
        return True
    if 1800 <= high <= 2100 and low < 100:
        return True
    return False


def _is_noise_number(raw, val, text, start, end):
    """Голые числа-шум: годы, номера пунктов, части научной нотации, ГОСТ/ISO."""
    if raw.endswith("."):
        return True
    if 1800 <= val <= 2100:
        return True
    before = text[max(0, start - 14):start]
    after = text[end:end + 14]
    # стандарты: ISO 6507, ГОСТ 2.45-2012
    if re.search(r"\b(ISO|ГОСТ|ASTM|DIN|EN)\b", before):
        return True
    # научная нотация: мантисса (2.3 в 2.3·10) или показатель (10^)
    if re.search(r"[\^·×*]|=\s*$", before):
        return True
    if re.search(r"^\s*[·×xX*]\s*10\b|^\s*[eE][-+]\d", after):
        return True
    return False


def extract_numbers(text):
    """Извлекает числа и диапазоны из текста (Слои 1-2)."""
    if not text:
        return []
    # запятая = десятичный разделитель (рус. научный текст), до всех паттернов
    text = re.sub(r"(?<=\d)[,](?=\d)", ".", text)
    excluded = _find_formula_spans(text) + _find_grade_spans(text) + _find_miller_spans(text)
    excluded = _merge_spans(excluded)
    return _classify_numeric(text, excluded)


def extract_qualifier(text):
    """Извлекает квалификатор (для каких условий)."""
    qualifiers = []
    qualifiers_map = {
        "для всех": "universal",
        "для легированных": "alloyed_only",
        "для углеродистых": "carbon_only",
        "стандартный режим": "standard_mode",
        "стандартном режиме": "standard_mode",
        "при стандартном": "standard_mode",
        "до ": "up_to",
        "не более": "max",
        "не менее": "min",
        "типично": "typical",
        "обычно": "typical",
        "в зависимости": "conditional",
    }
    text_lower = text.lower()
    for keyword, qtype in qualifiers_map.items():
        if keyword in text_lower:
            qualifiers.append(qtype)
    return qualifiers if qualifiers else ["unspecified"]


def compare_ranges(claim_range, source_range, tolerance=0.1):
    """Сравнивает два диапазона. tolerance = допустимое отклонение (10%)."""
    c_low, c_high = claim_range["low"], claim_range["high"]
    s_low, s_high = source_range.get("low", source_range.get("value")), source_range.get("high", source_range.get("value"))
    if s_low is None or s_high is None:
        return "no_data"

    if s_low <= c_low and c_high <= s_high:
        return "match"
    if c_low <= s_high and s_low <= c_high:
        return "partial_match"
    deviation = max(abs(c_low - s_low), abs(c_high - s_high)) / max(c_high, s_high, 1)
    if deviation > tolerance:
        return "mismatch"
    return "partial_match"


def _value_in_range(val, unc, lo, hi):
    if unc:
        return (val - unc) <= hi and lo <= (val + unc)
    return lo <= val <= hi


def compare_value_to_range(val, unc, rng, tolerance=0.1):
    """Сравнивает одиночное значение (с неопределённостью) с диапазоном."""
    lo, hi = rng["low"], rng["high"]
    if _value_in_range(val, unc, lo, hi):
        return "match"
    deviation = max(abs(val - lo), abs(val - hi)) / max(abs(hi), 1)
    if deviation > tolerance:
        return "mismatch"
    return "partial_match"


def compare_single(claim_val, source_val, tolerance=0.1, claim_unc=None, source_unc=None):
    """Сравнивает два числа. tolerance = 10%.
    Если у обоих задана неопределённость — сравнивает интервалы через compare_with_uncertainty."""
    if source_val is None:
        return "no_data"
    if claim_unc is not None and source_unc is not None:
        result = compare_with_uncertainty(claim_val, claim_unc, source_val, source_unc)
        return {"MATCH": "match", "PARTIAL_MATCH": "partial_match",
                "MISMATCH": "mismatch", "NO_DATA": "no_data"}[result]
    deviation = abs(claim_val - source_val) / max(abs(claim_val), abs(source_val), 1)
    if deviation <= tolerance:
        return "match"
    elif deviation <= 0.2:
        return "partial_match"
    else:
        return "mismatch"


def compare_qualifiers(claim_quals, source_quals):
    """Сравнивает квалификаторы."""
    if "universal" in claim_quals and "universal" not in source_quals:
        return "qualifier_mismatch"
    if "standard_mode" in claim_quals and "standard_mode" not in source_quals:
        return "qualifier_mismatch"
    if "up_to" in source_quals and "universal" in claim_quals:
        return "qualifier_mismatch"
    return "match"


def get_source_text(source):
    """Возвращает текст источника: из файла локального корпуса (если есть) или из descriptor."""
    fpath = source.get("file")
    if fpath and Path(fpath).is_file():
        try:
            return Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
    return source.get("descriptor", source.get("title", ""))


# ──────────────────────────── Слой 3: парное выравнивание ────────────────────────────

def _kind(n):
    """Группа сравнения для выравнивания: single|range|percent."""
    t = n.get("type")
    if t == "percent":
        return "percent"
    if t == "range":
        return "range"
    return "single"


def _unit_of(n):
    return n.get("unit") or n.get("unit_raw") or ""


def _same_dim(a_unit, b_unit):
    """Сравнимы ли две единицы по размерности (одинаковая физическая величина)."""
    a = _normalize_unit(a_unit)
    b = _normalize_unit(b_unit)
    if not a or not b:
        return True  # голое число — сравниваем по равенству
    try:
        return units_dimension(a) == units_dimension(b)
    except ValueError:
        return False


def _pair_status(cn, sn):
    """Сравнивает пару чисел (после выравнивания). Возвращает статус."""
    ck, sk = _kind(cn), _kind(sn)
    # разные размерности — несравнимо (не вердикт)
    if not _same_dim(_unit_of(cn), _unit_of(sn)):
        return "not_comparable"

    if ck == "percent" and sk == "percent":
        return compare_single(cn["value"], sn["value"])

    if ck == "range" and sk == "range":
        return compare_ranges(cn, sn)

    if ck == "single" and sk == "single":
        cu, su = _unit_of(cn), _unit_of(sn)
        if cu == "" or su == "":
            # голое число — только точное совпадение (иначе шум)
            if cn["value"] == sn["value"]:
                return "match"
            return "not_comparable"
        if cu != su:
            try:
                converted = units_convert(cn["value"], _normalize_unit(cu), _normalize_unit(su))
            except ValueError:
                return "not_comparable"
            return compare_single(converted, sn["value"],
                                  claim_unc=cn.get("uncertainty"),
                                  source_unc=sn.get("uncertainty"))
        return compare_single(cn["value"], sn["value"],
                              claim_unc=cn.get("uncertainty"),
                              source_unc=sn.get("uncertainty"))

    # single ↔ range (одна размерность)
    if ck == "single" and sk == "range":
        cu, su = _unit_of(cn), _unit_of(sn)
        try:
            if cu and su and cu != su:
                cn = dict(cn)
                cn["value"] = units_convert(cn["value"], _normalize_unit(cu), _normalize_unit(su))
        except ValueError:
            return "not_comparable"
        return compare_value_to_range(cn["value"], cn.get("uncertainty"), sn)

    if ck == "range" and sk == "single":
        cu, su = _unit_of(cn), _unit_of(sn)
        try:
            if cu and su and cu != su:
                sn = dict(sn)
                sn["value"] = units_convert(sn["value"], _normalize_unit(su), _normalize_unit(cu))
        except ValueError:
            return "not_comparable"
        return compare_value_to_range(sn["value"], sn.get("uncertainty"), cn)

    return "not_comparable"


def _align(claim_numbers, source_numbers):
    """Жадное парное выравнивание: каждое claim-число — максимум с одним source-числом.

    Возвращает pairs = [(cn, sn, status)]; разноразмерные кандидаты помечаются
    not_comparable и в вердикт не влияют (записываются в per-pair диагностику).
    """
    used = set()
    pairs = []
    for cn in claim_numbers:
        best = None
        best_score = None
        for j, sn in enumerate(source_numbers):
            if j in used:
                continue
            if not _same_dim(_unit_of(cn), _unit_of(sn)):
                continue
            score = _align_score(cn, sn)
            if score is None:
                continue
            if best_score is None or score < best_score:
                best_score = score
                best = j
        if best is not None:
            used.add(best)
            pairs.append((cn, source_numbers[best], _pair_status(cn, source_numbers[best])))
        else:
            # нет подходящей по размерности пары — фиксируем один not_comparable
            for j, sn in enumerate(source_numbers):
                if j not in used:
                    pairs.append((cn, sn, "not_comparable"))
                    break
    return pairs


def _representative(n):
    """Значение для выравнивания: у single — value, у range — центр."""
    if "value" in n:
        return n["value"]
    return (n["low"] + n["high"]) / 2.0


def _align_score(cn, sn):
    """Сходство пары (меньше = лучше). Сравнимы только в одной размерности."""
    ck, sk = _kind(cn), _kind(sn)
    if ck == "percent" and sk == "percent":
        return abs(cn["value"] - sn["value"])
    if ck == "range" and sk == "range":
        return abs(cn["low"] - sn["low"]) + abs(cn["high"] - sn["high"])
    # single ↔ single или single ↔ range (одна размерность)
    cu, su = _unit_of(cn), _unit_of(sn)
    try:
        if cu and su and cu != su:
            v = units_convert(_representative(cn), _normalize_unit(cu), _normalize_unit(su))
        else:
            v = _representative(cn)
    except ValueError:
        return None
    if sk == "range":
        return abs(v - _representative(sn))
    if ck == "range":
        return abs(_representative(cn) - sn["value"])
    return abs(v - sn["value"])


def _source_status_from_pairs(pairs, qual_status):
    """Собирает source_status из пар выравнивания."""
    if not pairs:
        return "no_data"
    statuses = [s for (_, _, s) in pairs]
    real = [s for s in statuses if s not in ("not_comparable", "no_data")]
    if not real:
        return "not_comparable"
    if "mismatch" in real:
        return "mismatch"
    if qual_status == "qualifier_mismatch":
        return "qualifier_mismatch"
    if "partial_match" in real:
        return "partial_match"
    return "match"


def compare_claim_sources(claim_data, sources_data):
    """Главная функция: сравнивает claim с источниками."""
    claim_text = claim_data.get("claim_text", "")
    claim_numbers = claim_data.get("claim_numbers") or extract_numbers(claim_text)
    claim_qualifiers = extract_qualifier(claim_text)

    results = []
    overall_status = "no_data"
    best_status = "no_data"

    for source in sources_data:
        source_title = source.get("title", source.get("descriptor", source.get("id", "")))
        source_text = source.get("text") or get_source_text(source)
        source_numbers = source.get("numbers") or extract_numbers(source_text)
        source_qualifiers = source.get("qualifier") or extract_qualifier(source_text)

        qual_status = compare_qualifiers(claim_qualifiers, source_qualifiers)

        # парное выравнивание (вместо cross-product)
        pairs = _align(claim_numbers, source_numbers)
        comparisons = [{
            "claim_value": cn.get("raw", ""),
            "source_value": sn.get("raw", ""),
            "status": st,
        } for cn, sn, st in pairs]

        source_status = _source_status_from_pairs(pairs, qual_status)

        results.append({
            "source_title": source_title,
            "comparisons": comparisons,
            "qualifier_comparison": {"claim": claim_qualifiers, "source": source_qualifiers, "status": qual_status},
            "source_status": source_status
        })

        status_priority = {"match": 4, "partial_match": 3, "qualifier_mismatch": 2,
                           "mismatch": 1, "not_comparable": 1, "no_data": 0}
        if status_priority.get(source_status, 0) > status_priority.get(best_status, 0):
            best_status = source_status

    # Формулы: если в claim найдена формула с конфликтом константы — числовой mismatch
    formula_name = detect_formula(claim_text)
    formula_info = None
    if formula_name:
        formula_info = {
            "name": formula_name,
            "constant_check": check_constant(formula_name, claim_text),
        }
        if formula_info["constant_check"] == "formula_conflict":
            best_status = "mismatch"

    if not claim_numbers and best_status == "no_data":
        best_status = "no_numbers_in_claim"

    return {
        "claim_id": claim_data.get("claim_id"),
        "claim_text": claim_text,
        "claim_numbers": claim_numbers,
        "claim_qualifiers": claim_qualifiers,
        "formula": formula_info,
        "results": results,
        "status": best_status,
        "explanation": f"Best match across {len(sources_data)} sources: {best_status}"
    }


def _normalize_groups(verdicts):
    """Нормализует вход в группы {original_index, claim_id, claims:[text], _flat_verdict}.

    Поддерживаемые формы входа:
      - list из плоских вердиктов (exp1): {claim_id, claim_text, sources, ...}
      - dict с verdicts[]: группировка по original_index если есть, иначе каждая
        запись — отдельная группа (по claim_id)
      - dict с groups[]: группы вида {original_index, claims:[text]}
      - dict БЕЗ verdicts/groups (одиночный вердикт или бесструктурный) — обрабатывается
      - None / пустой список — вернёт []
    """
    items = []
    if isinstance(verdicts, dict):
        if isinstance(verdicts.get("verdicts"), list):
            items = verdicts["verdicts"]
        elif isinstance(verdicts.get("groups"), list):
            items = verdicts["groups"]
        elif "claim_text" in verdicts or "claim_id" in verdicts or "verdict" in verdicts:
            items = [verdicts]
        else:
            vals = [v for v in verdicts.values() if isinstance(v, list)]
            items = [x for sub in vals for x in sub if isinstance(x, dict)]
    elif isinstance(verdicts, list):
        items = verdicts
    else:
        return []

    grouped = {}
    order = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("original_index") is not None:
            key = item["original_index"]
        elif item.get("claim_id") is not None:
            key = item["claim_id"]
        else:
            key = f"anon_{len(order)}"
        if key not in grouped:
            grouped[key] = {
                "original_index": item.get("original_index"),
                "claim_id": item.get("claim_id"),
                "claims": [],
                "_flat_verdict": None,
            }
            order.append(key)
        grp = grouped[key]
        if grp["original_index"] is None:
            grp["original_index"] = item.get("original_index")
        if grp["claim_id"] is None:
            grp["claim_id"] = item.get("claim_id")
        if isinstance(item.get("claims"), list):
            grp["claims"] = list(item["claims"])
        elif item.get("claim_text") is not None:
            grp["claims"].append(item["claim_text"])
        if grp["_flat_verdict"] is None:
            grp["_flat_verdict"] = item

    return [grouped[k] for k in order]


def _extract_sources_index(sources_data):
    """Разбирает sources.json на (index_dict, index_list).

    index_dict: {group_id: {sources: []}} ИЛИ {group_id: []} —
        ключи original_index ИЛИ claim_id (обе формы приёмлемы).
    index_list: [{original_index|claim_id, sources: []}].
    Возвращает (dict, list); одна из форм обычно пустая.
    """
    if isinstance(sources_data, dict):
        inner = sources_data.get("sources", sources_data)
        if isinstance(inner, dict):
            return inner, []
        if isinstance(inner, list):
            return {}, inner
        return {}, []
    if isinstance(sources_data, list):
        return {}, sources_data
    return {}, []


def load_sources(sources_data):
    """Единый загрузчик sources.json — принимает ОБЕ контрактные формы."""
    index_dict, index_list = _extract_sources_index(sources_data)
    warnings = []

    if index_dict:
        dict_shaped = list_shaped = 0
        for key, value in index_dict.items():
            if isinstance(value, dict):
                dict_shaped += 1
            elif isinstance(value, list):
                list_shaped += 1
        if dict_shaped and list_shaped:
            warnings.append(
                f"смешанный формат sources.json: {dict_shaped} групп в форме "
                f"{{group_id: {{sources: []}}}}, {list_shaped} — в форме "
                f"{{claim_id: [list]}}; нормализовано в единый индекс"
            )

    return index_dict, index_list, warnings


def _lookup_sources(index_dict, index_list, gid, claim_id):
    """Ищет sources для группы по original_index ИЛИ claim_id (fallback)."""
    candidates = [gid, claim_id]
    if index_dict:
        for key in candidates:
            if key is None:
                continue
            for lookup in (str(key), key):
                src_group = index_dict.get(lookup)
                if isinstance(src_group, list):
                    return src_group
                if not isinstance(src_group, dict):
                    continue
                srcs = src_group.get("sources", [])
                if isinstance(srcs, list):
                    return srcs
                if srcs:
                    return [srcs]
    if index_list:
        for sg in index_list:
            if not isinstance(sg, dict):
                continue
            for key in candidates:
                if key is None:
                    continue
                if str(sg.get("original_index")) == str(key) or str(sg.get("claim_id")) == str(key):
                    srcs = sg.get("sources", [])
                    if isinstance(srcs, list):
                        return srcs
                    if srcs:
                        return [srcs]
    return []


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 numeric_comparator.py <verdicts.json> <sources.json> <output.json>", file=sys.stderr)
        sys.exit(1)
    claim_path, sources_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        with open(claim_path, encoding="utf-8") as f:
            verdicts_data = json.load(f)
        with open(sources_path, encoding="utf-8") as f:
            sources_data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"ОШИБКА: не удалось прочитать входной JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    groups = _normalize_groups(verdicts_data)
    index_dict, index_list, src_warnings = load_sources(sources_data)
    for w in src_warnings:
        print(f"⚠️ ВАЛИДАТОР sources: {w}", file=sys.stderr)

    group_results = []
    status_counts = {}
    n_claims = 0
    zero_sources = []

    for group in groups:
        gid = group.get("original_index")
        claim_id = group.get("claim_id")
        group_sources = _lookup_sources(index_dict, index_list, gid, claim_id)

        claim_results = []
        group_best = "no_data"
        for i, claim_text in enumerate(group.get("claims", [])):
            claim_data = {"claim_id": claim_id if claim_id is not None else f"{gid}.{i}",
                          "claim_text": claim_text}
            res = compare_claim_sources(claim_data, group_sources)
            claim_results.append(res)
            n_claims += 1
            priority = {"match": 4, "partial_match": 3, "qualifier_mismatch": 2,
                        "mismatch": 1, "not_comparable": 1, "no_data": 0}
            if priority.get(res["status"], 0) > priority.get(group_best, 0):
                group_best = res["status"]
            status_counts[res["status"]] = status_counts.get(res["status"], 0) + 1

        group_results.append({
            "original_index": group.get("original_index"),
            "claim_id": group.get("claim_id"),
            "n_claims_in_group": len(group.get("claims", [])),
            "n_sources": len(group_sources),
            "group_status": group_best,
            "claims": claim_results,
        })
        if not group_sources:
            zero_sources.append(group.get("claim_id") if group.get("claim_id") is not None
                                else group.get("original_index"))

    result = {
        "total_groups": len(group_results),
        "total_claims": n_claims,
        "status_counts": status_counts,
        "groups": group_results,
    }
    if zero_sources:
        print(
            f"⚠️ ВАЛИДАТОР: {len(zero_sources)} групп получили n_sources=0 — "
            f"lookup не нашёл источники по original_index/claim_id; "
            f"проверьте форматы sources.json "
            f"(ожидается {{group_id: {{sources: []}}}} или {{claim_id: [list]}}). "
            f"Группы: {zero_sources}",
            file=sys.stderr,
        )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(result, open(output_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ Numeric comparison: {status_counts}")
    for g in group_results:
        if g["group_status"] in ("mismatch", "qualifier_mismatch", "not_comparable"):
            print(f"  group {g['original_index']}: {g['group_status']} ({g['n_claims_in_group']} claims, {g['n_sources']} sources)")


if __name__ == "__main__":
    main()
