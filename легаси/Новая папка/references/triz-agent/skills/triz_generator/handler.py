"""
Обработчик навыка Генератора.
Управляет вызовом LLM и обработкой результатов.
"""

import time
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Обеспечиваем доступ к модулям profile root (resilience, metrics, memory)
_profile_root = str(Path(__file__).resolve().parents[2])
if _profile_root not in sys.path:
    sys.path.insert(0, _profile_root)

from resilience import generate_seed, IdempotencyMode
from metrics import MetricsLogger, MetricEntry

from .schemas import GeneratorOutput, Concept, LinearizationStep, Source, Contradiction
from .prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_refinement_prompt,
    build_linearization_prompt,
)


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# ============================================================

def _resolve_llm(llm_client, model, role):
    """Возвращает (llm_client, model), создавая RealLLMClient если нужно."""
    if llm_client is None:
        from llm import RealLLMClient
        llm_client = RealLLMClient(role=role)
    if model is None:
        model = getattr(llm_client, 'model', 'deepseek-v4-flash')
    return llm_client, model


def _wrap_llm_client(llm_client, task_id: str, iteration: int, role: str):
    """
    Оборачивает llm_client.chat() с CircuitBreaker + retry_with_metrics.
    При отказе LLM возвращает fallback-ответ вместо падения.
    """
    try:
        from resilience.circuit_breaker import CircuitBreaker
        from resilience.retry import retry_with_metrics

        breaker = CircuitBreaker(name=f"llm_{role}")
        original_chat = llm_client.chat

        @retry_with_metrics(role=role, task_id=task_id, iteration=iteration)
        def resilient_chat(*args, **kwargs):
            if not breaker.can_execute():
                # Circuit breaker OPEN — возвращаем fallback
                return {
                    "choices": [{"message": {"content": json.dumps({
                        "error": f"LLM временно недоступен (circuit breaker OPEN, role={role})",
                        "fallback": True,
                    })}}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
            try:
                result = original_chat(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                exc_name = type(e).__name__
                if exc_name in {"TimeoutError", "APIError", "ConnectionError", "httpx.TimeoutException",
                                 "openai.APITimeoutError", "openai.APIConnectionError", "openai.RateLimitError"}:
                    breaker.record_failure(e)
                raise

        llm_client.chat = resilient_chat
    except ImportError:
        pass  # resilience модуль недоступен — работаем без защиты
    return llm_client


# ============================================================
# ГЛАВНЫЕ ФУНКЦИИ
# ============================================================


def generate_concepts(
    task_id: str,
    task_query: str,
    context: Dict[str, Any],
    iteration: int,
    mode: str,
    triz_memory: Dict[str, Any],
    ariz_memory: Dict[str, Any],
    llm_client: Any = None,
    model: str = None,
    **kwargs,
) -> GeneratorOutput:
    """
    Генерация концепций (шаги 1-7 АРИЗ).

    Args:
        task_id: UUID задачи
        task_query: Запрос пользователя
        context: Контекст задачи
        iteration: Номер итерации
        mode: sufficiency | optimality
        triz_memory: Принципы + матрица ТРИЗ
        ariz_memory: 8 шагов АРИЗ
        llm_client: Клиент LLM (должен иметь метод chat). None → RealLLMClient(role="generator")
        model: Модель для вызова. None → берётся из llm_client.model

    Returns:
        GeneratorOutput с концепциями
    """
    llm_client, model = _resolve_llm(llm_client, model, "generator")
    llm_client = _wrap_llm_client(llm_client, task_id, iteration, "generator")
    start_time = time.time()
    logger = MetricsLogger()

    # Генерация seed для идемпотентности
    idempotency_mode = IdempotencyMode.SUFFICIENCY if mode == "sufficiency" else IdempotencyMode.OPTIMALITY
    seed = generate_seed(task_id, iteration, "generator", idempotency_mode)

    # Извлекаем FactPack-параметры из kwargs, если есть
    fp_domain = kwargs.get("domain")
    fp_goal_type = kwargs.get("goal_type")
    fp_entities = kwargs.get("entities")
    fp_materials = kwargs.get("materials")
    fp_processes = kwargs.get("processes")
    fp_existing_solutions = kwargs.get("existing_solutions")

    # Построение промпта
    user_prompt = build_generation_prompt(
        task_query, context, triz_memory, ariz_memory,
        domain=fp_domain, goal_type=fp_goal_type,
        entities=fp_entities, materials=fp_materials,
        processes=fp_processes, existing_solutions=fp_existing_solutions,
    )

    # Вызов LLM
    try:
        response = llm_client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            seed=seed,
            response_format={"type": "json_object"}
        )

        tokens_in = response.get("usage", {}).get("prompt_tokens", 0)
        tokens_out = response.get("usage", {}).get("completion_tokens", 0)
        content = response.get("content", "{}")

    except Exception as e:
        # Запись ошибки в метрики
        latency = time.time() - start_time
        entry = MetricEntry.create(
            role="generator",
            latency_sec=latency,
            tokens_in=0,
            tokens_out=0,
            task_id=task_id,
            iteration=iteration,
            mode=mode,
            status="error",
            error_type=type(e).__name__
        )
        logger.log(entry)
        raise

    # Парсинг ответа с retry при JSONDecodeError
    max_attempts = 3
    for parse_attempt in range(max_attempts):
        try:
            data = json.loads(content)
            break
        except json.JSONDecodeError as e:
            if parse_attempt < max_attempts - 1:
                # Логируем и повторяем запрос
                latency = time.time() - start_time
                entry = MetricEntry.create(
                    role="generator",
                    latency_sec=latency,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    task_id=task_id,
                    iteration=iteration,
                    mode=mode,
                    status="retry",
                    error_type=f"JSONDecodeError (attempt {parse_attempt + 1})"
                )
                logger.log(entry)
                import time as _time
                _time.sleep(1)
                # Повтор запроса
                try:
                    response = llm_client.chat(
                        model=model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.2,  # lower temp for more deterministic output
                        seed=seed + parse_attempt + 1,  # new seed
                        response_format={"type": "json_object"}
                    )
                    tokens_in = response.get("usage", {}).get("prompt_tokens", 0)
                    tokens_out = response.get("usage", {}).get("completion_tokens", 0)
                    content = response.get("content", "{}")
                except Exception as retry_e:
                    latency = time.time() - start_time
                    entry = MetricEntry.create(
                        role="generator",
                        latency_sec=latency,
                        tokens_in=0,
                        tokens_out=0,
                        task_id=task_id,
                        iteration=iteration,
                        mode=mode,
                        status="error",
                        error_type=type(retry_e).__name__
                    )
                    logger.log(entry)
                    raise
            else:
                latency = time.time() - start_time
                entry = MetricEntry.create(
                    role="generator",
                    latency_sec=latency,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    task_id=task_id,
                    iteration=iteration,
                    mode=mode,
                    status="error",
                    error_type="JSONDecodeError"
                )
                logger.log(entry)
                raise ValueError(
                    f"Failed to parse LLM response as JSON after {max_attempts} attempts: {e}"
                )

    # Преобразование в GeneratorOutput
    output = _parse_generator_output(task_id, data)
    output.tokens_in = tokens_in
    output.tokens_out = tokens_out
    output.execution_time_sec = time.time() - start_time

    # Запись метрики success
    entry = MetricEntry.create(
        role="generator",
        latency_sec=output.execution_time_sec,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        task_id=task_id,
        iteration=iteration,
        mode=mode,
        status="success"
    )
    logger.log(entry)

    return output


def refine_concepts(
    task_id: str,
    task_query: str,
    context: Dict[str, Any],
    iteration: int,
    mode: str,
    previous_output: GeneratorOutput,
    previous_critique: Dict[str, Any],
    triz_memory: Dict[str, Any],
    llm_client: Any = None,
    model: str = None,
) -> GeneratorOutput:
    """
    Доработка концепций на основе критики.

    Args:
        task_id: UUID задачи
        task_query: Запрос пользователя
        context: Контекст
        iteration: Номер итерации
        mode: sufficiency | optimality
        previous_output: Предыдущий выход Генератора
        previous_critique: Критика от Критика
        triz_memory: Принципы + матрица ТРИЗ
        llm_client: Клиент LLM. None → RealLLMClient(role="generator")
        model: Модель. None → из клиента

    Returns:
        GeneratorOutput с доработанными концепциями
    """
    llm_client, model = _resolve_llm(llm_client, model, "generator")
    llm_client = _wrap_llm_client(llm_client, task_id, iteration, "generator")
    start_time = time.time()
    logger = MetricsLogger()

    # Генерация seed
    idempotency_mode = IdempotencyMode.SUFFICIENCY if mode == "sufficiency" else IdempotencyMode.OPTIMALITY
    seed = generate_seed(task_id, iteration, "generator", idempotency_mode)

    # Построение промпта
    previous_output_dict = json.loads(previous_output.to_json())
    user_prompt = build_refinement_prompt(
        task_query, context, previous_output_dict, previous_critique, triz_memory
    )

    # Вызов LLM
    try:
        response = llm_client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            seed=seed,
            response_format={"type": "json_object"}
        )

        tokens_in = response.get("usage", {}).get("prompt_tokens", 0)
        tokens_out = response.get("usage", {}).get("completion_tokens", 0)
        content = response.get("content", "{}")

    except Exception as e:
        latency = time.time() - start_time
        entry = MetricEntry.create(
            role="generator",
            latency_sec=latency,
            tokens_in=0,
            tokens_out=0,
            task_id=task_id,
            iteration=iteration,
            mode=mode,
            status="error",
            error_type=type(e).__name__
        )
        logger.log(entry)
        raise

    # Парсинг
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        latency = time.time() - start_time
        entry = MetricEntry.create(
            role="generator",
            latency_sec=latency,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            task_id=task_id,
            iteration=iteration,
            mode=mode,
            status="error",
            error_type="JSONDecodeError"
        )
        logger.log(entry)
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")

    # Преобразование
    output = _parse_generator_output(task_id, data)
    output.tokens_in = tokens_in
    output.tokens_out = tokens_out
    output.execution_time_sec = time.time() - start_time

    # Метрика
    entry = MetricEntry.create(
        role="generator",
        latency_sec=output.execution_time_sec,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        task_id=task_id,
        iteration=iteration,
        mode=mode,
        status="success"
    )
    logger.log(entry)

    return output


def run_ariz_full(
    task_id: str,
    task_query: str,
    context: Dict[str, Any],
    iteration: int,
    mode: str,
    triz_memory: Dict[str, Any],
    ariz_memory: Dict[str, Any],
    llm_client: Any = None,
    model: str = None,
    **kwargs,
) -> GeneratorOutput:
    """
    Полный проход АРИЗ (все 8 шагов за один вызов).
    Используется для sufficiency.

    llm_client: None → RealLLMClient(role="generator")
    model: None → из клиента
    kwargs: domain, goal_type, entities, materials, processes, existing_solutions
    """
    llm_client, model = _resolve_llm(llm_client, model, "generator")
    llm_client = _wrap_llm_client(llm_client, task_id, iteration, "generator")
    # Генерация концепций (шаги 1-7)
    output = generate_concepts(
        task_id, task_query, context, iteration, mode,
        triz_memory, ariz_memory, llm_client, model,
        **kwargs,
    )

    # Линеаризация каждой концепции (шаг 8)
    for i, concept in enumerate(output.concepts):
        linearization = _linearize_concept(concept.to_dict(), task_id, iteration, llm_client, model)
        output.concepts[i].linearization = linearization

    return output


def run_ariz_two_pass(
    task_id: str,
    task_query: str,
    context: Dict[str, Any],
    iteration: int,
    mode: str,
    triz_memory: Dict[str, Any],
    ariz_memory: Dict[str, Any],
    llm_client: Any = None,
    model: str = None,
    **kwargs,
) -> GeneratorOutput:
    """
    Двухпроходный АРИЗ (для optimality).
    Проход 1: шаги 1-4 (модель, ИКР, противоречия)
    Проход 2: шаги 5-8 (ресурсы, приёмы, концепции, линеаризация)

    llm_client: None → RealLLMClient(role="generator")
    model: None → из клиента
    """
    llm_client, model = _resolve_llm(llm_client, model, "generator")
    llm_client = _wrap_llm_client(llm_client, task_id, iteration, "generator")
    start_time = time.time()
    logger = MetricsLogger()

    idempotency_mode = IdempotencyMode.OPTIMALITY

    # Извлекаем FactPack-параметры из kwargs
    fp_domain = kwargs.get("domain")
    fp_goal_type = kwargs.get("goal_type")
    fp_entities = kwargs.get("entities")
    fp_materials = kwargs.get("materials")
    fp_processes = kwargs.get("processes")
    fp_existing_solutions = kwargs.get("existing_solutions")

    # Проход 1: шаги 1-4
    pass1_prompt = _build_pass1_prompt(
        task_query, context, triz_memory, ariz_memory,
        domain=fp_domain, goal_type=fp_goal_type,
        entities=fp_entities, materials=fp_materials,
        processes=fp_processes, existing_solutions=fp_existing_solutions,
    )

    seed1 = generate_seed(task_id, iteration, "generator_pass1", idempotency_mode)

    response1 = llm_client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": pass1_prompt},
        ],
        temperature=0.3,
        seed=seed1,
        response_format={"type": "json_object"}
    )

    pass1_data = json.loads(response1.get("content", "{}"))
    tokens_in_1 = response1.get("usage", {}).get("prompt_tokens", 0)
    tokens_out_1 = response1.get("usage", {}).get("completion_tokens", 0)

    # Проход 2: шаги 5-8 на основе pass1
    pass2_prompt = _build_pass2_prompt(
        task_query, context, pass1_data, triz_memory,
        domain=fp_domain, goal_type=fp_goal_type,
        entities=fp_entities, materials=fp_materials,
        processes=fp_processes, existing_solutions=fp_existing_solutions,
    )

    seed2 = generate_seed(task_id, iteration, "generator_pass2", idempotency_mode)

    response2 = llm_client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": pass2_prompt},
        ],
        temperature=0.4,
        seed=seed2,
        response_format={"type": "json_object"}
    )

    pass2_data = json.loads(response2.get("content", "{}"))
    tokens_in_2 = response2.get("usage", {}).get("prompt_tokens", 0)
    tokens_out_2 = response2.get("usage", {}).get("completion_tokens", 0)

    # Объединение результатов (FIX: dict merge, not set)
    combined_data = {**pass1_data, **pass2_data}

    output = _parse_generator_output(task_id, combined_data)
    output.tokens_in = tokens_in_1 + tokens_in_2
    output.tokens_out = tokens_out_1 + tokens_out_2
    output.execution_time_sec = time.time() - start_time

    # Метрика
    entry = MetricEntry.create(
        role="generator",
        latency_sec=output.execution_time_sec,
        tokens_in=output.tokens_in,
        tokens_out=output.tokens_out,
        task_id=task_id,
        iteration=iteration,
        mode=mode,
        status="success",
        pass_count=2
    )
    logger.log(entry)

    return output


