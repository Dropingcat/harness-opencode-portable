# -*- coding: utf-8 -*-
"""
prompt_engine.py — V5 Prompt Engine (динамический рендер промптов).

Template != prompt. Шаблон — версионированная исполняемая спецификация с
переменными {placeholders}, которые подтягиваются из скриптов/state (V-1 health,
legacy, статус, метрики). LLM видит только отрендеренный текст (G(S_t)), не state.

Формат шаблона (YAML/JSON):
  id, version, kind, slots, constraints, postconditions, metrics.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from orchestrator_integration import OrchestratorIntegration
from memory_injector import MemoryInjector


class Template:
    """Версионированный шаблон промпта."""

    def __init__(self, template_id: str, version: str, kind: str,
                 system_template: str, user_template: str,
                 required_vars: Optional[List[str]] = None,
                 constraints: Optional[List[str]] = None,
                 postconditions: Optional[List[str]] = None,
                 metrics: Optional[List[str]] = None) -> None:
        self.id = template_id
        self.version = version
        self.kind = kind
        self.system_template = system_template   # с {placeholders}
        self.user_template = user_template
        self.required_vars = required_vars or []
        self.constraints = constraints or []
        self.postconditions = postconditions or []
        self.metrics = metrics or []

    def render(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """Рендер: подстановка переменных. Отсутствующие required → ошибка."""
        missing = [v for v in self.required_vars if v not in variables]
        if missing:
            raise ValueError(f"Шаблон {self.id}: отсутствуют переменные {missing}")
        sys_out = self._substitute(self.system_template, variables)
        user_out = self._substitute(self.user_template, variables)
        return {"system": sys_out, "user": user_out}

    def _substitute(self, text: str, variables: Dict[str, Any]) -> str:
        def repl(m):
            name = m.group(1)
            val = variables.get(name, '')
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False, indent=1)
            return str(val)
        return re.sub(r'\{(\w+)\}', repl, text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "version": self.version, "kind": self.kind,
            "system_template": self.system_template[:80],
            "user_template": self.user_template[:80],
            "required_vars": self.required_vars,
            "constraints": self.constraints, "postconditions": self.postconditions,
            "metrics": self.metrics,
        }


class PromptEngine:
    """Реестр шаблонов + рендер с переменными из state (V-1/legacy/status)."""

    def __init__(self, orchestrator: str = "research",
                 state_dir: Optional[str] = None) -> None:
        self.orchestrator = orchestrator
        self.templates: Dict[str, Template] = {}
        # интеграция с Meta-Cycle (источник переменных)
        self.meta = OrchestratorIntegration(orchestrator, state_dir=state_dir)
        # динамическая память (L1-L3) для промта
        self.memory = MemoryInjector()
        # внедряемые провайдеры доп. переменных
        self.providers: Dict[str, Callable[[], Any]] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Стандартные шаблоны оркестратора."""
        self.register(Template(
            "task_intro", "1.0", "orchestrator",
            system_template=(
                "Ты — {role} в Harness. {dashboard}\n"
                "Состояние системы: {health_summary}.\n"
                "Память (L3-уроки): {memory_lessons}\n"
                "Память (L2): {memory_l2}\n"
                "Инварианты: {invariants}.\n"
                "Правило: не нарушай инварианты; LLM не меняет состояние напрямую.\n"
                "Ограничения: {constraints}."),
            user_template=(
                "ЗАДАЧА: {task}\n"
                "КОНТЕКСТ: {context}\n"
                "ПОХОЖИЕ ПРОВАЛЫ (legacy): {legacy_hint}\n"
                "Ожидаемый выход: {expected_output}"),
            required_vars=["role", "task", "health_summary"],
            constraints=["Не галлюцинируй числа", "Каждое утверждение с источником"],
            postconditions=["Выход проходит гейты"],
            metrics=["citation", "factual"],
        ))

    def register(self, template: Template) -> None:
        self.templates[template.id] = template

    def render(self, template_id: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Рендер шаблона с переменными из state + провайдеров + overrides."""
        if template_id not in self.templates:
            raise KeyError(f"Нет шаблона {template_id}")
        tpl = self.templates[template_id]
        # базовые переменные из Meta-Cycle state
        status = self.meta.status()
        dash = self.meta.dashboard()
        vars_ = {
            "role": f"{self.orchestrator}-orchestrator",
            "health_summary": self._health_text(status),
            "health_hp": status['health'].get('health_points', 100.0),
            "health_level": status['health'].get('level', 'excellent'),
            "veto": status['veto'],
            "legacy_records": status['legacy_records'],
            "cycle": status['cycle'],
            "invariants": "физика не врёт; числа с единицами; цитаты к claim",
            "constraints": "; ".join(tpl.constraints) or "нет",
            "legacy_hint": self._legacy_hint(),
            # дашборд (V-1): HP, урон, причины — от внешнего валидатора
            "dashboard": self.meta.dashboard_text(),
            "hp": dash['hp'],
            "damage_total": dash['total_damage_taken'],
            "recent_damage": "\n".join(
                f"-{abs(dm['damage'])} HP: [{dm['source']}] {dm.get('rule_id','')} {dm['message']}"
                for dm in dash['recent_damage']) or "нет",
            "sleep_status": json.dumps(dash['sleep'], ensure_ascii=False) if dash['sleep'] else "не в сне",
            # память L1-L3 (динамическая, через MemoryInjector)
            **self.memory.variables(),
        }
        # провайдеры
        for name, fn in self.providers.items():
            try:
                vars_[name] = fn()
            except Exception:
                vars_[name] = ""
        # overrides
        if overrides:
            vars_.update(overrides)
        return tpl.render(vars_)

    # --- провайдеры состояния ---
    def _health_text(self, status: Dict[str, Any]) -> str:
        h = status.get('health', {})
        return (f"HP={h.get('health_points', 100.0):.0f}, "
                f"level={h.get('level', 'excellent')}, "
                f"lives={h.get('lives_remaining', 3)}")

    def _legacy_hint(self) -> str:
        if self.meta.legacy.records:
            recent = self.meta.legacy.records[-3:]
            return "; ".join(f"[{r.rejection_reason}] {r.hypothesis_tested[:40]}"
                             for r in recent)
        return "нет"

    # --- персистентность шаблонов ---
    def save_registry(self, path: str) -> None:
        data = {tid: t.to_dict() for tid, t in self.templates.items()}
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding='utf-8')

    def load_registry(self, path: str) -> None:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        for tid, t in data.items():
            self.register(Template(tid, t['version'], t['kind'],
                                   t['system_template'], t['user_template'],
                                   t.get('required_vars'), t.get('constraints'),
                                   t.get('postconditions'), t.get('metrics')))