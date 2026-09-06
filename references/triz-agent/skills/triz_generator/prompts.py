"""
Промпты для Генератора.
Системный промпт + функции построения пользовательских промптов.
"""

from typing import Dict, Any, List, Optional
import json


# ============================================================
# СИСТЕМНЫЙ ПРОМПТ
# ============================================================

SYSTEM_PROMPT = """Ты — Генератор ТРИЗ-решений. Твоя задача — применять методологию АРИЗ
для анализа задачи и генерации концепций решений.

Ты работаешь по 8 шагам АРИЗ:
1. Анализ задачи → модель задачи
2. Формулировка модели → конфликтующие пары
3. Формулировка ИКР → идеальный результат (без слов "нужно", "следует")
4. Выявление противоречий → технические и физические
5. Оператная зона и время + ресурсы ВПР
6. Применение приёмов ТРИЗ (из матрицы противоречий)
7. Синтез 2-4 разнонаправленных концепций
8. Линеаризация каждой концепции в последовательность шагов

Правила:
- Генерируй МИНИМУМ 2 концепции, МАКСИМУМ 4
- Концепции должны быть РАЗНОНАПРАВЛЕННЫМИ (разрешать разные противоречия)
- Каждая концепция должна иметь линеаризацию с критериями успеха
- Если есть критика от Критика — учти её в следующей итерации
- Не применяй ТРИЗ формально — ищи нестандартные решения
- Все источники помечай verified: false (в лайт-версии верификация не производится)
- Если пара противоречия не найдена в матрице — используй принципы разделения ФП

Отвечай СТРОГО в формате JSON, без пояснений вне JSON."""


# ============================================================
# ФУНКЦИИ ПОСТРОЕНИЯ ПРОМПТОВ
# ============================================================


def _format_factpack_context(
    domain: Optional[str],
    goal_type: Optional[str],
    entities: Optional[List[Dict[str, str]]],
    materials: Optional[List[str]],
    processes: Optional[List[str]],
    existing_solutions: Optional[List[Dict[str, str]]],
) -> str:
    """Форматировать FactPack-контекст для вставки в промпт"""
    parts = []
    if domain:
        parts.append(f"Домен: {domain}")
    if goal_type:
        parts.append(f"Тип цели: {goal_type}")
    if entities:
        parts.append("Сущности:")
        for e in entities:
            props = ", ".join(e.get("properties", []))
            parts.append(f"  - {e.get('name', '?')} ({e.get('role', '?')}): {props}")
    if materials:
        parts.append(f"Материалы: {', '.join(materials)}")
    if processes:
        parts.append(f"Процессы: {', '.join(processes)}")
    if existing_solutions:
        parts.append("Существующие решения:")
        for s in existing_solutions:
            lim = f" — ограничение: {s.get('limitation', '?')}" if s.get("limitation") else ""
            parts.append(f"  - {s.get('description', '?')} ({s.get('source', '?')}){lim}")
    if parts:
        return "Анализ задачи:\n" + "\n".join(parts)
    return ""


