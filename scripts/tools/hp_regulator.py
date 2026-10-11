#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hp_regulator.py — HP-регуляция шага цикла и глубины аудита (M9).

Канон гл.29: триггер на НАРУШЕНИИ ОЖИДАНИЯ, а не на пороге. Система
не реагирует на абсолютный уровень урона сам по себе — она реагирует
на то, что реальный темп накопления урона разошёлся с ожидаемым
(expected_rate). Чем ниже HP, тем чаще цикл аудита и тем глубже движки.

Запрос пользователя: «чтобы можно было варьируя хп регулировать шаг цикла
и его глубину» — здесь HP (health_points из SystemHealth, 0..100) напрямую
управляет: (1) шагом цикла audit'а и (2) глубиной проверки.

Usage:
    python hp_regulator.py step --hp 75
    python hp_regulator.py depth --hp 35
    python hp_regulator.py violation --history 5,5,15,30 --expected-rate 5
    python hp_regulator.py recover --hp 30 --sleep-success true

API:
    cycle_step(hp) -> int
    audit_depth(hp) -> str
    expectation_violation(damage_history, expected_rate, window=3) -> bool
    recover_hp(hp, sleep_success) -> float

Зависимости: нет (pure functions). Интеграция с SystemHealth — через передачу
health_points как hp. Файлы health_monitor.py / damage_basket.py не меняются.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Union

# Пороги уровня здоровья (совпадают по духу с SystemHealth._recompute_level,
# но пороги шага/глубины — спецификация M9, НЕ health_monitor).
HP_MIN = 0.0
HP_MAX = 100.0

# Шаг цикла аудита: сколько циклов пропускать между проверками.
# hp < 20 — критический режим: каждый ход (шаг 1).
_STEP_BANDS = (
    (80.0, 10),   # hp >= 80  -> редкий аудит, экономия
    (60.0, 5),    # 60..79    -> обычный
    (40.0, 2),    # 40..59    -> учащённый
    (20.0, 1),    # 20..39    -> частый
    (0.0, 1),     # <20       -> критический: каждый ход
)

# Глубина аудита: набор движков.
# ВАЖНО: по acceptance audit_depth(35)=="deep", поэтому hardcore
# зарезервирован за критической зоной (<20, совпадает с critical-режимом
# cycle_step). Отклонение от черновика "<40 -> hardcore" задокументировано
# в notes JSON (acceptance приоритетнее).
_DEPTH_BANDS = (
    (80.0, "light"),     # hp >= 80 -> только text_heuristics
    (60.0, "normal"),    # 60..79   -> text + relation
    (40.0, "deep"),      # 40..59   -> text + relation + epistemic
    (20.0, "deep"),      # 20..39   -> deep (по acceptance 35 -> deep)
    (0.0, "hardcore"),   # <20      -> все движки + мета-проверки
)

_CRITICAL_HP = 20.0  # ниже этой границы — режим «критический»


def _clamp_hp(hp: float) -> float:
    """Привести HP к диапазону 0..100 (защита от вырожденного входа)."""
    return max(HP_MIN, min(HP_MAX, float(hp)))


def cycle_step(hp: float) -> int:
    """Шаг цикла аудита по HP.

    Чем ниже HP, тем чаще проверяем (шаг меньше). hp < 20 — критический
    режим: шаг 1 (каждый ход). Возвращает int >= 1.
    """
    hp = _clamp_hp(hp)
    for threshold, step in _STEP_BANDS:
        if hp >= threshold:
            return step
    return 1  # недостижимо после clamp, но безопасно


def is_critical(hp: float) -> bool:
    """Режим «критический» (hp < 20): каждый ход, все движки."""
    return _clamp_hp(hp) < _CRITICAL_HP


def audit_depth(hp: float) -> str:
    """Глубина аудита по HP: light / normal / deep / hardcore.

    light — только text_heuristics; normal — text + relation;
    deep — + epistemic; hardcore (<20) — все движки + мета-проверки.
    """
    hp = _clamp_hp(hp)
    for threshold, depth in _DEPTH_BANDS:
        if hp >= threshold:
            return depth
    return "hardcore"  # недостижимо после clamp, но безопасно


