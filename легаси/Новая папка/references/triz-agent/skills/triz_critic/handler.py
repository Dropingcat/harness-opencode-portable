"""
Обработчик Критика.
Содержит critique_generator_output и _parse_critic_report.
"""

import json
import time
from typing import Optional, Dict, Any, Callable

from .schemas import CriticInput, CriticReport
from .prompts import SYSTEM_PROMPT, build_critique_prompt
from .validator import validate_critic_output


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ: СОЗДАНИЕ REALLLM ПРИ НЕОБХОДИМОСТИ
# ============================================================

def _resolve_llm(llm_client, model, role):
    """Возвращает (llm_client, model), создавая RealLLMClient если нужно."""
    if llm_client is None:
        from llm import RealLLMClient
        llm_client = RealLLMClient(role=role)
    if model is None:
        model = getattr(llm_client, 'model', 'deepseek-v4-flash')
    return llm_client, model


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ: ПАРСИНГ LLM-ОТВЕТА
# ============================================================

def _parse_critic_report(raw_text: str, task_id: str, iteration: int,
                         tokens_in: int = 0, tokens_out: int = 0,
                         execution_time_sec: float = 0.0) -> CriticReport:
    """
    Парсит сырой ответ LLM в CriticReport.

    Args:
        raw_text: Сырой JSON-ответ от LLM
        task_id: ID задачи
        iteration: Номер итерации
        tokens_in: Потрачено токенов на вход
        tokens_out: Получено токенов на выходе
        execution_time_sec: Время выполнения в секундах

    Returns:
        CriticReport
    """
    report = validate_critic_output(raw_text)

    if report is None:
        report = CriticReport(
            task_id=task_id,
            iteration=iteration,
            accepted=False,
            overall_score=0.0,
            severity=1.0,
            check_results=[],
            recommendations=["❌ Не удалось распарсить ответ Критика"],
        )

    report.task_id = task_id
    report.iteration = iteration
    report.tokens_in = tokens_in
    report.tokens_out = tokens_out
    report.execution_time_sec = execution_time_sec

    return report


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ: КРИТИКА ВЫХОДА ГЕНЕРАТОРА
# ============================================================

def critique_generator_output(
    critic_input: CriticInput,
    llm_client: Any = None,
    model: str = None,
    logger: Optional[Callable] = None,
    tokens_callback: Optional[Callable] = None,
    mode_config: Optional[Dict[str, Any]] = None,
) -> CriticReport:
    """
    Критикует выход Генератора по чек-листу.

    llm_client: None → RealLLMClient(role="critic")
    model: None → из клиента
    """
    start_time = time.time()

    # Разрешаем дефолты
    llm_client, model = _resolve_llm(llm_client, model, "critic")

    # Шаг 1: Строим промпт
    prompt = build_critique_prompt(critic_input)

    # Шаг 2: Отправляем LLM
    response = llm_client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw_response = response.get("content", "{}")
    tokens_in = response.get("usage", {}).get("prompt_tokens", 0)
    tokens_out = response.get("usage", {}).get("completion_tokens", 0)
    elapsed = time.time() - start_time

    # Шаг 3: Парсим ответ
    report = _parse_critic_report(
        raw_text=raw_response,
        task_id=critic_input.task_id,
        iteration=critic_input.iteration,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        execution_time_sec=elapsed,
    )

    # Шаг 4: Логируем метрики
    if logger:
        summary = report.get_summary()
        logger({
            "event": "critic_completed",
            "task_id": critic_input.task_id,
            "iteration": critic_input.iteration,
            "accepted": report.accepted,
            "overall_score": report.overall_score,
            "severity": report.severity,
            "total_issues": summary["total_issues"],
            "critical_count": summary["critical_count"],
            "major_count": summary["major_count"],
            "minor_count": summary["minor_count"],
            "passed_checks": summary["passed_checks"],
            "total_checks": summary["total_checks"],
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "execution_time_sec": elapsed,
        })

    if tokens_callback:
        tokens_callback(tokens_in, tokens_out)

    return report


# ============================================================
# ХЕЛПЕР: СОЗДАНИЕ CRITICINPUT ИЗ GENERATOROUTPUT
# ============================================================

def build_critic_input(
    task_id: str,
    task_query: str,
    context: Dict[str, Any],
    iteration: int,
    mode: str,
    generator_output: Dict[str, Any],
    skip_checks: Optional[list] = None,
) -> CriticInput:
    """Строит CriticInput из выхода Генератора."""
    from .schemas import CHECKLIST_ITEMS

    checklist = CHECKLIST_ITEMS
    if skip_checks:
        checklist = [item for item in checklist if item["id"] not in skip_checks]

    return CriticInput(
        task_id=task_id,
        task_query=task_query,
        context=context,
        iteration=iteration,
        mode=mode,
        generator_output=generator_output,
        checklist=checklist,
    )
