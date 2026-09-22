#!/usr/bin/env python3
"""Pydantic v2-схемы состояния Writer Cell.

Дублирует структуру EMPTY_STATE из state_machine.py и предоставляет
validate_pydantic() как альтернативу state_machine.validate().
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

PHASES = [
    "AWAITING_ANSWERS",
    "PLANNING",
    "WRITING",
    "WAVE_A",
    "REVISING",
    "WAVE_B",
    "CONSISTENCY",
    "REVERIFY",
    "REGRESSION",
    "DONE",
]

FINAL_PHASES = {"DONE", "FINAL"}


class MetaModel(BaseModel):
    version: int = Field(default=1, ge=1, le=1)
    discussion_id: str = ""
    document: str = ""
    created_at: str = ""
    updated_at: str = ""
    profile: str = "resercher"


class CycleModel(BaseModel):
    iteration: int = Field(default=0, ge=0)
    phase: str = "AWAITING_ANSWERS"
    total_iterations_max: int = 3
    stop_reason: str | None = None

    @field_validator("phase")
    @classmethod
    def _check_phase(cls, v: str) -> str:
        if v not in PHASES and v not in FINAL_PHASES:
            raise ValueError(
                f"unknown phase: {v}; expected one of {PHASES + sorted(FINAL_PHASES)}"
            )
        return v


class TextVersionsModel(BaseModel):
    original: str = ""
    current: str = ""
    history: list = Field(default_factory=list)


class BudgetModel(BaseModel):
    spent_tokens: int = Field(default=0, ge=0)
    spent_cost_rub: float = Field(default=0.0, ge=0)
    max_cost_rub: float = Field(default=20.0, ge=0)
    per_iteration: dict = Field(default_factory=dict)


class WriterStateModel(BaseModel):
    model_config = {"populate_by_name": True}

    meta: MetaModel = Field(default_factory=MetaModel, alias="_meta")
    cycle: CycleModel = Field(default_factory=CycleModel)
    text_versions: TextVersionsModel = Field(default_factory=TextVersionsModel)
    questions: dict = Field(default_factory=dict)
    patches: dict = Field(default_factory=dict)
    verdicts_flow: dict = Field(default_factory=dict)
    regression: dict = Field(default_factory=dict)
    budget: BudgetModel = Field(default_factory=BudgetModel)
    checkpoints: list = Field(default_factory=list)


def validate_pydantic(state: dict) -> list[str]:
    """Валидирует dict-стейт через WriterStateModel.

    Возвращает список читаемых ошибок; пустой список = стейт валиден.
    """
    if not isinstance(state, dict):
        return [f"state must be a dict, got {type(state).__name__}"]
    try:
        WriterStateModel.model_validate(state)
    except Exception as exc:  # ValidationError
        msgs = []
        for err in getattr(exc, "errors", lambda: [])():
            loc = ".".join(str(part) for part in err.get("loc", ()))
            ctx = err.get("ctx")
            extra = ""
            if ctx and "error" in ctx:
                extra = f" ({ctx['error']})"
            msgs.append(f"{loc}: {err.get('msg', 'invalid')}{extra}")
        return msgs
    return []
