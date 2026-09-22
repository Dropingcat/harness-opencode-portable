#!/usr/bin/env python3
"""test_numeric_layer_fix.py — реальные тесты числового слоя (H1-H4 + cross-product +
запятая + индексы Миллера/марки) на фрагментах автореферата.

НЕ мок, НЕ поверхностные: каждый тест падает, если дефект не исправлен.
Источник: /home/orangepi/Документы/doc_AI_ReWriter/_work/pilot_test/автореферат_5_2в.txt
(Новизна/Положения/Актуальность + Достоверность/Глава 3).
"""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from numeric_comparator import (  # noqa: E402
    compare_claim_sources,
    extract_numbers,
    _pair_status,
)
from units import convert, dimension, normalize_unit  # noqa: E402


def _find(ns, typ, unit=""):
    """Ищет число заданного типа (и, если задано, единицы)."""
    for n in ns:
        if n["type"] == typ and (not unit or n.get("unit") == unit):
            return n
    return None


# ─────────────────────────── H1: реестр единиц ───────────────────────────

def test_h1_units():
    """Вт/Å/кПа/кгс/мм/мин/рад/°C распознаются."""
    cases = {
        "2000 Вт": ("single", "Вт", 2000.0),
        "2000 W": ("single", "W", 2000.0),
        "1,5418 Å": ("single", "Å", 1.5418),
        "10 кПа": ("single", "кПа", 10.0),
        "0,0044 рад": ("single", "рад", 0.0044),
        "540 °C": ("single", "°C", 540.0),
        "10 мм": ("single", "мм", 10.0),
    }
    for text, (typ, unit, val) in cases.items():
        ns = extract_numbers(text)
        n = _find(ns, typ, unit)
        assert n is not None, f"{text!r}: не найдено {typ}/{unit}, получили {ns}"
        assert n["value"] == pytest.approx(val), f"{text!r}: {n}"


def test_h1_units_on_ranges():
    """Единицы НЕ теряются на диапазонах: 2–6 мкм, 8–24 ч, 1200–2000 Вт."""
    r = _find(extract_numbers("2–6 мкм"), "range")
    assert r is not None and r["unit"] == "мкм" and (r["low"], r["high"]) == (2.0, 6.0)
    r = _find(extract_numbers("8–24 ч"), "range")
    assert r is not None and r["unit"] == "ч" and (r["low"], r["high"]) == (8.0, 24.0)
    r = _find(extract_numbers("1200–2000 Вт"), "range")
    assert r is not None and r["unit"] == "Вт" and (r["low"], r["high"]) == (1200.0, 2000.0)
    # нет дублей концов диапазона (6 мкм / 24 ч / 2000 Вт не эмитятся отдельно)
    ns = extract_numbers("2–6 мкм и 6–18 мкм")
    assert len([n for n in ns if n["type"] == "range"]) == 2
    assert not any(n["type"] == "single" for n in ns), f"дубль конца диапазона: {ns}"


def test_h1_units_conversion():
    """Новые единицы участвуют в конвертации (Слой 0)."""
    assert convert(10, "мм", "см") == pytest.approx(1.0)
    assert convert(1, "Å", "нм") == pytest.approx(0.1)
    assert convert(2, "мкм", "нм") == pytest.approx(2000.0)
    assert convert(120, "мин", "час") == pytest.approx(2.0)
    assert convert(540, "°C", "K") == pytest.approx(813.15)
    # размерности: длина ≠ время ≠ температура
    assert dimension("мкм") != dimension("ч")
    assert dimension("Вт") != dimension("°C")


# ─────────────────────────── H2: хим. формулы ───────────────────────────

def test_h2_formula():
    """Fe2-3N → FORMULA (не range/ньютон); Fe-N-Cr-W-Mo не даёт чисел."""
    ns = extract_numbers("Fe2-3N")
    assert ns == [], f"Fe2-3N должен быть формулой (0 чисел), получили {ns}"
    ns = extract_numbers("ε-Fe₂₋₃N и γ'-Fe₄N")
    assert ns == [], f"юникод-подстрочники — не числа, получили {ns}"
    ns = extract_numbers("Fe-N-Cr-W-Mo")
    assert ns == [], f"Fe-N-Cr-W-Mo — не числа, получили {ns}"
    # не ломаем реальные числа рядом с формулами
    ns = extract_numbers("Fe₄N — до 55 %, Fe₃N — до 20 %, Cr₂N — до 11 %")
    percents = [n for n in ns if n["type"] == "percent"]
    assert [n["value"] for n in percents] == pytest.approx([55.0, 20.0, 11.0]), ns


