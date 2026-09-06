"""
Навык Провизора (triz-provisor) -- супервизор ТРИЗ-агента.
Управляет циклом, хранит память, принимает решения.
"""

from .schemas import (
    ProvisorInput,
    Evaluation,
    StopDecision,
    FinalRecommendation,
    IterationRecord,
)
from .metrics import (
    compute_completeness,
    compute_coherence,
    compute_overall,
    compute_improvement_delta,
)
from .rule_based import (
    rule_based_stop_decision,
    rule_based_evaluate,
    select_best_concept,
)
from .prompts import (
    SYSTEM_PROMPT,
    build_evaluation_prompt,
    build_synthesis_prompt,
)
from .handler import (
    evaluate_iteration,
    decide_continue,
    synthesize_final,
    run_triz_cycle,
)

__all__ = [
    # Schemas
    'ProvisorInput',
    'Evaluation',
    'StopDecision',
    'FinalRecommendation',
    'IterationRecord',
    # Metrics
    'compute_completeness',
    'compute_coherence',
    'compute_overall',
    'compute_improvement_delta',
    # Rule-based
    'rule_based_stop_decision',
    'rule_based_evaluate',
    'select_best_concept',
    # Prompts
    'SYSTEM_PROMPT',
    'build_evaluation_prompt',
    'build_synthesis_prompt',
    # Handler
    'evaluate_iteration',
    'decide_continue',
    'synthesize_final',
    'run_triz_cycle',
]