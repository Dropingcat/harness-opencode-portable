# -*- coding: utf-8 -*-
"""
meta_daemon.py — АВТОНОМНЫЙ ЦИКЛ Meta-Cycle (без ручного запуска агента).

Циклы работают САМИ:
  1. Демон периодически запускает аудит (external auditor v2 -> корзина).
  2. Скрипт считает урон из корзины.
  3. При пороге 100 — принудительный сон.
  4. Планировщик кластеризует долги → ветки → КОНТРАКТ В ФАЙЛ (агент увидит).
  5. Спец-агент выполняет ветки (внедряемый executor_fn).
  6. Merge всех веток → корзина очищена → продолжение.

Агент-оркестратор:
  - видит дашборд в промпте (HP, урон, причины) — через PromptEngine;
  - при входе в сон видит контракт (файл sleep_contract.json) на выполнение веток.

Запуск (автономный):
  python meta_daemon.py --daemon --interval 10 --loops 0 (бесконечно)
  или разово: python meta_daemon.py --once
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
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


class MetaDaemon:
    """Автономный демон-цикл."""

    def __init__(self, orchestrator: str = 'research',
                 basket_dir: str | None = None,
                 state_dir: str | None = None,
                 threshold: int = 100,
                 artifacts_dir: str | None = None,
                 contract_file: str | None = None,
                 hardcore: bool = True) -> None:
        self.orchestrator = orchestrator
        self.hardcore = hardcore
        self.basket = DamageBasket(basket_dir, threshold=threshold)
        self.auditor = ExternalAuditorV2('daemon', basket=self.basket, hardcore=hardcore)
        self.planner = SleepPlannerAgent(self.basket)
        self.meta = OrchestratorIntegration(orchestrator, state_dir=state_dir)
        self.ctrl = SleepController(self.meta, self.auditor)
        # папка с артефактами для проверки (или пусто = проверять состояние)
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None
        # контракт сна (агент увидит его при входе в сон)
        self.contract_file = Path(contract_file) if contract_file else Path(
            _META.parent.parent / '.meta_state' / f'{orchestrator}_sleep_contract.json')
        self.contract_file.parent.mkdir(parents=True, exist_ok=True)
        self.loop_count = 0
        self.sleep_count = 0
        # внедряемый исполнитель веток (спец-агент)
        self.branch_executor = None  # fn(branches) -> {merged: bool, result: str}

    # ------------------------------------------------------ основной цикл

    def run_once(self) -> dict:
        """Один такт цикла (для --once и для --daemon)."""
        self.loop_count += 1
        # 1. Собрать артефакты (из папки или из state)
        artifacts = self._collect_artifacts()

        # 2. Аудит каждого артефакта → корзина
        total_dropped = 0
        for art in artifacts:
            dropped = self.auditor.observe_and_audit(art)
            total_dropped += len(dropped)

        # 3. Проверка порога → сон
        if self.basket.should_trigger_sleep():
            self.sleep_count += 1
            plan = self.planner.run_plan(self.orchestrator)
            if plan:
                # 4. Контракт в файл (агент увидит при входе в сон)
                contract = plan.to_dict()
                contract['orchestrator_prompt'] = self._build_sleep_prompt(plan)
                contract['created_at'] = datetime.now().isoformat()
                self.contract_file.write_text(
                    json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')

                # 5. Выполнение веток (спец-агент)
                if self.branch_executor:
                    result = self.branch_executor(plan.branches)
                else:
                    result = self._default_branch_executor(plan.branches)

                # 6. Merge → корзина очищена → контракт помечен done
                if result.get('merged'):
                    self.meta.sleep_merge(success=True,
                                          result_summary=result.get('result', 'merged'))
                    self.basket.reset()
                    contract['merged'] = True
                    contract['result'] = result.get('result', '')
                    self.contract_file.write_text(
                        json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
                    return {'sleep': True, 'merged': True, 'branches': plan.branches,
                            'hp': self.meta.health.health_points}
        return {'sleep': False, 'hp': self.meta.health.health_points,
                'damage': self.basket.total_damage(), 'dropped': total_dropped}

    def run_daemon(self, interval: float = 10.0, loops: int = 0) -> None:
        """Бесконечный автономный цикл (loops=0 = вечно)."""
        print(f'[daemon:{self.orchestrator}] запущен, интервал={interval}s')
        i = 0
        try:
            while loops == 0 or i < loops:
                i += 1
                res = self.run_once()
                if res.get('sleep'):
                    print(f'[daemon] цикл {i}: СОН → merge веток {res["branches"]}, HP={res["hp"]}')
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f'\n[daemon:{self.orchestrator}] остановлен после {i} тактов')

    # ------------------------------------------------------ внутренние

    def _collect_artifacts(self) -> list:
        """Артефакты для аудита: из файлов в папке или дефолт."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            arts = []
            for f in sorted(self.artifacts_dir.glob('*.json'))[:20]:
                try:
                    arts.append(json.loads(f.read_text(encoding='utf-8')))
                except Exception:
                    continue
            return arts
        # дефолт: проверить 'текст' (аудит найдёт нарушения, если есть)
        return [{'template': 'T3', 'slots': {
            'data': {'entity_id': 'OBS_XRD_FWHM'},
            'claim': {'entity_id': 'CLAIM_FERROMAGNETISM', 'modality': 'proves'}}}]

    def _build_sleep_prompt(self, plan) -> str:
        """Промпт сна для оркестратора (виден в контракте)."""
        return (f"[SLEEP-CONTRACT] {plan.sleep_prompt()}\n"
                f"Дашборд: {self.meta.dashboard_text()}\n"
                f"Выполни ветки, слей их без багов, не уводи от задачи.")

    def _default_branch_executor(self, branches: list) -> dict:
        """Дефолтный исполнитель веток (в реальности — спец-агент с git)."""
        # имитация: каждая ветка фиксируется в legacy
        for b in branches:
            self.meta.on_failure(f'[sleep-fix] {b}', task='sleep', tags=['sleep', 'daemon'])
        return {'merged': True, 'result': f'merged {len(branches)} branches'}


def main() -> int:
    ap = argparse.ArgumentParser(description='Автономный Meta-Cycle демон')
    ap.add_argument('--once', action='store_true', help='один такт')
    ap.add_argument('--daemon', action='store_true', help='бесконечный цикл')
    ap.add_argument('--interval', type=float, default=10.0)
    ap.add_argument('--loops', type=int, default=0, help='0 = бесконечно')
    ap.add_argument('--orchestrator', default='research')
    ap.add_argument('--basket-dir', default=None)
    ap.add_argument('--state-dir', default=None)
    ap.add_argument('--threshold', type=int, default=100)
    ap.add_argument('--artifacts-dir', default=None)
    ap.add_argument('--contract-file', default=None)
    ap.add_argument('--hardcore', action='store_true', default=True,
                    help='хардкор-аудит (по умолчанию вкл)')
    args = ap.parse_args()

    dm = MetaDaemon(
        orchestrator=args.orchestrator,
        basket_dir=args.basket_dir,
        state_dir=args.state_dir,
        threshold=args.threshold,
        artifacts_dir=args.artifacts_dir,
        contract_file=args.contract_file,
        hardcore=args.hardcore,
    )
    if args.daemon:
        dm.run_daemon(interval=args.interval, loops=args.loops)
    else:
        res = dm.run_once()
        print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())