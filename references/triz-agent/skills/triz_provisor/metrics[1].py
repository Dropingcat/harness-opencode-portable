"""
Детерминированные метрики Провизора.
2 из 4 метрик считаются кодом (completeness, coherence), не LLM.
"""

from typing import List, Dict, Any, Optional


def compute_completeness(
    concepts: List[Dict[str, Any]],
    target_concepts: int = 3,
) -> float:
    """
    Полнота: сколько концепций сгенерировано относительно цели.

    completeness = min(1.0, len(concepts) / target_concepts)

    Args:
        concepts: Список концепций
        target_concepts: Целевое число концепций (по умолчанию 3)

    Returns:
        float 0.0 - 1.0
    """
    if target_concepts <= 0:
        return 1.0
    return min(1.0, len(concepts) / target_concepts)


def compute_coherence(
    critique_output: Dict[str, Any],
    n_checks: int = 6,
) -> float:
    """
    Согласованность: доля пройденных проверок.

    coherence = max(0.0, 1.0 - n_issues / max(n_checks, 1))

    Args:
        critique_output: Выход Критика
        n_checks: Общее число проверок (по умолчанию 6)

    Returns:
        float 0.0 - 1.0
    """
    analyst_issues = critique_output.get("analyst_issues", [])
    designer_issues = critique_output.get("designer_issues", [])
    n_issues = len(analyst_issues) + len(designer_issues)

    return max(0.0, 1.0 - (n_issues / max(n_checks, 1)))


def compute_overall(
    completeness: float,
    coherence: float,
    feasibility: float,
    novelty: float,
) -> float:
    """
    Общая оценка (0.0 - 10.0).

    overall = (completeness + coherence + feasibility + novelty) / 4 * 10

    Args:
        completeness: 0.0 - 1.0
        coherence: 0.0 - 1.0
        feasibility: 0.0 - 1.0 (от LLM)
        novelty: 0.0 - 1.0 (от LLM)

    Returns:
        float 0.0 - 10.0
    """
    return (completeness + coherence + feasibility + novelty) / 4.0 * 10.0


def compute_improvement_delta(
    current_overall: float,
    previous_overall: Optional[float],
) -> float:
    """
    Улучшение по сравнению с предыдущей итерацией.

    Args:
        current_overall: Текущая оценка
        previous_overall: Предыдущая оценка (None если первая итерация)

    Returns:
        float (может быть отрицательным)
    """
    if previous_overall is None:
        return 0.0
    return current_overall - previous_overall


def detect_plateau(
    history: List[Dict[str, Any]],
    threshold: float,
    patience: int,
) -> bool:
    """
    Обнаружение плато качества.

    Args:
        history: История оценок (с полем 'overall')
        threshold: Порог улучшения
        patience: Число итераций без улучшения

    Returns:
        True если плато обнаружено
    """
    if len(history) < patience + 1:
        return False

    # Проверяем последние patience дельт
    # берём patience+1 записей чтобы получить patience дельт
    relevant = history[-patience-1:] if len(history) >= patience + 1 else history
    no_improvement_count = 0

    for i in range(1, len(relevant)):
        prev_overall = relevant[i - 1].get("overall", 0)
        curr_overall = relevant[i].get("overall", 0)
        delta = curr_overall - prev_overall
        if delta < threshold:
            no_improvement_count += 1

    return no_improvement_count >= patience