def expectation_violation(damage_history: List[float], expected_rate: float,
                          window: int = 3) -> bool:
    """Триггер на нарушении ожидания (канон гл.29), НЕ на пороге.

    damage_history — последовательность урона по циклам (свежее — правее).
    expected_rate — нормальная скорость накопления урона за цикл.

    Правило: средний урон за последние ``window`` циклов больше 2×
    expected_rate → нарушение ожидания (урон растёт быстрее ожидаемого).

    >>> expectation_violation([5, 5, 15, 30], 5)   # 16.67 > 10 -> True
    True
    >>> expectation_violation([5, 5, 5, 5], 5)      # 5 > 10 -> False
    False
    """
    if not damage_history:
        return False
    if expected_rate <= 0:
        # Неположительный ожидаемый темп: любой урон уже нарушение.
        return sum(damage_history) > 0
    recent = damage_history[-window:]
    actual_rate = sum(recent) / len(recent)
    return actual_rate > 2.0 * expected_rate


def recover_hp(hp: float, sleep_success: bool) -> float:
    """HP-восстановление после цикла сна.

    Успешный сон (merge ok) -> hp += 15 (max 100).
    Провальный -> hp -= 20 (min 0). Всегда возвращает float.
    """
    hp = _clamp_hp(hp)
    if sleep_success:
        return min(HP_MAX, hp + 15.0)
    return max(HP_MIN, hp - 20.0)


# ---------------------------------------------------------------------- CLI

def _parse_history(raw: str) -> List[float]:
    """'5,5,15,30' -> [5.0, 5.0, 15.0, 30.0]."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("--history пустой: ожидалось '5,5,15,30'")
    return [float(p) for p in parts]


def _bool_arg(raw: str) -> bool:
    """'true'/'false' (регистронезависимо) -> bool."""
    lowered = raw.strip().lower()
    if lowered in ("true", "1", "yes", "y"):
        return True
    if lowered in ("false", "0", "no", "n"):
        return False
    raise ValueError(f"ожидалось true/false, получено: {raw!r}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="hp_regulator.py",
        description="HP-регуляция шага цикла и глубины аудита (M9).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_step = sub.add_parser("step", help="шаг цикла по HP")
    p_step.add_argument("--hp", type=float, required=True)

    p_depth = sub.add_parser("depth", help="глубина аудита по HP")
    p_depth.add_argument("--hp", type=float, required=True)

    p_viol = sub.add_parser("violation", help="триггер нарушения ожидания")
    p_viol.add_argument("--history", required=True,
                        help="урон по циклам через запятую, напр. 5,5,15,30")
    p_viol.add_argument("--expected-rate", type=float, required=True,
                        dest="expected_rate", help="нормальная скорость урона")
    p_viol.add_argument("--window", type=int, default=3,
                        help="сколько последних циклов учитывать (default 3)")

    p_rec = sub.add_parser("recover", help="HP после цикла сна")
    p_rec.add_argument("--hp", type=float, required=True)
    p_rec.add_argument("--sleep-success", required=True, dest="sleep_success",
                       help="true/false (merge ok / провал)")

    args = parser.parse_args(argv)

    try:
        if args.command == "step":
            result = {"hp": _clamp_hp(args.hp),
                      "step": cycle_step(args.hp),
                      "critical": is_critical(args.hp)}
        elif args.command == "depth":
            result = {"hp": _clamp_hp(args.hp),
                      "depth": audit_depth(args.hp),
                      "critical": is_critical(args.hp)}
        elif args.command == "violation":
            history = _parse_history(args.history)
            result = {"history": history,
                      "expected_rate": args.expected_rate,
                      "window": args.window,
                      "violation": expectation_violation(
                          history, args.expected_rate, window=args.window)}
        elif args.command == "recover":
            ok = _bool_arg(args.sleep_success)
            result = {"hp": _clamp_hp(args.hp),
                      "sleep_success": ok,
                      "hp_after": recover_hp(args.hp, ok)}
        else:  # pragma: no cover — argparse не даст сюда попасть
            raise RuntimeError(f"неизвестная команда: {args.command}")
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    # Windows stdout cp1251 -> utf-8 (JSON с русскими строками ломается иначе).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())