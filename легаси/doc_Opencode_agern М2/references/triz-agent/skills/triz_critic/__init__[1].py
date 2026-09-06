"""
Навык Критика (triz-critic).
Проверяет выход Генератора по чек-листу из 6 пунктов.
"""

from .schemas import (
    CriticInput,
    CriticReport,
    Issue,
    CheckResult,
    Severity,
    AffectedRole,
    CHECKLIST_ITEMS,
)
from .handler import (
    critique_generator_output,
    build_critic_input,
)
from .validator import (
    has_solution_verbs,
    validate_critic_output,
)

__all__ = [
    "CriticInput",
    "CriticReport",
    "Issue",
    "CheckResult",
    "Severity",
    "AffectedRole",
    "CHECKLIST_ITEMS",
    "critique_generator_output",
    "build_critic_input",
    "has_solution_verbs",
    "validate_critic_output",
]