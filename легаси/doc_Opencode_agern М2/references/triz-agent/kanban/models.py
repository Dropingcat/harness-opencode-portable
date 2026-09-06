"""
Модели данных для канбан-доски.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime


class TaskStatus(Enum):
    """Статусы задачи в канбане"""
    QUEUE = "queue"
    GENERATOR = "generator"
    CRITIC = "critic"
    REWORK = "rework"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    """Задача в канбане"""
    id: str
    query: str
    context: Dict[str, Any]
    status: TaskStatus = TaskStatus.QUEUE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    current_iteration: int = 0
    max_iterations: int = 3
    mode: str = "sufficiency"
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    fact_pack: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "context": self.context,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "mode": self.mode,
            "iterations": self.iterations,
            "result": self.result,
            "error": self.error,
            "fact_pack": self.fact_pack,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        return cls(
            id=data["id"],
            query=data["query"],
            context=data["context"],
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            current_iteration=data["current_iteration"],
            max_iterations=data["max_iterations"],
            mode=data["mode"],
            iterations=data["iterations"],
            result=data["result"],
            error=data["error"],
            fact_pack=data.get("fact_pack"),
        )

    def update_status(self, new_status: TaskStatus):
        self.status = new_status
        self.updated_at = datetime.now()