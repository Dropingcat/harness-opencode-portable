# -*- coding: utf-8 -*-
"""
memory_injector.py — ДИНАМИЧЕСКАЯ ПЕРЕДАЧА ПАМЯТИ В ПРОМТ (dynamic pipeline).

Проблема: L1-L3 память существует, но НЕ инжектится в промт агента динамически.
Решение: MemoryInjector читает memory_registry (L3 lessons) + L1/L2 файлы
и предоставляет переменные для PromptEngine:
  {memory_lessons} — L3 уроки (топ по admissions)
  {memory_l2}      — L2 task memory (если есть)
  {memory_stats}   — статистика
Инжекция происходит через dynamic pipeline (PromptEngine.render),
а не вручную.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_ROOT = Path(os.environ.get(
    'OPENCODE_HARNESS_ROOT', str(Path(__file__).parent.parent.parent)))


class MemoryInjector:
    """Читает память L1-L3 и отдаёт переменные для промта."""

    def __init__(self, harness_root: Optional[str] = None,
                 max_lessons: int = 5) -> None:
        self.root = Path(harness_root) if harness_root else _DEFAULT_ROOT
        self.registry_file = self.root / 'config' / 'memory_registry.json'
        self.max_lessons = max_lessons

    # ------------------------------------------------------ L3

    def l3_lessons(self, top: int = 5) -> List[Dict[str, Any]]:
        """Топ уроков L3 по admissions."""
        if not self.registry_file.exists():
            return []
        try:
            d = json.loads(self.registry_file.read_text(encoding='utf-8'))
            lessons = d.get('levels', {}).get('L3', {}).get('lessons', {})
        except Exception:
            return []
        items = sorted(lessons.values(),
                       key=lambda e: int(e.get('admissions', 0)), reverse=True)
        return items[:top]

    # ------------------------------------------------------ L2 (task memory)

    def l2_memories(self) -> List[Dict[str, Any]]:
        """L2 task memory: из файлов l2_memory*.json если есть."""
        found = []
        for p in self.root.glob('**/l2_memory*.json'):
            try:
                d = json.loads(p.read_text(encoding='utf-8'))
                cands = d.get('candidate_lessons', []) if isinstance(d, dict) else []
                found.extend(cands)
            except Exception:
                continue
        return found[:5]

    # ------------------------------------------------------ L1 (snapshot)

    def l1_snapshot(self) -> Dict[str, Any]:
        """L1: audit snapshot (если есть runtime_snapshot)."""
        p = self.root / 'config' / 'runtime_snapshot.json'
        if not p.exists():
            return {}
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
            return {'version': d.get('version'),
                    'policy_hash': d.get('policy_hash'),
                    'routes': len(d.get('routes', {})) if isinstance(d.get('routes'), dict) else 0}
        except Exception:
            return {}

    # ------------------------------------------------------ переменные для промта

    def variables(self) -> Dict[str, Any]:
        """Переменные для PromptEngine: {memory_lessons}, {memory_l2}, {memory_stats}."""
        lessons = self.l3_lessons(self.max_lessons)
        l2 = self.l2_memories()
        l1 = self.l1_snapshot()
        # текстовая проекция (LLM видит только её, не сырые данные)
        lesson_lines = []
        for l in lessons:
            text = str(l.get('lesson_text', ''))[:150]
            codes = ', '.join(str(c) for c in l.get('reason_codes', []) or [])
            adm = l.get('admissions', 0)
            lesson_lines.append(f"[x{adm}] {text} ({codes})")
        return {
            'memory_lessons': "\n".join(lesson_lines) if lesson_lines else "нет уроков",
            'memory_lessons_count': len(lessons),
            'memory_l2': json.dumps(l2, ensure_ascii=False)[:500] if l2 else "нет L2",
            'memory_stats': f"L3={len(lessons)}, L2={len(l2)}, L1={json.dumps(l1, ensure_ascii=False)}",
        }