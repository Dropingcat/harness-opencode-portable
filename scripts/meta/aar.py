# -*- coding: utf-8 -*-
"""
aar.py — V2/V6: DeathCertificate, AfterActionReport, CandidateState.

После каждой смерти: свидетельство → разбор полётов (AAR) → уроки → паттерны.
CandidateState: кандидатное состояние S' = Parent + Delta.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class CandidateState:
    """Кандидатное состояние S' (V2)."""

    __slots__ = ("candidate_id", "parent_version_id", "delta", "projected_snapshot")

    def __init__(self, parent_version_id: str, delta: Dict[str, Any],
                 projected_snapshot: Optional[Any] = None) -> None:
        self.candidate_id = str(uuid.uuid4())
        self.parent_version_id = parent_version_id
        self.delta = delta
        self.projected_snapshot = projected_snapshot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_version_id": self.parent_version_id,
            "delta": self.delta,
        }


class DeathCertificate:
    """Свидетельство о смерти ветки (V2)."""

    __slots__ = ("death_id", "branch_id", "dream_run_id", "timestamp", "fatal_signals",
                 "hp_at_death", "lives_lost", "state_before_death", "task_being_attempted",
                 "text_that_killed", "death_pattern", "root_cause_hypothesis")

    def __init__(self, branch_id: str, death_pattern: str,
                 fatal_signals: Optional[List[Any]] = None,
                 hp_at_death: float = 0.0, lives_lost: int = 1,
                 state_before_death: str = "", task_being_attempted: str = "",
                 text_that_killed: Optional[str] = None,
                 dream_run_id: Optional[str] = None,
                 root_cause_hypothesis: Optional[str] = None) -> None:
        self.death_id = str(uuid.uuid4())
        self.branch_id = branch_id
        self.dream_run_id = dream_run_id
        self.timestamp = datetime.now().isoformat()
        self.fatal_signals = fatal_signals or []
        self.hp_at_death = hp_at_death
        self.lives_lost = lives_lost
        self.state_before_death = state_before_death
        self.task_being_attempted = task_being_attempted
        self.text_that_killed = text_that_killed
        self.death_pattern = death_pattern
        self.root_cause_hypothesis = root_cause_hypothesis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "death_id": self.death_id, "branch_id": self.branch_id,
            "death_pattern": self.death_pattern, "hp_at_death": self.hp_at_death,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "timestamp": self.timestamp,
        }


class AfterActionReport:
    """Разбор полётов после смерти (V2-TD-07 AAR)."""

    __slots__ = ("aar_id", "death", "branch_id", "root_causes", "contributing_factors",
                 "lessons_learned", "proposed_mutations", "predicted_failure_points",
                 "patterns_extracted", "nested_depth", "timestamp")

    def __init__(self, branch_id: str, death: Optional[DeathCertificate] = None) -> None:
        self.aar_id = str(uuid.uuid4())
        self.death = death
        self.branch_id = branch_id
        self.root_causes: List[str] = []
        self.contributing_factors: List[str] = []
        self.lessons_learned: List[Any] = []
        self.proposed_mutations: List[Dict[str, Any]] = []
        self.predicted_failure_points: List[str] = []
        self.patterns_extracted: List[str] = []
        self.nested_depth = 0
        self.timestamp = datetime.now().isoformat()

    def add_root_cause(self, cause: str) -> None:
        self.root_causes.append(cause)

    def add_lesson(self, lesson: Any) -> None:
        self.lessons_learned.append(lesson)

    def add_pattern(self, pattern_id: str) -> None:
        self.patterns_extracted.append(pattern_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aar_id": self.aar_id, "branch_id": self.branch_id,
            "root_causes": self.root_causes,
            "death": self.death.to_dict() if self.death else None,
            "lessons": [getattr(l, 'to_dict', lambda: str(l))() for l in self.lessons_learned],
            "patterns_extracted": self.patterns_extracted,
            "nested_depth": self.nested_depth, "timestamp": self.timestamp,
        }