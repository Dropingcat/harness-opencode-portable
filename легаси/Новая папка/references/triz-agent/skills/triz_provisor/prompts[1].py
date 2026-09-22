"""
Промпты для Провизора.
"""

from typing import Dict, Any, List
import json

# ============================================================
# СИСТЕМНЫЙ ПРОМПТ
# ============================================================

SYSTEM_PROMPT = """Ты — Провизор ТРИЗ-процесса. Твоя задача — управлять циклом решения задачи.

Твои обязанности:
1. Оценивать качество итераций по 4 метрикам:
   - completeness (полнота) — считается кодом, НЕ оценивай
   - coherence (согласованность) — считается кодом, НЕ оценивай
   - feasibility (реализуемость) — оцени ты, 0.0-1.0
   - novelty (новизна) — оцени ты, 0.0-1.0
2. Принимать решение о продолжении или остановке
3. Синтезировать финальную рекомендацию

Правила:
- completeness и coherence уже посчитаны — не пересчитывай
- Оценивай ТОЛЬКО feasibility и novelty
- Будь объективен: не завышай оценки
- При синтезе финала — выбирай концепцию с максимальной идеальностью

Отвечай СТРОГО в формате JSON."""


# ============================================================
# ФУНКЦИИ ПОСТРОЕНИЯ ПРОМПТОВ
# ============================================================

def build_evaluation_prompt(
    task_query: str,
    iteration: int,
    generator_output: Dict[str, Any],
    critique_output: Dict[str, Any],
    completeness: float,
    coherence: float,
) -> str:
    """
    Промпт для оценки feasibility и novelty.

    completeness и coherence уже посчитаны кодом.
    """
    concepts = generator_output.get("concepts", [])
    concepts_summary = "\n".join([
        f"  - {c.get('name', '?')}: {c.get('description', '')[:100]}"
        for c in concepts
    ])

    # Краткая сводка критики
    analyst_issues = critique_output.get("analyst_issues", [])
    designer_issues = critique_output.get("designer_issues", [])
    n_issues = len(analyst_issues) + len(designer_issues)

    return f"""Оцени следующие метрики для текущей итерации.

Задача: {task_query}
Итерация: {iteration}

Концепции ({len(concepts)} шт.):
{concepts_summary}

Уже посчитано (НЕ пересчитывай):
- completeness = {completeness:.2f}
- coherence = {coherence:.2f}

Замечаний Критика: {n_issues}

Оцени (0.0-1.0):
- feasibility: насколько концепции реализуемы в заданном контексте
- novelty: насколько решения нестандартны

Верни JSON:
{{
  "feasibility": 0.0-1.0,
  "novelty": 0.0-1.0,
  "comments": "краткое обоснование"
}}"""


def build_synthesis_prompt(
    task_query: str,
    history: List[Dict[str, Any]],
) -> str:
    """Промпт для синтеза финальной рекомендации."""
    history_summary = "\n".join([
        f"Итерация {r['iteration']}: overall={r['evaluation']['overall']:.1f}, "
        f"concepts={len(r['generator_output'].get('concepts', []))}"
        for r in history
    ])

    # Все концепции из всех итераций
    all_concepts = []
    for record in history:
        for c in record.get("generator_output", {}).get("concepts", []):
            all_concepts.append(c)

    concepts_text = "\n".join([
        f"  - {c.get('id', '?')} ({c.get('name', '?')}): "
        f"idealness={c.get('estimated_metrics', {}).get('idealness', '?')}, "
        f"{c.get('description', '')[:100]}"
        for c in all_concepts
    ])

    return f"""Синтезируй финальную рекомендацию.

Задача: {task_query}

История итераций:
{history_summary}

Все концепции:
{concepts_text}

Выбери ЛУЧШУЮ концепцию (по idealness) и обоснуй выбор.
Укажи 1-2 запасных варианта.
Перечисли основные риски.

Верни JSON:
{{
  "recommended_concept": {{...}},
  "justification": ["причина 1", "причина 2"],
  "fallback_concepts": [{{...}}, {{...}}],
  "risks": [
    {{"description": "...", "probability": 0.0-1.0, "impact": 0.0-1.0, "mitigation": "..."}}
  ],
  "stop_reason": "причина остановки"
}}"""