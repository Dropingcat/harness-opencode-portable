#!/usr/bin/env python3
"""claim_classifier.py — классификатор claim-типов (инкапсулированный модуль).

Классы (детерминированно, на маркерах):
  - gap      — заявленный пробел («остаётся нерешённой», «отсутствуют»,
               «не изучено», «не решено», «нет данных», «требует дальнейших»…);
  - attribute — приписывание/авторство (в работах, установлено, показано,
               доказано, заложены, наблюдается, экспериментально…);
  - numeric  — числовое утверждение (цифры/единицы измерений);
  - framing  — рамка/общеизвестный факт (фундаментальная задача, важно,
               актуально, играет роль…).

Порядок приоритета: gap > numeric > attribute > framing.
Для gap-claims верификация идёт по отдельным правилам (gap_rules.py): отсутствие
поддерживающих источников — НЕ «опровергнуто», а «заявлено отсутствие данных».

Модуль самодостаточен и тестируется отдельно (test_claim_classifier.py).

CLI:
  python3 claim_classifier.py "<claim_text>"
"""
import argparse
import re
import sys

GAP_MARKERS = [
    "остаётся нерешённ", "остается нерешенн", "нерешённой задачей",
    "нерешенной задачей", "нерешённой", "нерешенной", "нерешена", "нерешён",
    "не решена", "не решён", "не решено",
    "данные отсутствуют", "такие данные отсутствуют",
    "отсутствуют", "отсутствует", "отсутствие",
    "не изучен", "не изучено", "не изучена", "не изучены",
    "неизвестн", "нет данных", "нет сведений",
    "пробел", "не хватает", "недостаточно изучен", "недостаточно данных",
    "недостаточно изучено", "недостаточно исследован",
    "требует дальнейших", "требует дальнейшего", "нуждается в изучении",
    "не позволяет", "не позволяют", "открытым остаётся", "открытым остается",
    "не установлено", "не установлена", "не установлен",
    "не определено", "не определена", "не определены",
    "малоизучен", "слабо изучен", "не объяснено", "не объяснена",
    "не подтверждено", "не подтверждена",
]

ATTRIBUTE_MARKERS = [
    "в работах", "в работе", "работы", "работах",
    "установлено", "установили", "было установлено", "показано", "показали",
    "доказано", "доказал", "доказали", "доказана",
    "заложены", "заложено", "наблюдается", "наблюдаемое",
    "отмечено", "экспериментально", "по данным", "по результатам",
    "указывает", "свидетельств", "выделить научную школу", "научную школу",
    "исследована", "исследованы", "исследовано", "разработан", "разработано",
    "предложен", "предложено", "описано", "описан",
    "авторы", "исследования", "соавторами", "с соавторами",
    "экспериментальная", "экспериментальный", "впервые",
]

NUMERIC_RE = re.compile(r"(?<![\w])\d[\d.,%\s]*(?:°?[CКК]|мм|мкм|нм|HV|ГПа|МПа|кДж|см|атм|час|ч|ч\.|%)|"
                        r"\d+[.,]\d+", re.IGNORECASE)

FRAMING_MARKERS = [
    "фундаментальная задача", "является важн", "актуальн", "актуальная задача",
    "общеизвестн", "представляет собой", "играет важную", "играет ключевую",
    "одна из задач", "определяет актуальность", "важность", "значимость",
    "необходимость", "целью", "задачей исследования",
]

# Слишком широкие маркеры, дающие ложные срабатывания на framing-claim (C0).
_GAP_EXCLUDE = {
    "задач", "задача", "задачи", "задач физики", "фундаментальная задача",
}


def classify(text):
    """Классифицирует claim.

    Возвращает {"claim_class": ..., "markers_found": [...], "has_numbers": bool}.
    """
    low = (text or "").lower()
    low_norm = re.sub(r"[^a-zа-яё0-9\s-]", " ", low)
    markers_found = []

    # 1. gap (составные/уточнённые маркеры; исключения не считаются)
    for m in GAP_MARKERS:
        if m in low_norm or m in low:
            if m in _GAP_EXCLUDE:
                continue
            markers_found.append(("gap", m))
            break
    if any(tag == "gap" for tag, _ in markers_found):
        return {
            "claim_class": "gap",
            "markers_found": [m for _, m in markers_found],
            "has_numbers": bool(NUMERIC_RE.search(text or "")),
        }

    # 2. numeric
    has_numbers = bool(NUMERIC_RE.search(text or ""))
    if has_numbers:
        return {
            "claim_class": "numeric",
            "markers_found": ["digits/units present"],
            "has_numbers": True,
        }

    # 3. attribute
    for m in ATTRIBUTE_MARKERS:
        if m in low:
            markers_found.append(("attribute", m))
    if any(tag == "attribute" for tag, _ in markers_found):
        return {
            "claim_class": "attribute",
            "markers_found": [m for _, m in markers_found],
            "has_numbers": False,
        }

    # 4. framing
    for m in FRAMING_MARKERS:
        if m in low:
            markers_found.append(("framing", m))
            break
    if markers_found:
        return {
            "claim_class": "framing",
            "markers_found": [m for _, m in markers_found],
            "has_numbers": False,
        }

    return {
        "claim_class": "framing",
        "markers_found": ["no markers — default framing"],
        "has_numbers": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("claim_text")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()
    res = classify(args.claim_text)
    if args.as_json:
        print(__import__("json").dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"claim_class: {res['claim_class']}")
        print(f"markers_found: {res['markers_found']}")
        print(f"has_numbers: {res['has_numbers']}")


if __name__ == "__main__":
    main()