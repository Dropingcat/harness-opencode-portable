#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""monte_carlo_sleep.py — Monte-Carlo прогоны цикла сна (M8).

Канон:
  гл.20 — ошибки/техдолги копятся НЕЛИНЕЙНО (каскадный остаток после merge);
  гл.23 — эвалы = доля успешных из N; разброс (std) считается ПО СРЕЗАМ
          (по threshold и по merge_mode).

Цель (запрос пользователя): прогнать цикл сна много раз на сетке сценариев,
варьируя HP-порог (threshold) и глубину цикла (число артефактов -> веток),
чтобы сделать цикл отказоустойчивым и предсказуемым на любых настройках.

Модель прогона (детерминированная, seed-управляемая):
  - total_damage = artifacts_count * damage_per_artifact
  - triggered_sleep = total_damage >= threshold  (HP-бюджет исчерпан -> сон)
  - если сон: SleepPlannerAgent.run_plan -> ветки fix/<rule> (по артефактам)
  - имитация merge (реальный git НЕ вызывается — это scope out):
      all_ok   -> все ветки слиты ok
      conflict -> ровно 1 ветка конфликтна (abort, остальные слиты)
      failed   -> ровно 1 ветка потеряна (не слита, не удалена)
  - остаток урона remaining (гл.20: нелинейно):
      ok-ветка ремонтирует свою долю урона;
      conflict — её доля остаётся (урон не исчез);
      failed   — её доля остаётся + 25% каскада от отремонтированной части;
  - hp_after = max(0, threshold - remaining)
  - exit_ok  = hp_after > 0  (цикл пережил прогон без исчерпания HP)

API:
  scenarios() -> list[Scenario]
  run_scenario(scenario, rng=None) -> dict
  aggregate(results) -> dict
  add_damage(basket, rule_id, damage_points) -> int  (обёртка drop/add_damage)

CLI:
  python monte_carlo_sleep.py run [--limit 81] [--seed 42] [--json out.json] [--table]
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import statistics
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
_META_DIR = Path(__file__).resolve().parents[1] / "meta"

# --------------------------------------------------------------------------
# Мета-слой (damage_basket, sleep_planner) живёт на других ветках.
# Пытаемся импортировать реальные классы; если их нет в текущем checkout —
# используем встроенный fallback с тем же интерфейсом (модуль должен
# работать "на любых настройках", по запросу пользователя).
# --------------------------------------------------------------------------
try:
    sys.path.insert(0, str(_META_DIR))
    from damage_basket import DamageBasket, DamageEntry          # noqa: F401
    from sleep_planner import SleepPlannerAgent                  # noqa: F401
    _REAL_META = True
except Exception as _imp_exc:  # noqa: BLE001 — fallback при отсутствии meta-слоя
    _REAL_META = False

    class DamageEntry:  # type: ignore[no-redef]
        """Fallback-запись урона (зеркалит реальный DamageEntry)."""

        __slots__ = ("entry_id", "rule_id", "engine", "severity", "message",
                     "target", "damage_points", "timestamp", "auditor_id")

        def __init__(self, rule_id: str, engine: str = "monte_carlo",
                     severity: str = "WARNING", message: str = "",
                     target: str = "", auditor_id: str = "external") -> None:
            self.entry_id = f"fb_{rule_id}"
            self.rule_id = rule_id
            self.engine = engine
            self.severity = severity
            self.message = message
            self.target = target
            self.damage_points = {"CRITICAL": 25, "WARNING": 5, "LOW": 1}.get(severity, 1)
            self.timestamp = "1970-01-01T00:00:00"
            self.auditor_id = auditor_id

        def to_dict(self) -> Dict[str, Any]:
            return {k: getattr(self, k) for k in self.__slots__}

    class DamageBasket:  # type: ignore[no-redef]
        """Fallback-корзина урона (файловый, изолированный per-scenario)."""

        def __init__(self, basket_dir: Optional[str] = None,
                     threshold: int = 100) -> None:
            self.dir = Path(basket_dir) if basket_dir else Path(tempfile.gettempdir()) / "fb_basket"
            self.dir.mkdir(parents=True, exist_ok=True)
            self.file = self.dir / "basket.json"
            self.threshold = threshold
            self.entries: List[DamageEntry] = []

        def add_damage(self, rule_id: str, damage_points: int) -> int:
            e = DamageEntry(rule_id=rule_id)
            e.damage_points = int(damage_points)
            self.entries.append(e)
            return self.total_damage()

        def drop(self, entry: DamageEntry) -> int:
            self.entries.append(entry)
            return self.total_damage()

        def drop_many(self, entries: List[DamageEntry]) -> int:
            self.entries.extend(entries)
            return self.total_damage()

        def total_damage(self) -> int:
            return sum(e.damage_points for e in self.entries)

        def should_trigger_sleep(self) -> bool:
            return self.total_damage() >= self.threshold

        def reset(self) -> None:
            self.entries = []

    class SleepPlan:  # type: ignore[no-redef]
        def __init__(self, branches: List[str]) -> None:
            self.branches = branches

    class SleepPlannerAgent:  # type: ignore[no-redef]
        """Fallback-планировщик: ветка на каждый rule_id из корзины."""

        def __init__(self, basket: DamageBasket, cluster_fn: Any = None,
                     state_dir: Optional[str] = None) -> None:
            self.basket = basket
            self.history: List[SleepPlan] = []

        def run_plan(self, orchestrator: str) -> Optional[SleepPlan]:
            if not self.basket.should_trigger_sleep():
                return None
            clusters: Dict[str, List[DamageEntry]] = {}
            for e in self.basket.entries:
                clusters.setdefault(e.rule_id, []).append(e)
            plan = SleepPlan([f"fix/{rid}" for rid in clusters])
            self.history.append(plan)
            return plan


