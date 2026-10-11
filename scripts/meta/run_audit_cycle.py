# -*- coding: utf-8 -*-
"""
run_audit_cycle.py — ДЕТЕРМИНИРОВАННЫЙ ЦИКЛ аудита (скрипт ведёт).

Поток (изоляция полная):
  1. Скрипт формирует контракт аудита ПОД ТЕКУЩИЙ промпт оркестратора.
  2. Аудитор наблюдает артефакт, бросает долги в КОРЗИНУ.
  3. Скрипт считает урон из корзины (аудитор урон НЕ считает).
  4. Если урон >= 100 → планировщик (изолированный) кластеризует → промпт сна.
  5. SleepController выполняет сон: спец-агент → ветки → merge → выход.

Цикл управляется СКРИПТОМ, не LLM.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from damage_basket import DamageBasket
from auditor_v2 import ExternalAuditorV2
from sleep_planner import SleepPlannerAgent
from orchestrator_integration import OrchestratorIntegration
from sleep_controller import SleepController


def main() -> int:
    ap = argparse.ArgumentParser(description='Детерминированный цикл внешнего аудита')
    ap.add_argument('--orchestrator', default='research')
    ap.add_argument('--artifact', default='', help='текст артефакта для проверки')
    ap.add_argument('--orchestrator-prompt', default='', help='текущий промпт оркестратора')
    ap.add_argument('--threshold', type=int, default=100)
    ap.add_argument('--basket-dir', default=None)
    ap.add_argument('--state-dir', default=None)
    ap.add_argument('--loop', type=int, default=1, help='сколько раз прогнать цикл')
    args = ap.parse_args()

    # 1. Корзина (скрипт-счётчик)
    basket = DamageBasket(args.basket_dir, threshold=args.threshold)

    # 2. Аудитор (изолирован) — контракт под промпт оркестратора
    auditor = ExternalAuditorV2('external-v2', basket=basket)
    if args.orchestrator_prompt:
        auditor.bind_contract(args.orchestrator, args.orchestrator_prompt)

    # 3. Планировщик (изолирован, видит только корзину)
    planner = SleepPlannerAgent(basket)

    # 4. Оркестратор-интеграция + SleepController
    meta = OrchestratorIntegration(args.orchestrator, state_dir=args.state_dir)
    ctrl = SleepController(meta, auditor)

    for i in range(args.loop):
        print(f'--- цикл {i+1} ---')
        # 2a. Аудит артефакта → бросок в корзину
        dropped = auditor.observe_and_audit(args.artifact or f'артефакт {i+1}')
        print(f'[аудит] observations={auditor.observations}, dropped={len(dropped)}, '
              f'урон в корзине={basket.total_damage()}/{basket.threshold}')

        # 3a. Скрипт проверяет порог → планировщик
        plan = planner.run_plan(args.orchestrator)
        if plan:
            print(f'[сон] СРАБОТАЛ ТРИГГЕР урона {basket.total_damage()} >= {basket.threshold}')
            print(plan.sleep_prompt())
            # 5. SleepController: сон через спец-агента
            contract = ctrl.check_and_force_sleep(args.artifact or f'артефакт {i+1}',
                                                  f'задача {i+1}')
            if contract and contract.merged:
                print(f'[сон] ВЕТКИ СЛИТЫ: {contract.branches}')
                basket.reset()
                print(f'[сон] корзина очищена, HP={meta.health.health_points}')
            else:
                print('[сон] не удалось слить')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())