# -*- coding: utf-8 -*-
"""
branch.py — V4 Experiment Infrastructure.

SkillInvocation, Artifact, ExperimentRun, ExperimentBranch, BranchStatus.
Каждая ветка = Parent + Delta + Trace + Metrics + Artifacts.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class BranchStatus(str, Enum):
    EXPERIMENT = "experiment"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class SkillInvocation:
    """Запись использования скила/инструмента/агента (история вызовов)."""

    __slots__ = ("invocation_id", "skill_name", "agent_role", "input_params",
                 "output_artifact_id", "duration_ms", "tokens_used", "cost_usd",
                 "success", "error_message", "timestamp")

    def __init__(self, skill_name: str, agent_role: Optional[str] = None,
                 input_params: Optional[Dict[str, Any]] = None) -> None:
        self.invocation_id = str(uuid.uuid4())
        self.skill_name = skill_name
        self.agent_role = agent_role
        self.input_params = input_params or {}
        self.output_artifact_id = None
        self.duration_ms = 0
        self.tokens_used = 0
        self.cost_usd = 0.0
        self.success = True
        self.error_message = None
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invocation_id": self.invocation_id, "skill_name": self.skill_name,
            "agent_role": self.agent_role, "input_params": self.input_params,
            "output_artifact_id": self.output_artifact_id, "success": self.success,
            "error_message": self.error_message, "timestamp": self.timestamp,
        }


class Artifact:
    """Артефакт — результат работы (текст, данные, код)."""

    __slots__ = ("artifact_id", "artifact_type", "content", "source_invocation_id",
                 "source_branch_id", "embedding", "created_at", "tags")

    def __init__(self, artifact_type: str, content: Any,
                 source_branch_id: Optional[str] = None,
                 tags: Optional[List[str]] = None) -> None:
        self.artifact_id = str(uuid.uuid4())
        self.artifact_type = artifact_type
        self.content = content
        self.source_invocation_id = None
        self.source_branch_id = source_branch_id
        self.embedding = None
        self.created_at = datetime.now().isoformat()
        self.tags = tags or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id, "artifact_type": self.artifact_type,
            "source_branch_id": self.source_branch_id, "tags": self.tags,
            "created_at": self.created_at,
        }


class ExperimentRun:
    """Один прогон (сон) внутри ветки."""

    __slots__ = ("run_id", "branch_id", "candidate_id", "input_task", "llm_output",
                 "skill_invocations", "evaluation_metrics", "health_impact",
                 "isolation_params", "timestamp")

    def __init__(self, branch_id: str, candidate_id: str, input_task: str) -> None:
        self.run_id = str(uuid.uuid4())
        self.branch_id = branch_id
        self.candidate_id = candidate_id
        self.input_task = input_task
        self.llm_output = None
        self.skill_invocations: List[SkillInvocation] = []
        self.evaluation_metrics: Dict[str, float] = {}
        self.health_impact = 0.0
        self.isolation_params: Dict[str, Any] = {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id, "branch_id": self.branch_id,
            "input_task": self.input_task[:100], "evaluation_metrics": self.evaluation_metrics,
            "health_impact": self.health_impact,
            "skill_invocations": [i.to_dict() for i in self.skill_invocations],
        }


class ExperimentBranch:
    """Ветка = Parent + Delta + Trace + Metrics + Artifacts."""

    __slots__ = ("branch_id", "parent_version_id", "delta", "status", "runs",
                 "artifacts", "aggregated_metrics", "statistical_significance",
                 "lessons_extracted", "created_at", "closed_at")

    def __init__(self, parent_version_id: str, delta: Dict[str, Any]) -> None:
        self.branch_id = str(uuid.uuid4())
        self.parent_version_id = parent_version_id
        self.delta = delta
        self.status = BranchStatus.EXPERIMENT
        self.runs: List[ExperimentRun] = []
        self.artifacts: List[Artifact] = []
        self.aggregated_metrics: Dict[str, float] = {}
        self.statistical_significance = 0.0
        self.lessons_extracted: List[str] = []
        self.created_at = datetime.now().isoformat()
        self.closed_at = None

    def add_run(self, run: ExperimentRun) -> None:
        self.runs.append(run)

    def add_artifact(self, artifact: Artifact) -> None:
        self.artifacts.append(artifact)

    def close(self, status: BranchStatus) -> None:
        self.status = status
        self.closed_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id, "parent_version_id": self.parent_version_id,
            "delta": self.delta, "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "runs": len(self.runs), "artifacts": len(self.artifacts),
            "aggregated_metrics": self.aggregated_metrics,
            "statistical_significance": self.statistical_significance,
            "created_at": self.created_at, "closed_at": self.closed_at,
        }