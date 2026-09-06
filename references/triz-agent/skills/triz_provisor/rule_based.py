"""
Rule-based fallback для Провизора.
Используется при отказе LLM (circuit breaker open).
"""

from typing import List, Dict, Any, Optional

from .schemas import Evaluation, StopDecision
from .metrics import (
    compute_completeness,
    compute_coherence,
    compute_overall,
    compute_improvement_delta,
    detect_plateau,
)


def rule_based_evaluate(
    iteration: int,
    generator_output: Dict[str, Any],
    critique_output: Dict[str, Any],
    history: List[Dict[str, Any]],
    target_concepts: int = 3,
) -> Evaluation:
    """
    Rule-based оценка итерации (без LLM).

    feasibility и novelty берутся как среднее по истории.
    Если история пуста — используются значения по умолчанию (0.5).

    Args:
        iteration: Номер итерации
        generator_output: Выход Генератора
        critique_output: Выход Критика
        history: История предыдущих итераций
        target_concepts: Целевое число концепций

    Returns:
        Evaluation
    """
    # Детерминированные метрики
    concepts = generator_output.get("concepts", [])
    completeness = compute_completeness(concepts, target_concepts)
    coherence = compute_coherence(critique_output)

    # LLM-метрики: среднее по истории или default
    if history:
        feasibility = sum(
            h.get("evaluation", {}).get("feasibility", 0.5) for h in history
        ) / len(history)
        novelty = sum(
            h.get("evaluation", {}).get("novelty", 0.5) for h in history
        ) / len(history)
    else:
        feasibility = 0.5
        novelty = 0.5

    overall = compute_overall(completeness, coherence, feasibility, novelty)

    # improvement_delta
    previous_overall = None
    if history:
        previous_overall = history[-1].get("evaluation", {}).get("overall")
    improvement_delta = compute_improvement_delta(overall, previous_overall)

    return Evaluation(
        iteration=iteration,
        completeness=completeness,
        coherence=coherence,
        feasibility=feasibility,
        novelty=novelty,
        overall=overall,
        improvement_delta=improvement_delta,
        comments="Rule-based evaluation (LLM unavailable)",
    )


def rule_based_stop_decision(
    iteration: int,
    history: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> StopDecision:
    """
    Rule-based решение о продолжении/остановке.

    Формулы:
    1. if overall >= threshold -> STOP_QUALITY
    2. elif iteration >= max_iterations -> STOP_LIMIT
    3. elif plateau detected -> STOP_PLATEAU
    4. else -> CONTINUE

    Args:
        iteration: Текущая итерация (номер следующей)
        history: История итераций
        config: Конфигурация режима

    Returns:
        StopDecision
    """
    if not history:
        return StopDecision.CONTINUE

    current = history[-1].get("evaluation", {})
    overall = current.get("overall", 0.0)

    quality_threshold = config.get("quality_threshold", 7.0)
    max_iterations = config.get("max_iterations", 3)
    plateau_threshold = config.get("plateau_threshold", 0.3)
    plateau_patience = config.get("plateau_patience", 2)

    # Критерий 1: Достигнут порог качества
    if overall >= quality_threshold:
        return StopDecision.STOP_QUALITY

    # Критерий 2: Лимит итераций
    if iteration >= max_iterations:
        return StopDecision.STOP_LIMIT

    # Критерий 3: Плато
    eval_history = [
        {"overall": h.get("evaluation", {}).get("overall", 0.0)}
        for h in history
    ]
    if detect_plateau(eval_history, plateau_threshold, plateau_patience):
        return StopDecision.STOP_PLATEAU

    return StopDecision.CONTINUE


def select_best_concept(history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Выбор лучшей концепции из истории (для fallback).

    Выбирает концепцию с максимальной idealness.

    Args:
        history: История итераций

    Returns:
        Лучшая концепция или None
    """
    if not history:
        return None

    best_concept = None
    best_score = -1.0

    for record in history:
        concepts = record.get("generator_output", {}).get("concepts", [])
        for concept in concepts:
            score = concept.get("estimated_metrics", {}).get("idealness", 0.0)
            if score > best_score:
                best_score = score
                best_concept = concept

    return best_concept