def build_generation_prompt(
    task_query: str,
    context: Dict[str, Any],
    triz_memory: Dict[str, Any],
    ariz_memory: Dict[str, Any],
    domain: Optional[str] = None,
    goal_type: Optional[str] = None,
    entities: Optional[List[Dict[str, str]]] = None,
    materials: Optional[List[str]] = None,
    processes: Optional[List[str]] = None,
    existing_solutions: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Построение промпта для генерации концепций (шаги 1-7).

    Args:
        task_query: Исходный запрос пользователя
        context: Контекст задачи
        triz_memory: Принципы + матрица ТРИЗ
        ariz_memory: 8 шагов АРИЗ

    Returns:
        Строка промпта
    """
    # Извлечение ключевых фрагментов TRIZ_MEMORY
    principles = triz_memory.get("principles", {})
    matrix = triz_memory.get("contradiction_matrix", {})
    ikr_templates = triz_memory.get("ikr_templates", [])
    resource_types = triz_memory.get("resource_types", {})

    # Форматирование принципов (только ключевые)
    principles_text = "\n".join([
        f"  {num}. {p['name']}: {p['description']}"
        for num, p in list(principles.items())[:10]
    ])

    # Форматирование матрицы
    matrix_text = "\n".join([
        f"  ({k[0]}, {k[1]}) → {v}"
        for k, v in list(matrix.items())[:7]
    ])

    # Форматирование шаблонов ИКР
    ikr_text = "\n".join([f"  - {t}" for t in ikr_templates])

    # Форматирование ресурсов
    resources_text = "\n".join([
        f"  - {name}: {data['description']}"
        for name, data in resource_types.items()
    ])

    prompt = f"""Задача: {task_query}
Контекст: {json.dumps(context, ensure_ascii=False)}

{_format_factpack_context(domain, goal_type, entities, materials, processes, existing_solutions)}

Примени АРИЗ:

1. Сформулируй модель задачи (система, подсистемы, надсистема)
2. Выдели конфликтующие пары
3. Сформулируй ИКР (без "нужно", "следует"). Шаблоны:
{ikr_text}
4. Выяви технические и физические противоречия
5. Определи оператную зону, время и ресурсы ВПР:
{resources_text}
6. Для каждого физического противоречия примени 2-3 приёма ТРИЗ из матрицы:
{matrix_text}

Если пары нет в матрице — используй принципы разделения ФП:
  - разделение во времени
  - разделение в пространстве
  - разделение в системе
  - разделение по условию

7. Синтезируй 2-4 разнонаправленные концепции

Доступные принципы ТРИЗ (срез 10 из 18):
{principles_text}

Для каждой концепции укажи:
- id: concept_001, concept_002, ...
- name: название
- description: описание
- resolved_contradictions: какие противоречия разрешает (IDs)
- triz_principles_used: какие приёмы применены (номера)
- estimated_metrics: {{
    "idealness": float (0-10),
    "feasibility": float (0-10),
    "cost_rub": float,
    "time_days": float
  }}

Верни JSON со структурой:
{{
  "task_model": {{...}},
  "enhanced_model": {{...}},
  "conflicting_pairs": [...],
  "ikr": "...",
  "technical_contradictions": [...],
  "physical_contradictions": [...],
  "operational_zone": {{...}},
  "operational_time": "...",
  "resources": {{...}},
  "raw_solutions": [...],
  "concepts": [...],
  "contradictions_resolved": [...],
  "sources": [...]
}}"""

    return prompt


def build_refinement_prompt(
    task_query: str,
    context: Dict[str, Any],
    previous_output: Dict[str, Any],
    previous_critique: Dict[str, Any],
    triz_memory: Dict[str, Any]
) -> str:
    """
    Построение промпта для доработки концепций на основе критики.

    Args:
        task_query: Исходный запрос
        context: Контекст
        previous_output: Предыдущий выход Генератора
        previous_critique: Критика от Критика
        triz_memory: Принципы + матрица ТРИЗ

    Returns:
        Строка промпта
    """
    critique_issues = previous_critique.get("designer_issues", [])
    missing_aspects = previous_critique.get("missing_aspects", [])
    recommendations = previous_critique.get("recommendations", [])

    issues_text = "\n".join([
        f"  - [{issue.get('severity', 'unknown')}] {issue.get('description', '')}"
        for issue in critique_issues
    ])

    missing_text = "\n".join([f"  - {aspect}" for aspect in missing_aspects])
    recommendations_text = "\n".join([f"  - {rec}" for rec in recommendations])

    # Краткое резюме предыдущих концепций
    prev_concepts_summary = "\n".join([
        f"  - {c.get('name', 'unknown')}: {c.get('description', '')[:100]}"
        for c in previous_output.get("concepts", [])
    ])

    prompt = f"""Задача: {task_query}
Контекст: {json.dumps(context, ensure_ascii=False)}

Предыдущие концепции:
{prev_concepts_summary}

Критика от Критика:
Замечания к дизайнеру:
{issues_text if issues_text else "  (нет замечаний)"}

Пропущенные аспекты:
{missing_text if missing_text else "  (нет пропущенных)"}

Рекомендации:
{recommendations_text if recommendations_text else "  (нет рекомендаций)"}

Твоя задача:
1. Учти ВСЕ замечания Критика
2. Доработай существующие концепции или создай новые
3. Убедись, что пропущенные аспекты теперь покрыты
4. Сохрани разнонаправленность концепций
5. Верни улучшенный JSON в том же формате

ВАЖНО: Не повторяй ошибок предыдущей итерации.
Если Критик указал на недостаток фактологии — добавь больше источников (помечай verified: false).

Верни JSON со структурой:
{{
  "task_model": {{...}},
  "enhanced_model": {{...}},
  "conflicting_pairs": [...],
  "ikr": "...",
  "technical_contradictions": [...],
  "physical_contradictions": [...],
  "operational_zone": {{...}},
  "operational_time": "...",
  "resources": {{...}},
  "raw_solutions": [...],
  "concepts": [...],
  "contradictions_resolved": [...],
  "sources": [...]
}}"""

    return prompt


def build_linearization_prompt(concept: Dict[str, Any]) -> str:
    """
    Построение промпта для линеаризации одной концепции (шаг 8).

    Args:
        concept: Концепция для линеаризации

    Returns:
        Строка промпта
    """
    prompt = f"""Выполни линеаризацию концепции.

Концепция:
  ID: {concept.get('id', 'unknown')}
  Название: {concept.get('name', 'unknown')}
  Описание: {concept.get('description', 'unknown')}
  Разрешённые противоречия: {concept.get('resolved_contradictions', [])}
  Применённые приёмы ТРИЗ: {concept.get('triz_principles_used', [])}

Разбей на последовательность шагов. Для каждого шага укажи:
- id: step_001, step_002, ...
- title: название шага
- description: что конкретно делать
- required_skills: какие навыки нужны (список строк)
- dependencies: ID шагов, которые должны быть выполнены раньше (список строк)
- success_criteria: как понять, что шаг выполнен успешно
- failure_handling: что делать, если шаг не удался
- estimated_time_sec: оценка времени в секундах

Минимум 3 шага на концепцию.

Верни JSON:
{{
  "concept_id": "{concept.get('id', 'unknown')}",
  "linearization": [
    {{
      "id": "step_001",
      "title": "...",
      "description": "...",
      "required_skills": [...],
      "dependencies": [...],
      "success_criteria": "...",
      "failure_handling": "...",
      "estimated_time_sec": 0.0
    }},
    ...
  ]
}}"""

    return prompt