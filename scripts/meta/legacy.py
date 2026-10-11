# -*- coding: utf-8 -*-
"""
legacy.py — V6 Negative Knowledge Archive.

Legacy — активный фильтр, не кладбище. Накопление опыта:
провалы кристаллизуются в ExperiencePattern, уроки — в LessonLearned.
Семантический поиск по эмбеддингам.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PatternCategory(str, Enum):
    FAILURE = "failure"
    SUCCESS = "success"
    ANTI_PATTERN = "anti_pattern"
    BEST_PRACTICE = "best_practice"
    SKILL_COMBINATION = "skill_combination"


class LessonLearned:
    """Урок, извлечённый из провала/смерти."""

    __slots__ = ("lesson_id", "error_pattern", "corrective_rule", "target_component",
                 "priority", "source_death_id", "source_branch_id", "validated",
                 "times_applied", "success_count")

    def __init__(self, error_pattern: str, corrective_rule: str,
                 target_component: str = "policy", priority: int = 3,
                 source_death_id: Optional[str] = None,
                 source_branch_id: Optional[str] = None) -> None:
        self.lesson_id = str(uuid.uuid4())
        self.error_pattern = error_pattern
        self.corrective_rule = corrective_rule
        self.target_component = target_component
        self.priority = priority
        self.source_death_id = source_death_id
        self.source_branch_id = source_branch_id
        self.validated = False
        self.times_applied = 0
        self.success_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lesson_id": self.lesson_id, "error_pattern": self.error_pattern,
            "corrective_rule": self.corrective_rule, "target_component": self.target_component,
            "priority": self.priority, "validated": self.validated,
            "times_applied": self.times_applied,
        }


class ExperiencePattern:
    """Узел накопления опыта: всё, что система узнала, кристаллизуется сюда."""

    __slots__ = ("pattern_id", "category", "title", "description", "source_lesson_ids",
                 "involved_skills", "involved_agents", "example_artifact_ids",
                 "times_applied", "success_count", "failure_count", "embedding",
                 "tags", "created_at", "last_applied_at")

    def __init__(self, category: PatternCategory, title: str, description: str,
                 source_lesson_ids: Optional[List[str]] = None,
                 involved_skills: Optional[List[str]] = None,
                 involved_agents: Optional[List[str]] = None,
                 tags: Optional[List[str]] = None) -> None:
        self.pattern_id = str(uuid.uuid4())
        self.category = category
        self.title = title
        self.description = description
        self.source_lesson_ids = source_lesson_ids or []
        self.involved_skills = involved_skills or []
        self.involved_agents = involved_agents or []
        self.example_artifact_ids: List[str] = []
        self.times_applied = 0
        self.success_count = 0
        self.failure_count = 0
        self.embedding: Optional[List[float]] = None
        self.tags = tags or []
        self.created_at = datetime.now().isoformat()
        self.last_applied_at: Optional[str] = None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def record_outcome(self, success: bool) -> None:
        self.times_applied += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.last_applied_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "category": self.category.value if hasattr(self.category, 'value') else str(self.category),
            "title": self.title, "description": self.description,
            "involved_skills": self.involved_skills, "involved_agents": self.involved_agents,
            "times_applied": self.times_applied, "success_count": self.success_count,
            "failure_count": self.failure_count, "success_rate": self.success_rate,
            "tags": self.tags, "created_at": self.created_at,
        }


class LegacyRecord:
    """Запись в архиве опыта (ветка + AAR + смерть + паттерны + уроки)."""

    __slots__ = ("record_id", "branch", "aar", "death", "failure_patterns", "lessons",
                 "parent_state_version", "hypothesis_tested", "rejection_reason",
                 "max_achieved_metrics", "embedding", "tags", "relevance_ttl",
                 "cycles_since_creation", "times_consulted", "last_consulted_at",
                 "created_at")

    def __init__(self, parent_state_version: str, hypothesis_tested: str,
                 rejection_reason: str = "unknown",
                 max_achieved_metrics: Optional[Dict[str, float]] = None,
                 tags: Optional[List[str]] = None) -> None:
        self.record_id = str(uuid.uuid4())
        self.branch = None
        self.aar = None
        self.death = None
        self.failure_patterns: List[ExperiencePattern] = []
        self.lessons: List[LessonLearned] = []
        self.parent_state_version = parent_state_version
        self.hypothesis_tested = hypothesis_tested
        self.rejection_reason = rejection_reason
        self.max_achieved_metrics = max_achieved_metrics or {}
        self.embedding: Optional[List[float]] = None
        self.tags = tags or []
        self.relevance_ttl = 50
        self.cycles_since_creation = 0
        self.times_consulted = 0
        self.last_consulted_at: Optional[str] = None
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id, "parent_state_version": self.parent_state_version,
            "hypothesis_tested": self.hypothesis_tested[:80],
            "rejection_reason": self.rejection_reason, "tags": self.tags,
            "times_consulted": self.times_consulted, "relevance_ttl": self.relevance_ttl,
        }


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class LegacyArchive:
    """Активный архив опыта: поиск похожих провалов, паттернов, комбинаций скилов."""

    def __init__(self, embed_fn: Optional[Any] = None) -> None:
        self.records: List[LegacyRecord] = []
        self.patterns: Dict[str, ExperiencePattern] = {}
        self.lessons: Dict[str, LessonLearned] = {}
        self._embed = embed_fn  # callable(text) -> List[float]

    def archive(self, record: LegacyRecord) -> None:
        """Архивация записи (ветка/AAR/смерть)."""
        self.records.append(record)
        for lesson in record.lessons:
            self.lessons[lesson.lesson_id] = lesson
        for pattern in record.failure_patterns:
            self.patterns[pattern.pattern_id] = pattern

    def register_pattern(self, pattern: ExperiencePattern) -> str:
        self.patterns[pattern.pattern_id] = pattern
        return pattern.pattern_id

    def search_similar_failures(self, new_hypothesis: str,
                                threshold: float = 0.85) -> List[LegacyRecord]:
        """Поиск похожих провалов (не наступать на грабли)."""
        if not self._embed or not self.records:
            return []
        query_emb = self._embed(new_hypothesis)
        results = []
        for rec in self.records:
            if rec.embedding:
                sim = cosine_similarity(query_emb, rec.embedding)
                if sim >= threshold:
                    rec.times_consulted += 1
                    rec.last_consulted_at = datetime.now().isoformat()
                    results.append((sim, rec))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in results]

    def search_patterns(self, query: str, category: Optional[PatternCategory] = None,
                        top_k: int = 5) -> List[ExperiencePattern]:
        """Поиск паттернов опыта."""
        if not self._embed:
            return list(self.patterns.values())[:top_k]
        query_emb = self._embed(query)
        candidates = list(self.patterns.values())
        if category:
            candidates = [p for p in candidates if p.category == category]
        scored = []
        for p in candidates:
            if p.embedding:
                scored.append((cosine_similarity(query_emb, p.embedding), p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:top_k]]

    def find_successful_skill_combinations(self, task_type: str) -> List[ExperiencePattern]:
        return self.search_patterns(task_type, PatternCategory.SKILL_COMBINATION, top_k=3)

    def garbage_collect(self) -> int:
        """TTL: устаревшие записи удаляются/продлеваются."""
        kept = []
        for rec in self.records:
            rec.cycles_since_creation += 1
            if rec.cycles_since_creation <= rec.relevance_ttl:
                kept.append(rec)
            elif rec.times_consulted > 5:
                rec.relevance_ttl += 20  # важные живут дольше
                kept.append(rec)
        removed = len(self.records) - len(kept)
        self.records = kept
        return removed