# ============================================================
# ВНУТРЕННИЕ ФУНКЦИИ
# ============================================================


def _parse_generator_output(task_id: str, data: Dict[str, Any]) -> GeneratorOutput:
    """Парсинг JSON-ответа LLM в GeneratorOutput"""
    # Парсинг концепций
    concepts = []
    for c_data in data.get("concepts", []):
        if isinstance(c_data, str):
            concepts.append(Concept(
                id=f"concept_{len(concepts)+1:03d}",
                name=c_data[:60],
                description=c_data,
            ))
            continue
        concept = Concept(
            id=c_data.get("id", f"concept_{len(concepts)+1:03d}"),
            name=c_data.get("name", "Unnamed"),
            description=c_data.get("description", ""),
            resolved_contradictions=c_data.get("resolved_contradictions", []),
            triz_principles_used=c_data.get("triz_principles_used", []),
            linearization=[],  # Заполняется позже
            estimated_metrics=c_data.get("estimated_metrics", {}),
        )
        concepts.append(concept)

    # Парсинг противоречий
    contradictions = []
    for c_data in data.get("contradictions_resolved", []):
        if isinstance(c_data, str):
            # LLM вернула строку вместо объекта — создаём заглушку
            contradictions.append(Contradiction(
                id=f"contr_{len(contradictions)+1:03d}",
                contradiction_type="unknown",
                improving_parameter="",
                worsening_parameter="",
                description=c_data,
            ))
            continue
        contradiction = Contradiction(
            id=c_data.get("id", f"contr_{len(contradictions)+1:03d}"),
            contradiction_type=c_data.get("contradiction_type", "technical"),
            improving_parameter=c_data.get("improving_parameter", ""),
            worsening_parameter=c_data.get("worsening_parameter", ""),
            description=c_data.get("description", ""),
        )
        contradictions.append(contradiction)

    # Парсинг источников
    sources = []
    for s_data in data.get("sources", []):
        source = Source(
            title=s_data.get("title", "Unknown"),
            doi=s_data.get("doi"),
            url=s_data.get("url"),
            verified=False,  # ВСЕГДА false в лайт
            verification_note="Generated by LLM, not verified against real database"
        )
        sources.append(source)

    return GeneratorOutput(
        task_id=task_id,
        task_model=data.get("task_model"),
        enhanced_model=data.get("enhanced_model"),
        conflicting_pairs=data.get("conflicting_pairs"),
        ikr=data.get("ikr"),
        technical_contradictions=data.get("technical_contradictions"),
        physical_contradictions=data.get("physical_contradictions"),
        operational_zone=data.get("operational_zone"),
        operational_time=data.get("operational_time"),
        resources=data.get("resources"),
        raw_solutions=data.get("raw_solutions"),
        concepts=concepts,
        contradictions_resolved=contradictions,
        sources=sources,
    )


