# -*- coding: utf-8 -*-
"""
skill_master.py — ВАРГЕЙМ-СИСТЕМА ПРОКАЧКИ СКИЛОВ.

Принципы (варгейм):
- Скилы улучшаются ВНЕШНИМИ агентами (не самим владельцем).
- При частом использовании / переписывании / временных суб-скриптах —
  запускается МАСТЕР-СКИЛ, который:
    1) анализирует историю использования (SkillUsageRecord),
    2) улучшает скил (SkillUpgrade), 
    3) повышает УРОВЕНЬ ВЛАДЕНИЯ (Level 1..N),
    4) выдаёт НОВЫЙ КОНТРАКТ и ШАБЛОН использования,
    5) модулирует ГЛОБАЛЬНУЮ ПАМЯТЬ (опыт → patterns).
- Изоляция: мастер-скил видит только записи использования, не контекст агента.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from legacy import ExperiencePattern, PatternCategory


class SkillLevel:
    """Уровень владения скилом (прокачка)."""
    def __init__(self, level: int = 1, name: str = "novice") -> None:
        self.level = level
        self.name = name

    @property
    def next_threshold(self) -> int:
        """Порог использований для след. уровня (экспоненциальный рост)."""
        return 5 * (2 ** (self.level - 1))

    def to_dict(self) -> Dict[str, Any]:
        return {"level": self.level, "name": self.name,
                "next_threshold": self.next_threshold}


class SkillUsageRecord:
    """Запись использования скила (история)."""

    __slots__ = ("record_id", "skill_name", "timestamp", "context_hash",
                 "outcome", "temporary_script", "notes")

    def __init__(self, skill_name: str, outcome: str = "ok",
                 context_hash: str = "", temporary_script: str = "",
                 notes: str = "") -> None:
        self.record_id = str(uuid.uuid4())[:8]
        self.skill_name = skill_name
        self.timestamp = datetime.now().isoformat()
        self.context_hash = context_hash
        self.outcome = outcome          # ok | error | rewritten | temp_script
        self.temporary_script = temporary_script
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}


class SkillUpgrade:
    """Улучшение скила (что изменилось)."""

    def __init__(self, skill_name: str, from_level: int, to_level: int,
                 changes: List[str], new_contract: Dict[str, Any],
                 new_template: Dict[str, Any]) -> None:
        self.upgrade_id = str(uuid.uuid4())[:8]
        self.skill_name = skill_name
        self.from_level = from_level
        self.to_level = to_level
        self.changes = changes
        self.new_contract = new_contract
        self.new_template = new_template
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {"upgrade_id": self.upgrade_id, "skill_name": self.skill_name,
                "from_level": self.from_level, "to_level": self.to_level,
                "changes": self.changes, "new_contract": self.new_contract,
                "new_template": self.new_template, "timestamp": self.timestamp}


class SkillMaster:
    """Мастер-скил: прокачка скилов варгейм-способом."""

    def __init__(self, skills_dir: Optional[str] = None,
                 external_upgrader: Optional[Callable[[str, List[Dict[str, Any]]], List[str]]] = None,
                 memory_writer: Optional[Callable[[ExperiencePattern], None]] = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else Path(os.environ.get(
            'HARNESS_SKILLS_STATE', str(Path(__file__).parent.parent.parent / '.skills_state')))
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        # внедряемые: внешний агент-улучшатель, модулятор глобальной памяти
        self.external_upgrader = external_upgrader or self._default_upgrader
        self.memory_writer = memory_writer or self._default_memory_writer
        self._skills: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------ использование

    def record_usage(self, skill_name: str, outcome: str = "ok",
                     context_hash: str = "", temporary_script: str = "",
                     notes: str = "") -> Optional[SkillUpgrade]:
        """Фиксация использования → проверка порога → прокачка."""
        rec = SkillUsageRecord(skill_name, outcome, context_hash,
                               temporary_script, notes)
        skill = self._skills.setdefault(skill_name, {
            "level": 1, "name": "novice", "usage_count": 0, "records": []})
        skill["usage_count"] += 1
        skill["records"].append(rec.to_dict())
        self._save()

        # Порог достигнут? → мастер-скил запускается (внешний агент)
        if skill["usage_count"] >= SkillLevel(skill["level"]).next_threshold:
            return self._upgrade(skill_name)
        return None

    # ------------------------------------------------------ прокачка

    def _upgrade(self, skill_name: str) -> SkillUpgrade:
        """Мастер-скил улучшает скил (внешний агент + шаблон + контракт + память)."""
        skill = self._skills[skill_name]
        from_level = skill["level"]
        to_level = from_level + 1

        # 1. Внешний агент анализирует историю → изменения
        records = skill["records"]
        changes = self.external_upgrader(skill_name, records)

        # 2. Новый контракт и шаблон (уровень растёт)
        new_contract = self._build_contract(skill_name, to_level)
        new_template = self._build_template(skill_name, to_level, changes)

        # 3. Повышение уровня
        skill["level"] = to_level
        skill["name"] = ["novice", "apprentice", "adept", "expert", "master"][
            min(to_level - 1, 4)]
        self._save()

        upgrade = SkillUpgrade(skill_name, from_level, to_level,
                               changes, new_contract, new_template)
        # 4. Модуляция глобальной памяти (опыт → pattern)
        pattern = ExperiencePattern(
            PatternCategory.BEST_PRACTICE,
            f"skill:{skill_name}:lvl{to_level}",
            f"скил {skill_name} достиг уровня {to_level} ({skill['name']})",
            involved_skills=[skill_name],
            tags=[skill_name, f"level-{to_level}"])
        self.memory_writer(pattern)
        return upgrade

    # ------------------------------------------------------ контракты/шаблоны

    def get_contract(self, skill_name: str) -> Dict[str, Any]:
        """Контракт для ТЕКУЩЕГО уровня скила (не только при апгрейде)."""
        s = self._skills.get(skill_name, {"level": 1, "name": "novice"})
        return self._build_contract(skill_name, s["level"])

    def get_template(self, skill_name: str) -> Dict[str, Any]:
        """Шаблон для ТЕКУЩЕГО уровня (с учётом истории улучшений)."""
        s = self._skills.get(skill_name, {"level": 1, "name": "novice",
                                          "records": []})
        changes = self.external_upgrader(skill_name, s.get("records", []))
        return self._build_template(skill_name, s["level"], changes)

    def level_name(self, level: int) -> str:
        names = ["novice", "apprentice", "adept", "expert", "master"]
        return names[min(max(level, 1) - 1, 4)]

    def _build_contract(self, skill_name: str, level: int) -> Dict[str, Any]:
        """Контракт, растущий с уровнем (авторитет, гейты, аудит, лимиты)."""
        return {
            "skill": skill_name,
            "level": level,
            "rank": self.level_name(level),
            "authority": "increases with level" if level < 3 else "high authority",
            "quality_gates": ["citation", "physics", "style", "logic"][:min(level, 4)],
            "external_audit_required": level >= 3,
            "auto_approval": level >= 4,           # эксперт может сам утверждать
            "budget_multiplier": min(1.0 + 0.25 * (level - 1), 2.0),  # больше ресурсов
            "legacy_consult": level >= 2,          # уровень 2+: смотреть legacy
            "subagent_delegation": level >= 4,     # мастер делегирует суб-агентам
        }

    def _build_template(self, skill_name: str, level: int, changes: List[str]) -> Dict[str, Any]:
        """Шаблон, усложняющийся с уровнем."""
        gates = ", ".join(["citation", "physics", "style", "logic"][:min(level, 4)])
        delegation = ("\nДелегируй суб-агентам рутинные подзадачи." if level >= 4 else "")
        legacy = ("\nСверься с LegacyArchive перед началом (похожие провалы)."
                  if level >= 2 else "")
        audit = ("\nПеред сдачей — внешний аудит обязателен (level 3+)."
                 if level >= 3 else "")
        return {
            "skill": skill_name, "level": level, "rank": self.level_name(level),
            "prompt_template": (
                f"Ты используешь скил {skill_name} уровня {level} ({self.level_name(level)}).\n"
                f"Гейты: {gates}.\n"
                f"Улучшения: {', '.join(changes) if changes else 'базовая конфигурация'}.{legacy}{audit}{delegation}"),
            "version": level,
        }

    # ------------------------------------------------------ внешние (внедряемые)

    def _default_upgrader(self, skill_name: str, records: List[Dict[str, Any]]) -> List[str]:
        """Дефолтный улучшатель: анализирует временные суб-скрипты и ошибки."""
        changes = []
        temp_scripts = [r.get('temporary_script') for r in records if r.get('temporary_script')]
        if temp_scripts:
            changes.append(f"интегрировать {len(temp_scripts)} временных суб-скриптов")
        errors = [r for r in records if r.get('outcome') == 'error']
        if errors:
            changes.append(f"исправлено {len(errors)} ошибок")
        rewrites = [r for r in records if r.get('outcome') == 'rewritten']
        if rewrites:
            changes.append(f"учтено {len(rewrites)} переписываний")
        if not changes:
            changes.append("уточнение параметров по истории использования")
        return changes

    def _default_memory_writer(self, pattern: ExperiencePattern) -> None:
        """Модуляция глобальной памяти: пишем паттерн в файл памяти."""
        mem_file = self.skills_dir / 'global_memory.json'
        data = []
        if mem_file.exists():
            try:
                data = json.loads(mem_file.read_text(encoding='utf-8'))
            except Exception:
                data = []
        data.append(pattern.to_dict())
        mem_file.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding='utf-8')

    # ------------------------------------------------------ персистентность

    def _save(self) -> None:
        f = self.skills_dir / 'skills_state.json'
        f.write_text(json.dumps(self._skills, ensure_ascii=False, indent=2),
                     encoding='utf-8')

    def _load(self) -> None:
        f = self.skills_dir / 'skills_state.json'
        if f.exists():
            try:
                self._skills = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                self._skills = {}

    def skill_status(self, skill_name: str) -> Dict[str, Any]:
        s = self._skills.get(skill_name, {"level": 1, "name": "novice",
                                          "usage_count": 0, "records": []})
        return {"skill": skill_name, "level": s["level"], "name": s["name"],
                "usage_count": s["usage_count"],
                "next_threshold": SkillLevel(s["level"]).next_threshold}