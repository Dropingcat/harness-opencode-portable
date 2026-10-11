# -*- coding: utf-8 -*-
"""
memory_circulator.py — ИЗОЛИРОВАННЫЙ АГЕНТ-ПЕРЕНОСЧИК ПАМЯТИ (через роутер).

Схема памяти (3 уровня, циркуляция без забывания):
  L1 (быстрая/текущая): формируется РОУТЕРОМ из переменных baseline задачи.
      Хранится в runtime vars (не персистентно для агента).
  L2 (сессионная): формируется роутер-агентом и им обновляется.
      Хранится в l2_memory/<task_id>.json (candidate_lessons).
  L3 (глубокая/глобальная): уроки и глобальные паттерны.
      Хранится в config/memory_registry.json (memory_bridge L3).

Циркуляция:
  L3 -> L1/L2: при старте задачи роутер подтягивает релевантные L3-уроки
               в переменные промта (PromptEngine {memory_lessons}).
  L1/L2 -> L3: изолированный переносчик (этот агент) по достижении порога
               переносит candidate_lessons в L3 (memory_bridge add-file),
               с дедупликацией (stable_key) — забывания нет, всё накапливается.

Все изменения: git add + commit (после каждого переноса).
Изоляция: переносчик видит только l2_memory/* + registry, не контекст агента.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

_ROOT = _META.parent.parent   # harness root
_MEMORY_BRIDGE = _ROOT / 'scripts' / 'memory' / 'memory_bridge.py'
_L2_DIR = _ROOT / '.l2_memory'


class MemoryCirculator:
    """Изолированный переносчик: L2 -> L3, циркуляция L3 <-> L1/L2, git-коммит."""

    def __init__(self, l2_dir: Optional[str] = None,
                 promote_threshold: int = 2) -> None:
        self.l2_dir = Path(l2_dir) if l2_dir else _L2_DIR
        self.l2_dir.mkdir(parents=True, exist_ok=True)
        self.memory_bridge = _MEMORY_BRIDGE
        self.promote_threshold = promote_threshold   # admissions >= N -> L3
        self.circulation_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------ L1 (быстрая, переменные)

    def l1_variables(self, task: str, baseline: Dict[str, Any]) -> Dict[str, Any]:
        """L1: быстрые переменные (формирует роутер для промта)."""
        return {
            'task': task,
            'baseline_hash': self._hash(json.dumps(baseline, sort_keys=True)),
            'timestamp': datetime.now().isoformat(),
        }

    # ------------------------------------------------------ L2 (сессионная)

    def l2_remember(self, task_id: str, lesson: Dict[str, Any]) -> str:
        """Запись в L2 (сессионная память). Возвращает key."""
        f = self.l2_dir / f'{self._safe(task_id)}.json'
        data = {'task_id': task_id, 'candidate_lessons': []}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                data = {'task_id': task_id, 'candidate_lessons': []}
        # дедупликация по stable_json (БЕЗ _key/_admissions)
        clean = {k: v for k, v in lesson.items() if k not in ('_key', '_admissions')}
        key = self._hash(json.dumps(clean, sort_keys=True))
        lesson['_key'] = key
        exists = any(l.get('_key') == key for l in data['candidate_lessons'])
        if not exists:
            lesson['_admissions'] = 1
            data['candidate_lessons'].append(lesson)
        else:
            for l in data['candidate_lessons']:
                if l.get('_key') == key:
                    l['_admissions'] = int(l.get('_admissions', 1)) + 1
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return key

    # ------------------------------------------------------ L3 (глубокая) + перенос

    def promote_to_l3(self, task_id: str = '') -> List[str]:
        """
        Перенос L2 -> L3 (изолированный агент). Уроки с admissions >= threshold
        переходят в memory_bridge (L3). Забывания нет — всё накапливается.
        Возвращает ключи добавленных.
        """
        added = []
        for f in sorted(self.l2_dir.glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            tid = data.get('task_id', task_id)
            keep = []
            for cand in data.get('candidate_lessons', []):
                adm = int(cand.get('_admissions', 1))
                if adm >= self.promote_threshold:
                    # в L3 (через memory_bridge add)
                    lesson = {
                        'lesson_text': cand.get('lesson_text', ''),
                        'reason_codes': cand.get('reason_codes', []),
                        'evidence_refs': cand.get('evidence_refs', []),
                        'recurring_count': adm,
                        'task_id': tid,
                        'added_via': 'memory_circulator.promote',
                    }
                    if self._bridge_add(lesson):
                        added.append(self._hash(json.dumps(lesson, sort_keys=True)))
                else:
                    keep.append(cand)
            data['candidate_lessons'] = keep
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        if added:
            self._git_commit(f'promote {len(added)} lessons L2->L3')
        return added

    def circulate_l3_to_l1(self, task: str, top: int = 5) -> List[Dict[str, Any]]:
        """L3 -> L1/L2: подтянуть глобальные уроки для текущей задачи (роутер)."""
        lessons = []
        try:
            reg = self._load_registry()
            l3 = reg.get('levels', {}).get('L3', {}).get('lessons', {})
            items = sorted(l3.values(), key=lambda e: int(e.get('admissions', 0)),
                           reverse=True)
            lessons = items[:top]
        except Exception:
            pass
        return lessons

    # ------------------------------------------------------ внутренние

    def _bridge_add(self, lesson: Dict[str, Any]) -> bool:
        try:
            r = subprocess.run([sys.executable, str(self.memory_bridge), 'add',
                                json.dumps(lesson, ensure_ascii=False)],
                               capture_output=True, timeout=20,
                               cwd=str(_ROOT))
            return r.returncode == 0
        except Exception:
            return False

    def _load_registry(self) -> Dict[str, Any]:
        p = _ROOT / 'config' / 'memory_registry.json'
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
        return {'levels': {}}

    def _git_commit(self, message: str) -> None:
        try:
            subprocess.run(['git', '-C', str(_ROOT), 'add', 'config/memory_registry.json',
                            '.l2_memory'], capture_output=True, timeout=20)
            subprocess.run(['git', '-C', str(_ROOT), 'commit', '-m', message],
                           capture_output=True, timeout=30)
        except Exception:
            pass

    @staticmethod
    def _safe(name: str) -> str:
        return ''.join(c for c in name if c.isalnum() or c in '_-')[:60] or 'task'

    @staticmethod
    def _hash(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]

    def status(self) -> Dict[str, Any]:
        return {
            'l2_files': len(list(self.l2_dir.glob('*.json'))),
            'l3_lessons': len(self._load_registry().get('levels', {}).get('L3', {}).get('lessons', {})),
            'circulation_log': self.circulation_log[-5:],
        }