# ─────────────────────────── H3: запятая-десятичный ───────────────────────────

def test_h3_comma():
    """1,5 % → 1.5; 3,585–3,591 Å → range{3.585,3.591}; 44,5 нм → 44.5."""
    n = _find(extract_numbers("1,5 %"), "percent")
    assert n is not None and n["value"] == pytest.approx(1.5), extract_numbers("1,5 %")
    r = _find(extract_numbers("3,585–3,591 Å"), "range")
    assert r is not None and (r["low"], r["high"]) == pytest.approx((3.585, 3.591)), \
        extract_numbers("3,585–3,591 Å")
    n = _find(extract_numbers("44,5 нм"), "single", "нм")
    assert n is not None and n["value"] == pytest.approx(44.5), extract_numbers("44,5 нм")
    # 0,05°; 0,9%/0,6%; 1,5418 Å; 2–2,5 раза
    n = _find(extract_numbers("0,05°"), "single", "°")
    assert n is not None and n["value"] == pytest.approx(0.05)
    ps = [x["value"] for x in extract_numbers("0,9% … 0,6%") if x["type"] == "percent"]
    assert ps == pytest.approx([0.9, 0.6]), extract_numbers("0,9% … 0,6%")
    r = _find(extract_numbers("2–2,5 раза"), "range")
    assert r is not None and r["high"] == pytest.approx(2.5), extract_numbers("2–2,5 раза")
    # Глава 3: переходные диапазоны (→) и научная нотация с м⁻²
    r = _find(extract_numbers("2,880 → 2,874 Å"), "range", "Å")
    assert r is not None and r["low"] == pytest.approx(2.880) and r["high"] == pytest.approx(2.874), \
        extract_numbers("2,880 → 2,874 Å")
    sci = _find(extract_numbers("ρ ≈ 6·10²⁰ м⁻²"), "scientific")
    assert sci is not None and sci["unit"] == "м⁻²" and sci["value"] == pytest.approx(6e20), \
        extract_numbers("ρ ≈ 6·10²⁰ м⁻²")


# ─────────────────────────── cross-product: парное выравнивание ───────────────────────────

def test_pairwise_alignment():
    """[55%,2%] vs [55%,2%] → match (не ложный mismatch)."""
    claim = {"claim_id": 1,
             "claim_text": "объёмная доля нитридов в сплаве ВКС‑10 до 55 %, менее 2 %"}
    source = {"title": "src",
              "text": "объёмная доля нитридов в сплаве ВКС-10 до 55 %, менее 2 %"}
    res = compare_claim_sources(claim, [source])
    assert res["status"] == "match", \
        f"[55%,2%] vs [55%,2%] должен быть match, получили {res['status']}: " \
        f"{[c['status'] for c in res['results'][0]['comparisons']]}"
    # ровно 2 пары (парное выравнивание, не 4 из cross-product)
    assert len(res["results"][0]["comparisons"]) == 2


# ─────────────────────────── индексы Миллера / марки ───────────────────────────

def test_miller_grade():
    """(220)/(311)/(222) → MILLER (не числа); ВКС-10 → GRADE; β(110)=0.2770° → 0.2770."""
    assert extract_numbers("(220), (311), (222)") == [], extract_numbers("(220), (311), (222)")
    assert extract_numbers("ВКС-10") == [], extract_numbers("ВКС-10")
    assert extract_numbers("ВКС‑10") == [], "неразрывный дефис U+2011"
    assert extract_numbers("ВКС10") == [], extract_numbers("ВКС10")
    assert extract_numbers("08Х18Н10Т") == [], extract_numbers("08Х18Н10Т")
    # β(110) = 0.2770° — значение извлекается, рефлекс (110) — нет
    ns = extract_numbers("β(110) = 0.2770°")
    vals = [n["value"] for n in ns]
    assert vals == pytest.approx([0.2770]), f"β(110)=0.2770°: {ns}"
    assert 110.0 not in vals
    # стандарты (ISO 6507) — шум, не числа; кириллическая единица Н на диапазоне
    assert extract_numbers("ISO 6507") == []
    r = _find(extract_numbers("нагрузка 0.1-0.5 Н"), "range", "Н")
    assert r is not None and (r["low"], r["high"]) == pytest.approx((0.1, 0.5))


# ─────────────────────────── not_comparable ───────────────────────────

