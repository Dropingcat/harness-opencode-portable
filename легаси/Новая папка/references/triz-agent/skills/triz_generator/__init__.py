"""
Навык Генератора (Generator) — выполняет 8 шагов АРИЗ и генерирует концепции.
"""

from .schemas import (
    GeneratorInput,
    GeneratorOutput,
    Concept,
    Contradiction,
    LinearizationStep,
    Source,
    VepolModel,
)
from .prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_refinement_prompt,
    build_linearization_prompt,
)
from .handler import (
    generate_concepts,
    refine_concepts,
    run_ariz_full,
    run_ariz_two_pass,
)

__all__ = [
    # Schemas
    'GeneratorInput',
    'GeneratorOutput',
    'Concept',
    'Contradiction',
    'LinearizationStep',
    'Source',
    'VepolModel',
    # Prompts
    'SYSTEM_PROMPT',
    'build_generation_prompt',
    'build_refinement_prompt',
    'build_linearization_prompt',
    # Handler
    'generate_concepts',
    'refine_concepts',
    'run_ariz_full',
    'run_ariz_two_pass',
]