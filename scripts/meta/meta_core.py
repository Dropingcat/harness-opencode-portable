# -*- coding: utf-8 -*-
"""
meta_core.py — ЗАЦИКЛЕННЫЙ ЯДРО Meta-Cycle.

Связывает все модули в единый контур:
  аудит (хардкор) → корзина → урон → сон → планировщик → контракт →
  автообработка → скил-прокачка (SkillMaster) → память (memory_bridge) → дашборд

Все циклы работают между собой через state-файлы и memory_registry.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from orchestrator_integration import OrchestratorIntegration
from skill_master import SkillMaster
from auto_bootstrap import AutoBootstrap
from memory_circulator import MemoryCirculator


class MetaCore:
    """Ядро: все модули зациклены."""

    def __init__(self, orchestrator: str = 'research',
                 state_dir: Optional[str] = None,
                 memory_bridge: Optional[str] = None) -> None:
        self.orchestrator = orchestrator
        self.state_dir = Path(state_dir) if state_dir else Path(os.environ.get(
            'HARNESS_META_STATE', str(_META.parent.parent / '.meta_state')))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # memory_bridge script (harness: scripts/memory/memory_bridge.py)
        self.memory_bridge = memory_bridge or str(
            _META.parent / 'memory' / 'memory_bridge.py')
        # модули
        self.meta = OrchestratorIntegration(orchestrator, state_dir=self.state_dir)
        self.skills = SkillMaster(self.state_dir / 'skills')
        self.auto = AutoBootstrap(orchestrator, state_dir=self.state_dir)
        # циркулятор памяти (L2 сессия -> L3 глубокая)
        self.circulator = MemoryCirculator(l2_dir=self.state_dir / 'l2')
        # последние события (для дашборда)
        self.skill_events: List[Dict[str, Any]] = []
        self._load_skill_events()

    # ------------------------------------------------------ скил-прокачка + память

    def use_skill(self, skill_name: str, outcome: str = "ok",
                  temporary_script: str = "", notes: str = "") -> Optional[Dict[str, Any]]:
        """Использование скила → прокачка → урок в память → событие."""
        upgrade = self.skills.record_usage(skill_name, outcome,
                                           temporary_script=temporary_script,
                                           notes=notes)
        if upgrade:
            event = {
                'skill': skill_name,
                'level': upgrade.to_level,
                'changes': upgrade.changes,
                'contract': upgrade.new_contract,
                'template': upgrade.new_template,
                'ts': datetime.now().isoformat(),
            }
            self.skill_events.append(event)
            self._save_skill_events()
            # урок в L3-память (через memory_bridge)
            self._write_memory_lesson(skill_name, upgrade)
            return event
        return None

    def _write_memory_lesson(self, skill_name: str, upgrade) -> None:
        """Урок от прокачки скила → L3 registry (через memory_bridge)."""
        lesson = {
            "lesson_text": f"Skill '{skill_name}' reached level {upgrade.to_level}: "
                           f"{'; '.join(upgrade.changes)}",
            "reason_codes": [f"SKILL_{skill_name.upper()}", f"LEVEL_{upgrade.to_level}"],
            "evidence_refs": [f"skill:{skill_name}:lvl{upgrade.to_level}"],
            "recurring_count": 1,
            "task_id": self.orchestrator,
            "added_via": "meta_core.skill_upgrade",
        }
        try:
            subprocess.run([sys.executable, self.memory_bridge, 'add',
                            json.dumps(lesson, ensure_ascii=False)],
                           capture_output=True, timeout=20,
                           cwd=str(Path(self.memory_bridge).parents[2]))
        except Exception:
            pass

    # ------------------------------------------------------ дашборд (с скилами/памятью)

    def dashboard_text(self) -> str:
        """Дашборд: состояние + обновления скилов + память."""
        base = self.meta.dashboard_text()
        lines = [base]
        # скил-обновления
        if self.skill_events:
            lines.append("  [SKILL-UPDATES]")
            for ev in self.skill_events[-3:]:
                lines.append(f"    {ev['skill']} → level {ev['level']}: "
                             f"{', '.join(ev['changes'])}")
                if ev.get('contract'):
                    lines.append(f"      контракт: {json.dumps(ev['contract'], ensure_ascii=False)[:100]}")
        # память
        mem_stats = self._memory_stats()
        if mem_stats:
            lines.append(f"  [MEMORY] lessons={mem_stats}")
        return "\n".join(lines)

    def _memory_stats(self) -> int:
        try:
            r = subprocess.run([sys.executable, self.memory_bridge, 'stats'],
                               capture_output=True, timeout=15,
                               cwd=str(Path(self.memory_bridge).parents[2]))
            data = json.loads(r.stdout)
            return data.get('total_lessons', 0)
        except Exception:
            return 0

    # ------------------------------------------------------ персистентность скил-событий

    def _save_skill_events(self) -> None:
        f = self.state_dir / 'skill_events.json'
        f.write_text(json.dumps(self.skill_events[-20:], ensure_ascii=False, indent=2),
                     encoding='utf-8')

    def _load_skill_events(self) -> None:
        f = self.state_dir / 'skill_events.json'
        if f.exists():
            try:
                self.skill_events = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                self.skill_events = []

    # ------------------------------------------------------ полный цикл

    def cycle(self, task: str, artifact: Any = None) -> Dict[str, Any]:
        """Один полный такт: аудит + сон + скилы + память (L2 запись задачи)."""
        # 1. Автономный старт (демон, контракт)
        boot = self.auto.bootstrap()
        # 2. L2-сессионная память: каждая задача → запись (повседневный цикл)
        self.circulator.l2_remember(self.orchestrator, {
            'lesson_text': f'task: {task[:100]}',
            'reason_codes': [f'TASK_{self.orchestrator.upper()}'],
            'evidence_refs': [f'task:{task[:30]}'],
        })
        # 2b. L2 -> L3: перенос зрелых уроков (admissions >= порога)
        promoted = self.circulator.promote_to_l3(self.orchestrator)
        # 3. Дашборд с обновлениями
        dash = self.dashboard_text()
        return {
            'dashboard': dash,
            'daemon_started': boot['daemon_started'],
            'contract_processed': boot['contract_processed'],
            'hp': self.meta.health.health_points,
            'skill_events': len(self.skill_events),
            'l2_promoted': len(promoted),
            'veto': self.meta.veto(),
        }