def test_not_comparable():
    """Разноразмерные пары → not_comparable (не dimension-вердикт)."""
    res = compare_claim_sources(
        {"claim_id": 1, "claim_text": "температура 540 °C"},
        [{"title": "s", "text": "выдержка 8–24 ч"}])
    assert res["status"] == "not_comparable", \
        f"540°C vs 8-24ч должен быть not_comparable, получили {res['status']}"
    # 77 мм vs 77 °C
    res2 = compare_claim_sources(
        {"claim_id": 2, "claim_text": "размер 77 мм"},
        [{"title": "s", "text": "температура 77 °C"}])
    assert res2["status"] == "not_comparable", res2["status"]


# ─────────────────────────── реальный прогон «Новизна» ───────────────────────────

def test_real_actuality_numeric():
    """Реальные куски «Новизна 2/3»: 2000 Вт, 55%, 540°C, 8–24 ч, 2–6 мкм — вердикты."""
    # Новизна 2: совпадающий источник
    claim_n2 = ("предварительная лазерная обработка с оплавлением поверхности (2000 Вт) "
                "увеличивает объёмную долю нитридов в сплаве ВКС‑10 до 55 % "
                "(против менее 2 % при классическом азотировании)")
    src_n2 = ("лазерная обработка с оплавлением поверхности (2000 Вт) увеличивает "
              "объёмную долю нитридов в сплаве ВКС-10 до 55 % против менее 2 %")
    r = compare_claim_sources({"claim_id": 1, "claim_text": claim_n2}, [{"title": "s", "text": src_n2}])
    assert r["status"] == "match", r["status"]

    # Новизна 3: 540 °C, 8–24 ч, 2–6 мкм, 6–18 мкм
    claim_n3 = ("вакуумном азотировании (540 °C, 8–24 ч)… излучения Cu- с глубиной 2–6 мкм "
                "и Co- с глубиной 6–18 мкм")
    src_n3 = ("вакуумное азотирование (540 °C, 8–24 ч), глубины проникновения 2–6 мкм "
              "и 6–18 мкм")
    r3 = compare_claim_sources({"claim_id": 3, "claim_text": claim_n3}, [{"title": "s", "text": src_n3}])
    assert r3["status"] == "match", r3["status"]
    # обе пары диапазонов спарены и несут единицы
    for c in r3["results"][0]["comparisons"]:
        assert c["status"] != "not_comparable", c

    # Положения 2: 55 %
    claim_p = "увеличивает объёмную долю нитридов в сплаве ВКС‑10 до 55 %"
    src_p = "объёмная доля нитридов в сплаве ВКС-10 до 55 %"
    rp = compare_claim_sources({"claim_id": 1, "claim_text": claim_p}, [{"title": "s", "text": src_p}])
    assert rp["status"] == "match", rp["status"]


# ─────────────────────────── регрессия exp1 ───────────────────────────

def test_regression_exp1():
    """exp1: совпадающие числовые claim-источники не дают ложных mismatch.

    Отсутствие регрессии: Fe2-3N в claim 7 не ломает вердикт (FORMULA), а
    claim 10 (0.3-0.6 мм) остаётся частичным по диапазону.
    """
    # claim 7 (ε-фаза Fe2-3N) — не ложный mismatch (был из-за парсинга 2-3 + N-ньютон)
    r7 = compare_claim_sources(
        {"claim_id": 7,
         "claim_text": "Образование ε-фазы (Fe2-3N) происходит на поверхности "
                       "[металла] при высоких концентрациях азота."},
        [{"title": "s", "text": "ε-фаза — твердый раствор на базе нитрида Fe2-3N, 8-11.2%N"}])
    assert r7["status"] != "mismatch", \
        f"Fe2-3N не должен давать ложный mismatch: {r7['status']}"

    # claim 10 (0.3-0.6 мм) — диапазон с единицей мм, partial/match по источнику
    r10 = compare_claim_sources(
        {"claim_id": 10,
         "claim_text": "Глубина азотированного слоя составляет 0.3-0.6 мм "
                       "при стандартном режиме азотирования"},
        [{"title": "s", "text": "Typical gas nitriding case depths range from 0.1 mm to 0.6 mm"}])
    assert r10["status"] in ("match", "partial_match", "qualifier_mismatch"), r10["status"]
    # диапазон распознан с единицей
    rng = _find(r10["claim_numbers"], "range", "мм")
    assert rng is not None and rng["low"] == pytest.approx(0.3) and rng["high"] == pytest.approx(0.6)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
