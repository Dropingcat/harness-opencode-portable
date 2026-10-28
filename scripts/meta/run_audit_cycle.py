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

    # This legacy command has no independent executor/verifier. Fail closed
    # before constructing stateful audit/meta/controller objects (A3 owns repair).
    print(json.dumps({'status': 'blocked', 'code': 'UNVERIFIED_LEGACY_AUTO_REPAIR',
                      'reason': 'legacy auto-repair requires a verified execution path'}))
    return 2



if __name__ == '__main__':
    raise SystemExit(main())