# --------------------------------------------------------------------------
# Сценарии
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    """Вариация параметров цикла сна для одного Monte-Carlo прогона."""

    threshold: int            # HP-порог корзины урона (шаг/глубина цикла)
    damage_per_artifact: int  # урон одного артефакта
    artifacts_count: int      # глубина цикла (число артефактов -> веток)
    sleep_merge_mode: str     # all_ok | conflict | failed

    @property
    def scenario_id(self) -> str:
        return (f"t{self.threshold}_d{self.damage_per_artifact}"
                f"_a{self.artifacts_count}_{self.sleep_merge_mode}")


def scenarios() -> List[Scenario]:
    """Сетка 3x3x3x3 = 81 сценарий (cartesian, детерминированный порядок)."""
    thresholds = [30, 50, 100]
    damages = [5, 25, 50]
    counts = [1, 3, 10]
    modes = ["all_ok", "conflict", "failed"]
    return [Scenario(t, d, a, m)
            for t, d, a, m in itertools.product(thresholds, damages, counts, modes)]


# --------------------------------------------------------------------------
# Прогон одного сценария
# --------------------------------------------------------------------------
def add_damage(basket: Any, rule_id: str, damage_points: int) -> int:
    """Положить артефакт с фиксированным уроном в корзину.

    Работает и с реальным DamageBasket (нет add_damage — используем
    drop + DamageEntry с переопределённым damage_points), и с fallback
    (у которого add_damage есть).
    """
    if hasattr(basket, "add_damage"):
        return basket.add_damage(rule_id, int(damage_points))
    entry = DamageEntry(rule_id=rule_id, engine="monte_carlo", severity="WARNING",
                        message=f"mc-artifact {rule_id}")
    entry.damage_points = int(damage_points)  # точный урон поверх severity-карты
    return basket.drop(entry)


def _simulate_merge(scenario: Scenario, branches: List[str],
                    total_damage: int, rng: random.Random) -> Dict[str, Any]:
    """Имитация merge без реального git (scope out).

    Возвращает {merged, remaining}: merged — число слитых ok-веток;
    remaining — остаточный урон после сна (нелинейный, гл.20).
    """
    n = len(branches)
    if n == 0:
        # сон не триггерился: урон ниже HP-порога, чинить нечего
        return {"merged": 0, "remaining": 0.0}
    statuses = ["ok"] * n
    if scenario.sleep_merge_mode != "all_ok":
        idx = rng.randrange(n) if rng is not None else 0
        statuses[idx] = scenario.sleep_merge_mode  # conflict | failed
    merged = sum(s == "ok" for s in statuses)
    share = total_damage / n
    remaining = total_damage * (n - merged) / n  # доли неслитых веток остаются
    if scenario.sleep_merge_mode == "failed":
        # гл.20: ошибки копятся нелинейно — 25% каскада от отремонтированной части
        remaining += 0.25 * total_damage * merged / n
    return {"merged": merged, "remaining": remaining}


