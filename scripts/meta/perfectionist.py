# -*- coding: utf-8 -*-
"""
perfectionist.py — СКИЛ ПЕРФЕКЦИОНИСТА (изолированная капсула-агент).

Назначение:
  Вызывается ПО ХУКУ при признаках завершения задачи/подзадачи (не вручную).
  Изолированно оценивает выполнение и показывает, ЧТО ЯВНО ПЛОХО,
  и КОНСТРУКТИВНО мотивирует улучшить (не декоративно).

Принципы:
  - Изолирован: видит только артефакт (результат), не контекст оркестратора.
  - Запускается отдельно от оркестратора/субагентов (через роутер).
  - Подчиняется SkillMaster: каждое срабатывание → record_usage, при пороге → апгрейд.
  - Не «хвалит» — ищет реальные слабости и конкретные улучшения.

Хук: completion_hook(artifact) — вызывается при завершении задачи.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from skill_master import SkillMaster


class PerfectionistReport:
    """Отчёт перфекциониста: слабости + конструктивные улучшения."""

    __slots__ = ("report_id", "artifact_hash", "weaknesses", "improvements",
                 "verdict", "created_at")

    def __init__(self, artifact_hash: str, weaknesses: List[Dict[str, Any]],
                 improvements: List[str], verdict: str) -> None:
        import uuid
        self.report_id = str(uuid.uuid4())[:8]
        self.artifact_hash = artifact_hash
        self.weaknesses = weaknesses      # [{severity, area, what_bad, why}]
        self.improvements = improvements  # [конструктивные шаги]
        self.verdict = verdict            # needs_improvement | good | excellent
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {"report_id": self.report_id, "artifact_hash": self.artifact_hash,
                "weaknesses": self.weaknesses, "improvements": self.improvements,
                "verdict": self.verdict, "created_at": self.created_at}


class PerfectionistSkill:
    """Изолированный перфекционист. Вызывается по хуку завершения."""

    # эвристики слабостей (детерминированные, без LLM)
    HEURISTICS = [
        {"area": "completeness", "pattern": "todo", "severity": "high",
         "what": "есть незакрытые TODO/заглушки", "fix": "закрыть или явно пометить legacy"},
        {"area": "verification", "pattern": "проверить", "severity": "medium",
         "what": "нет подтверждения проверки", "fix": "добавить явный результат верификации"},
        {"area": "detail", "pattern": "и т.д.", "severity": "low",
         "what": "обрыв перечисления", "fix": "перечислить полностью или убрать"},
        {"area": "precision", "pattern": "где-то", "severity": "low",
         "what": "неопределённое указание", "fix": "заменить на конкретное"},
        {"area": "numbers", "has_digits": False, "severity": "medium",
         "what": "нет ни одной цифры (данные?)", "fix": "добавить количественные параметры"},
    ]

    def __init__(self, skills_dir: Optional[str] = None,
                 critic_fn: Optional[Callable[[Any], List[Dict[str, Any]]]] = None,
                 improvement_fn: Optional[Callable[[List[Dict[str, Any]]], List[str]]] = None,
                 skill_master: Optional[SkillMaster] = None) -> None:
        # подчиняется SkillMaster (прокачка при частом использовании)
        self.skills = skill_master or SkillMaster(skills_dir)
        # внедряемые: внешний критик (может быть LLM), генератор улучшений
        self.critic_fn = critic_fn or self._default_critic
        self.improvement_fn = improvement_fn or self._default_improvements
        self.reports: List[PerfectionistReport] = []

    # ------------------------------------------------------ хук завершения

    def completion_hook(self, artifact: Any) -> PerfectionistReport:
        """
        ВЫЗЫВАЕТСЯ АВТОМАТИЧЕСКИ при завершении задачи/подзадачи.
        Изолированно оценивает, показывает слабости, мотивирует улучшить.
        """
        text = str(artifact) if not isinstance(artifact, dict) else json.dumps(
            artifact, ensure_ascii=False)
        h = self._hash(text)

        # 1. Критика (детерминированные эвристики + внешний критик)
        weaknesses = self.critic_fn(artifact)
        # 2. Конструктивные улучшения
        improvements = self.improvement_fn(weaknesses)
        # 3. Вердикт
        verdict = self._verdict(weaknesses)
        # 4. Отчёт
        report = PerfectionistReport(h, weaknesses, improvements, verdict)
        self.reports.append(report)
        # 5. Подчинение SkillMaster: record_usage (прокачка перфекциониста)
        outcome = 'ok' if verdict == 'good' else ('error' if verdict == 'needs_improvement' else 'ok')
        self.skills.record_usage('perfectionist', outcome=outcome,
                                 notes=f'verdict={verdict}, weaknesses={len(weaknesses)}')
        return report

    # ------------------------------------------------------ критика

    def _default_critic(self, artifact: Any) -> List[Dict[str, Any]]:
        """Детерминированная критика: эвристики по тексту."""
        raw = str(artifact) if not isinstance(artifact, dict) else json.dumps(
            artifact, ensure_ascii=False)
        text = raw.lower()  # TD-178: .lower() ко всему тексту, не только dict
        has_digits = any(c.isdigit() for c in text)
        weaknesses = []
        for hk in self.HEURISTICS:
            pat = hk.get('pattern')
            if pat and pat.lower() in text:
                weaknesses.append({"severity": hk["severity"], "area": hk["area"],
                                   "what_bad": hk["what"], "why": f"найден паттерн '{pat}'"})
            elif hk.get('has_digits') is False and not has_digits and hk["area"] == 'numbers':
                weaknesses.append({"severity": hk["severity"], "area": hk["area"],
                                   "what_bad": hk["what"], "why": "артефакт без числовых данных"})
        return weaknesses

    def _default_improvements(self, weaknesses: List[Dict[str, Any]]) -> List[str]:
        """Конструктивные шаги (не декоративные)."""
        steps = []
        for w in weaknesses:
            steps.append(f"[{w['severity']}] {w['area']}: {w.get('fix', w['what_bad'])}")
        if not weaknesses:
            steps.append("проверить на внешний аудит (правило RULE_*) перед финалом")
        return steps

    def _verdict(self, weaknesses: List[Dict[str, Any]]) -> str:
        high = sum(1 for w in weaknesses if w.get('severity') == 'high')
        if high >= 2:
            return 'needs_improvement'
        if weaknesses:
            return 'needs_improvement' if high else 'good'
        return 'excellent'

    @staticmethod
    def _hash(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]

    def motivation_text(self, report: PerfectionistReport) -> str:
        """Текст мотивации (показать агенту, почему стоит улучшить)."""
        lines = [
            f"[PERFECTIONIST:{report.verdict}] {len(report.weaknesses)} слабостей найдено",
        ]
        for w in report.weaknesses:
            lines.append(f"  - [{w['severity']}] {w['area']}: {w['what_bad']}")
        lines.append("  Конструктивные улучшения (что сделать):")
        for imp in report.improvements:
            lines.append(f"    + {imp}")
        lines.append("  Цель: не декоративные правки, а реальное повышение качества "
                     "до уровня 'нечего стыдливо обходить'.")
        return "\n".join(lines)