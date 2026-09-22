"""
JSON-схемы Провизора.
Содержит ProvisorInput, Evaluation, StopDecision, IterationRecord, FinalRecommendation.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
import json


class StopDecision(Enum):
    """Решение о продолжении/остановке"""
    CONTINUE = "continue"
    STOP_QUALITY = "stop_quality"       # Достигнут порог качества
    STOP_PLATEAU = "stop_plateau"       # Плато качества
    STOP_LIMIT = "stop_limit"           # Достигнут лимит итераций
    STOP_USER = "stop_user"             # Решение пользователя
    STOP_CONFIDENCE = "stop_confidence" # Достигнута стат. значимость


@dataclass
class Evaluation:
    """Оценка итерации"""
    iteration: int
    completeness: float       # 0.0 - 1.0 (детерминированная)
    coherence: float          # 0.0 - 1.0 (детерминированная)
    feasibility: float        # 0.0 - 1.0 (LLM)
    novelty: float            # 0.0 - 1.0 (LLM)
    overall: float            # 0.0 - 10.0
    improvement_delta: float  # Изменение по сравнению с прошлой итерацией
    comments: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Evaluation':
        return cls(**data)


@dataclass
class IterationRecord:
    """Запись одной итерации"""
    iteration: int
    generator_output: Dict[str, Any]
    critique_output: Dict[str, Any]
    evaluation: Evaluation
    stop_decision: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["evaluation"] = self.evaluation.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IterationRecord':
        evaluation = Evaluation.from_dict(data["evaluation"])
        return cls(
            iteration=data["iteration"],
            generator_output=data["generator_output"],
            critique_output=data["critique_output"],
            evaluation=evaluation,
            stop_decision=data.get("stop_decision"),
        )


@dataclass
class ProvisorInput:
    """Входные данные для Провизора"""
    task_id: str
    task_query: str
    context: Dict[str, Any]
    mode: str
    triz_memory: Dict[str, Any]
    ariz_memory: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'ProvisorInput':
        return cls(**json.loads(json_str))


@dataclass
class FinalRecommendation:
    """Финальная рекомендация Провизора"""
    task_id: str
    total_iterations: int
    mode: str

    # Рекомендуемая концепция
    recommended_concept: Dict[str, Any]
    justification: List[str] = field(default_factory=list)

    # Запасные варианты
    fallback_concepts: List[Dict[str, Any]] = field(default_factory=list)

    # Риски
    risks: List[Dict[str, Any]] = field(default_factory=list)

    # Финальные метрики
    final_evaluation: Optional[Evaluation] = None
    stop_reason: str = ""

    # Метаданные
    tokens_in: int = 0
    tokens_out: int = 0
    execution_time_sec: float = 0.0

    def to_json(self) -> str:
        data = asdict(self)
        if self.final_evaluation:
            data["final_evaluation"] = self.final_evaluation.to_dict()
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'FinalRecommendation':
        data = json.loads(json_str)
        if data.get("final_evaluation"):
            data["final_evaluation"] = Evaluation.from_dict(data["final_evaluation"])
        return cls(**data)