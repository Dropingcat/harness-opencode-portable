# -*- coding: utf-8 -*-
"""
auto_bootstrap.py — АВТОНОМНЫЙ СТАРТ Meta-Cycle.

Вызывается ПРИ СТАРТЕ любой задачи оркестратора (не вручную):
  1. Автозапуск демона (если не запущен) — фоновый процесс.
  2. Автоинжекция дашборда в контекст (HP/урон/причины/сон).
  3. Автообработка контракта сна (если появился — выполнить ветки, merge).

Изоляция: читает только state-файлы (не вмешивается в контекст агента).
Оркестратор (LLM) НЕ управляет этим — скрипт сам.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from orchestrator_integration import OrchestratorIntegration
from daemon_safety import DaemonLease, FileLease, execute_verified


class AutoBootstrap:
    """Автономный старт: демон + инжекция + обработка контракта."""

    def __init__(self, orchestrator: str = 'research',
                 state_dir: Optional[str] = None,
                 daemon_interval: float = 30.0,
                 auto_start_daemon: bool = True) -> None:
        self.orchestrator = orchestrator
        self.meta = OrchestratorIntegration(orchestrator, state_dir=state_dir)
        self.state_dir = self.meta.state_dir
        self.contract_file = self.state_dir / f'{orchestrator}_sleep_contract.json'
        self.pid_file = self.state_dir / f'{orchestrator}_daemon.pid'
        self.daemon_interval = daemon_interval
        self.auto_start_daemon = auto_start_daemon
        self._processed_contracts: set = set()

    # ------------------------------------------------------ 1. автозапуск демона

    def ensure_daemon(self) -> bool:
        """Проверить, запущен ли демон; если нет — поднять (фоновый процесс)."""
        if not self.auto_start_daemon:
            return False
        lease = DaemonLease(self.state_dir, self.orchestrator)
        if lease.live(max(60, self.daemon_interval * 3)):
            return True
        # Unknown legacy live PID blocks startup; it is not verified identity.
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text(encoding='utf-8').strip())
                if self._is_alive(pid):
                    return False
            except Exception:
                pass
        startup = FileLease(self.state_dir / f'{self.orchestrator}_daemon.start.lock')
        if not startup.acquire():
            return False
        try:
            return self._start_daemon(lease)
        finally:
            startup.close()

    def _start_daemon(self, lease) -> bool:
        import uuid
        if lease.live(max(60, self.daemon_interval * 3)):
            return True
        # Held lease with stale/mismatched identity: block, never duplicate.
        if not lease.lock.acquire():
            return False
        lease.lock.close()
        token = uuid.uuid4().hex
        script = _META / 'meta_daemon.py'
        args = [sys.executable, '-u', str(script), '--daemon',
                '--orchestrator', self.orchestrator,
                '--interval', str(self.daemon_interval),
                '--state-dir', str(self.state_dir), '--instance-token', token]
        stdout_path = self.state_dir / f'{self.orchestrator}_daemon.stdout.log'
        stderr_path = self.state_dir / f'{self.orchestrator}_daemon.stderr.log'
        proc = None
        try:
            # Popen duplicates/inherits the descriptors. Close only the parent's
            # handles immediately after spawn, including partial-open failures.
            with stdout_path.open('ab', buffering=0) as stdout, \
                    stderr_path.open('ab', buffering=0) as stderr:
                if os.name == 'nt':
                    # Windows: CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
                    DETACHED = 0x00000008
                    CREATE_NEW_PG = 0x00000200
                    proc = subprocess.Popen(args, creationflags=DETACHED | CREATE_NEW_PG,
                                            stdout=stdout, stderr=stderr)
                else:
                    proc = subprocess.Popen(args, start_new_session=True,
                                            stdout=stdout, stderr=stderr)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                exit_code = proc.poll()
                if exit_code is not None:
                    self._record_startup('exited', token, proc, exit_code=exit_code)
                    return False
                if lease.live(max(60, self.daemon_interval * 3), token=token):
                    self._record_startup('ready', token, proc)
                    return True
                time.sleep(0.05)
            self._record_startup('timeout', token, proc, timeout_seconds=5.0)
            return False  # Spawn is not proof of daemon readiness.
        except Exception as e:
            self._record_startup('spawn-error' if proc is None else 'startup-error',
                                 token, proc, error=f'{type(e).__name__}: {e}')
            return False

    def _record_startup(self, status, token, proc=None, **details) -> None:
        """Append attempt diagnostics without overwriting earlier failures."""
        record = {'created_at': datetime.now().isoformat(), 'status': status,
                  'orchestrator': self.orchestrator, 'token': token,
                  'stdout_log': str(self.state_dir / f'{self.orchestrator}_daemon.stdout.log'),
                  'stderr_log': str(self.state_dir / f'{self.orchestrator}_daemon.stderr.log'),
                  **details}
        if proc is not None and isinstance(proc.pid, int):
            record['pid'] = proc.pid
        path = self.state_dir / f'{self.orchestrator}_daemon.startup.jsonl'
        try:
            with path.open('a', encoding='utf-8') as log:
                log.write(json.dumps(record, ensure_ascii=False) + '\n')
                log.flush()
                os.fsync(log.fileno())
        except OSError as exc:
            # Disk/permission failures cannot be made durable; do not hide them.
            print(f'Cannot persist daemon startup diagnostic to {path}: {exc}; {record}',
                  file=sys.stderr)

    @staticmethod
    def _is_alive(pid: int) -> bool:
        try:
            if os.name == 'nt':
                import ctypes
                PROCESS_QUERY_INFORMATION = 0x0400
                h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
                if not h:
                    return False
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    # ------------------------------------------------------ 2. автоинжекция дашборда

    def inject_dashboard(self) -> str:
        """Дашборд для контекста (LLM видит при старте задачи)."""
        dash = self.meta.dashboard_text()
        # предупреждение, если система в опасности
        if self.meta.veto():
            dash += "\n⚠️ VETO: система в критическом состоянии — задача заблокирована."
        return dash

    # ------------------------------------------------------ 3. автообработка контракта

    def process_sleep_contract(self, branch_executor: Optional[Any] = None,
                               merge_verifier: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """
        Если контракт сна появился/обновлён — выполнить ветки, merge, очистить.
        БЕЗ участия оркестратора (LLM). branch_executor — изолированный агент.
        """
        if not self.contract_file.exists():
            return None
        try:
            contract = json.loads(self.contract_file.read_text(encoding='utf-8'))
        except Exception:
            return None
        # уже обработан?
        cid = contract.get('plan_id') or contract.get('contract_id')
        if cid in self._processed_contracts:
            return None
        # A legacy merged flag is not evidence; never authorize recovery from it.

        branches = contract.get('branches', [])
        # выполнение веток (изолированный исполнитель)
        result = execute_verified(branches, branch_executor, merge_verifier)
        contract.update(result)
        self.contract_file.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')

        # merge результат
        if result.get('merged'):
            self.meta.sleep_merge(success=True, result_summary=result.get('result', 'merged'))
            contract['merged'] = True
            contract['result'] = result.get('result', '')
            self.contract_file.write_text(
                json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
            # корзина очищается демоном (следующий такт)
            self._processed_contracts.add(cid)
            return contract
        return contract

    def _default_executor(self, branches: List[str]) -> Dict[str, Any]:
        """No production executor installed: observe and leave recovery blocked."""
        return execute_verified(branches)

    # ------------------------------------------------------ фасад: полный автостарт

    def bootstrap(self, branch_executor: Optional[Any] = None,
                  merge_verifier: Optional[Any] = None) -> Dict[str, Any]:
        """Всё вместе: демон + инжекция + контракт."""
        daemon_started = self.ensure_daemon()
        dashboard = self.inject_dashboard()
        contract_result = self.process_sleep_contract(branch_executor, merge_verifier)
        return {
            'daemon_started': daemon_started,
            'dashboard': dashboard,
            'contract_processed': contract_result,
            'hp': self.meta.health.health_points,
            'veto': self.meta.veto(),
        }


# ------------------------------------------------------ CLI (для теста/интеграции)
def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description='Автономный старт Meta-Cycle')
    ap.add_argument('--orchestrator', default='research')
    ap.add_argument('--state-dir', default=None)
    ap.add_argument('--no-daemon', action='store_true')
    args = ap.parse_args()

    ab = AutoBootstrap(args.orchestrator, state_dir=args.state_dir,
                       auto_start_daemon=not args.no_daemon)
    result = ab.bootstrap()
    print(json.dumps({'dashboard': result['dashboard'],
                      'daemon_started': result['daemon_started'],
                      'contract_processed': result['contract_processed'],
                      'hp': result['hp'], 'veto': result['veto']},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