def _linearize_concept(
    concept: Dict[str, Any],
    task_id: str,
    iteration: int,
    llm_client: Any = None,
    model: str = None,
) -> list:
    """Линеаризация одной концепции (шаг 8)"""
    llm_client, model = _resolve_llm(llm_client, model, "generator")
    llm_client = _wrap_llm_client(llm_client, task_id, iteration, "generator")
    prompt = build_linearization_prompt(concept)

    response = llm_client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    data = json.loads(response.get("content", "{}"))

    steps = []
    for step_data in data.get("linearization", []):
        step = LinearizationStep(
            id=step_data.get("id", f"step_{len(steps)+1:03d}"),
            title=step_data.get("title", ""),
            description=step_data.get("description", ""),
            required_skills=step_data.get("required_skills", []),
            dependencies=step_data.get("dependencies", []),
            success_criteria=step_data.get("success_criteria", ""),
            failure_handling=step_data.get("failure_handling", ""),
            estimated_time_sec=step_data.get("estimated_time_sec", 0.0),
        )
        steps.append(step)

    return steps


def _build_pass1_prompt(
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
    """Построение промпта для прохода 1 (шаги 1-4)"""
    from .prompts import _format_factpack_context
    principles = triz_memory.get("principles", {})
    principles_text = "\n".join([
        f"  {num}. {p['name']}: {p['description']}"
        for num, p in list(principles.items())[:10]
    ])

    ikr_templates = triz_memory.get("ikr_templates", [])
    ikr_text = "\n".join([f"  - {t}" for t in ikr_templates])

    fp_context = _format_factpack_context(domain, goal_type, entities, materials, processes, existing_solutions)

    return f"""Задача: {task_query}
Контекст: {json.dumps(context, ensure_ascii=False)}

{fp_context}

Выполни ШАГИ 1-4 АРИЗ:
1. Сформулируй модель задачи (система, подсистемы, надсистема)
2. Выдели конфликтующие пары
3. Сформулируй ИКР (без "нужно", "следует"). Шаблоны:
{ikr_text}
4. Выяви технические и физические противоречия

Доступные принципы ТРИЗ:
{principles_text}

Верни JSON:
{{
  "task_model": {{...}},
  "enhanced_model": {{...}},
  "conflicting_pairs": [...],
  "ikr": "...",
  "technical_contradictions": [...],
  "physical_contradictions": [...]
}}"""


def _build_pass2_prompt(
    task_query: str,
    context: Dict[str, Any],
    pass1_data: Dict[str, Any],
    triz_memory: Dict[str, Any],
    domain: Optional[str] = None,
    goal_type: Optional[str] = None,
    entities: Optional[List[Dict[str, str]]] = None,
    materials: Optional[List[str]] = None,
    processes: Optional[List[str]] = None,
    existing_solutions: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Построение промпта для прохода 2 (шаги 5-8)"""
    from .prompts import _format_factpack_context
    matrix = triz_memory.get("contradiction_matrix", {})
    matrix_text = "\n".join([
        f"  ({k[0]}, {k[1]}) → {v}"
        for k, v in list(matrix.items())[:7]
    ])

    resource_types = triz_memory.get("resource_types", {})
    resources_text = "\n".join([
        f"  - {name}: {data['description']}"
        for name, data in resource_types.items()
    ])

    fp_context = _format_factpack_context(domain, goal_type, entities, materials, processes, existing_solutions)

    pass1_summary = json.dumps(pass1_data, ensure_ascii=False, indent=2)[:2000]

    return f"""Задача: {task_query}
Контекст: {json.dumps(context, ensure_ascii=False)}

{fp_context}

Результаты шагов 1-4:
{pass1_summary}

Выполни ШАГИ 5-8 АРИЗ на основе результатов шагов 1-4:

5. Определи оператную зону, время и ресурсы ВПР:
{resources_text}
6. Для каждого физического противоречия примени 2-3 приёма ТРИЗ:
{matrix_text}
7. Синтезируй 2-4 разнонаправленные концепции
8. Линеаризуй каждую концепцию

Верни JSON:
{{
  "operational_zone": {{...}},
  "operational_time": "...",
  "resources": {{...}},
  "raw_solutions": [...],
  "concepts": [...],
  "contradictions_resolved": [...],
  "sources": [...]
}}"""