def run_scenario(scenario: Scenario,
                 rng: Optional[random.Random] = None) -> Dict[str, Any]:
    """Прогон одного сценария цикла сна в изолированном tempdir.

    Возвращает {scenario_id, threshold, damage_per_artifact, artifacts_count,
    sleep_merge_mode, triggered_sleep, branches, merged, hp_after, exit_ok}.
    """
    with tempfile.TemporaryDirectory(prefix="mc_sleep_") as tmp:
        basket = DamageBasket(basket_dir=tmp, threshold=scenario.threshold)
        for i in range(scenario.artifacts_count):
            add_damage(basket, f"mc_rule_{i}", scenario.damage_per_artifact)
        total_damage = basket.total_damage()
        triggered = basket.should_trigger_sleep()

        branches: List[str] = []
        if triggered:
            planner = SleepPlannerAgent(basket=basket, state_dir=tmp)
            plan = planner.run_plan("monte-carlo")
            branches = list(plan.branches) if plan else []

        merge = _simulate_merge(scenario, branches, total_damage, rng)
        remaining = merge["remaining"]
        hp_after = max(0, scenario.threshold - remaining)
        exit_ok = hp_after > 0  # цикл пережил прогон (HP не исчерпан)

    return {
        "scenario_id": scenario.scenario_id,
        "threshold": scenario.threshold,
        "damage_per_artifact": scenario.damage_per_artifact,
        "artifacts_count": scenario.artifacts_count,
        "sleep_merge_mode": scenario.sleep_merge_mode,
        "triggered_sleep": triggered,
        "branches": branches,
        "merged": merge["merged"],
        "hp_after": round(hp_after, 3),
        "exit_ok": exit_ok,
    }


# --------------------------------------------------------------------------
# Статистика (канон гл.23: доля успешных из N + разброс по срезам)
# --------------------------------------------------------------------------
def _rate_and_std(values: List[bool]) -> Dict[str, Any]:
    n = len(values)
    if n == 0:
        return {"n": 0, "success_rate": 0.0, "std": 0.0}
    ok = sum(1 for v in values if v)
    std = statistics.stdev([1.0 if v else 0.0 for v in values]) if n > 1 else 0.0
    return {"n": n, "success_rate": round(ok / n, 4), "std": round(std, 4)}


def aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Сводная статистика: доля успехов, разброс, срезы, вердикт.

    Срезы (гл.23): по threshold и по sleep_merge_mode.
    Вердикт: stable если глобальный std мал (< 0.25), иначе unstable.
    """
    overall = _rate_and_std([r["exit_ok"] for r in results])

    by_threshold: Dict[str, Any] = {}
    for t in sorted({r["threshold"] for r in results}):
        group = [r for r in results if r["threshold"] == t]
        by_threshold[str(t)] = _rate_and_std([r["exit_ok"] for r in group])

    by_mode: Dict[str, Any] = {}
    for m in sorted({r["sleep_merge_mode"] for r in results}):
        group = [r for r in results if r["sleep_merge_mode"] == m]
        by_mode[m] = _rate_and_std([r["exit_ok"] for r in group])

    verdict = "stable" if overall["std"] < 0.25 else "unstable"
    return {
        "scenarios_total": len(results),
        "success_rate": overall["success_rate"],
        "std": overall["std"],
        "slices": {"by_threshold": by_threshold, "by_merge_mode": by_mode},
        "verdict": verdict,
        "runs": results,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _print_table(stats: Dict[str, Any]) -> None:
    print(f"\nverdict: {stats['verdict']}  "
          f"scenarios_total={stats['scenarios_total']}  "
          f"success_rate={stats['success_rate']}  std={stats['std']}")
    for slice_name, groups in stats["slices"].items():
        print(f"\n[{slice_name}]")
        for key, g in groups.items():
            print(f"  {key:>10}: n={g['n']:>3}  rate={g['success_rate']:.3f}  std={g['std']:.3f}")


def _cmd_run(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed) if args.seed is not None else None
    all_scenarios = scenarios()
    selected = all_scenarios[:args.limit] if args.limit else all_scenarios
    results = [run_scenario(sc, rng) for sc in selected]
    stats = aggregate(results)
    print(f"scenarios_total={stats['scenarios_total']}  "
          f"success_rate={stats['success_rate']}  std={stats['std']}  "
          f"verdict={stats['verdict']}")
    if args.table:
        _print_table(stats)
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"json: {out}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="monte_carlo_sleep.py",
        description="Monte-Carlo прогоны цикла сна (M8): сетка сценариев -> "
                    "статистика успеха и разброса по срезам")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="прогнать сетку сценариев")
    p_run.add_argument("--limit", type=int, default=None,
                       help="ограничить число сценариев (по умолчанию все 81)")
    p_run.add_argument("--seed", type=int, default=42,
                       help="seed RNG для детерминизма (default=42)")
    p_run.add_argument("--json", default=None,
                       help="путь для записи полного результата JSON")
    p_run.add_argument("--table", action="store_true",
                       help="печатать таблицу срезов")
    p_run.set_defaults(fn=_cmd_run)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())