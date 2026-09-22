"""
Обработчик навыка Провизора.
Оркестрирует цикл Генератор -> Критик -> Оценка -> Решение.
"""

import sys
import os
import time
import json
from typing import Dict, Any, List, Optional, Callable

# --- Импорты профиля через sys.path ---
_profile_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _profile_root not in sys.path:
    sys.path.insert(0, _profile_root)

from .schemas import (
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
# ОЦЕНКА ИТЕРАЦИИ
# ============================================================

def evaluate_iteration(
    task_id: str,
    task_query: str,
    iteration: int,
    generator_output: Dict[str, Any],
    critique_output: Dict[str, Any],
    history: List[Dict[str, Any]],
    llm_client: Any = None,
    model: str = None,
    target_concepts: int = 3,
) -> Evaluation:
    """
    Оценка итерации.

    completeness и coherence считаются кодом.
    feasibility и novelty — через LLM (с rule-based fallback).

    llm_client: None → RealLLMClient(role="provisor")
    model: None → из клиента
    """
    llm_client, model = _resolve_llm(llm_client, model, "provisor")
    from memory.config import get_mode_config, WorkMode
    from resilience import generate_seed, IdempotencyMode
    from metrics import MetricsLogger, MetricEntry

    logger = MetricsLogger()
    start_time = time.time()

    # Детерминированные метрики
    concepts = generator_output.get("concepts", [])
    completeness = compute_completeness(concepts, target_concepts)
    coherence = compute_coherence(critique_output)

    # LLM-метрики с fallback
    try:
        feasibility, novelty, comments = _evaluate_with_llm(
            task_id, task_query, iteration, generator_output, critique_output,
            completeness, coherence, llm_client, model,
        )
    except Exception:
        rule_eval = rule_based_evaluate(
            iteration, generator_output, critique_output, history, target_concepts,
        )
        feasibility = rule_eval.feasibility
        novelty = rule_eval.novelty
        comments = rule_eval.comments

    overall = compute_overall(completeness, coherence, feasibility, novelty)

    previous_overall = None
    if history:
        previous_overall = history[-1].get("evaluation", {}).get("overall")
    improvement_delta = compute_improvement_delta(overall, previous_overall)

    evaluation = Evaluation(
        iteration=iteration,
        completeness=completeness,
        coherence=coherence,
        feasibility=feasibility,
        novelty=novelty,
        overall=overall,
        improvement_delta=improvement_delta,
        comments=comments,
    )

    entry = MetricEntry.create(
        role="provisor_evaluate",
        latency_sec=time.time() - start_time,
        tokens_in=0,
        tokens_out=0,
        task_id=task_id,
        iteration=iteration,
        status="success",
        overall=overall,
        improvement_delta=improvement_delta,
    )
    logger.log(entry)

    return evaluation


# ============================================================
# LLM-ОЦЕНКА FEASIBILITY И NOVELTY
# ============================================================

def _evaluate_with_llm(
    task_id: str,
    task_query: str,
    iteration: int,
    generator_output: Dict[str, Any],
    critique_output: Dict[str, Any],
    completeness: float,
    coherence: float,
    llm_client: Any = None,
    model: str = None,
) -> tuple:
    """LLM-оценка feasibility и novelty."""
    llm_client, model = _resolve_llm(llm_client, model, "provisor")
    from resilience import generate_seed, IdempotencyMode

    seed = generate_seed(task_id, iteration, "provisor_evaluate", IdempotencyMode.SUFFICIENCY)

    prompt = build_evaluation_prompt(
        task_query, iteration, generator_output, critique_output,
        completeness, coherence,
    )

    response = llm_client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        seed=seed,
        response_format={"type": "json_object"},
    )

    data = json.loads(response.get("content", "{}"))

    feasibility = float(data.get("feasibility", 0.5))
    novelty = float(data.get("novelty", 0.5))
    comments = data.get("comments", "")

    feasibility = max(0.0, min(1.0, feasibility))
    novelty = max(0.0, min(1.0, novelty))

    return feasibility, novelty, comments


# ============================================================
# РЕШЕНИЕ О ПРОДОЛЖЕНИИ
# ============================================================

def decide_continue(
    iteration: int,
    history: List[Dict[str, Any]],
    mode: str,
    llm_client: Any = None,
    user_callback: Optional[Callable] = None,
) -> StopDecision:
    """
    Решение о продолжении/остановке.
    Для sufficiency — rule-based.
    Для optimality — rule-based + пользователь.
    """
    from memory.config import get_mode_config, WorkMode

    config = get_mode_config(WorkMode(mode))

    decision = rule_based_stop_decision(iteration, history, config)

    if mode == "optimality" and not config.get("auto_stop", False):
        if user_callback is not None and decision != StopDecision.CONTINUE:
            user_decision = user_callback(decision, history)
            if user_decision == "stop":
                return StopDecision.STOP_USER

    return decision


# ============================================================
# ФИНАЛЬНЫЙ СИНТЕЗ
# ============================================================

def synthesize_final(
    task_id: str,
    task_query: str,
    mode: str,
    history: List[Dict[str, Any]],
    stop_decision: StopDecision,
    llm_client: Any = None,
    model: str = None,
) -> FinalRecommendation:
    """
    Синтез финальной рекомендации.

    llm_client: None → RealLLMClient(role="provisor")
    model: None → из клиента
    """
    llm_client, model = _resolve_llm(llm_client, model, "provisor")
    from resilience import generate_seed, IdempotencyMode
    from metrics import MetricsLogger, MetricEntry

    logger = MetricsLogger()
    start_time = time.time()

    best_concept = select_best_concept(history)

    if best_concept is None:
        final_eval_dict = history[-1]["evaluation"] if history else {
            "iteration": 0, "completeness": 0, "coherence": 0,
            "feasibility": 0, "novelty": 0, "overall": 0, "improvement_delta": 0,
        }
        final_eval = Evaluation.from_dict(final_eval_dict) if isinstance(final_eval_dict, dict) else final_eval_dict
        return FinalRecommendation(
            task_id=task_id,
            total_iterations=len(history),
            mode=mode,
            recommended_concept={},
            justification=["Не удалось найти подходящую концепцию"],
            final_evaluation=final_eval,
            stop_reason=stop_decision.value,
        )

    # LLM-синтез
    try:
        seed = generate_seed(task_id, len(history), "provisor_synthesize", IdempotencyMode.SUFFICIENCY)
        prompt = build_synthesis_prompt(task_query, history)

        response = llm_client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            seed=seed,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.get("content", "{}"))
        tokens_in = response.get("usage", {}).get("prompt_tokens", 0)
        tokens_out = response.get("usage", {}).get("completion_tokens", 0)

    except Exception:
        data = _rule_based_synthesize(history, best_concept)
        tokens_in = 0
        tokens_out = 0

    final_eval_dict = history[-1]["evaluation"] if history else {
        "iteration": 0, "completeness": 0, "coherence": 0,
        "feasibility": 0, "novelty": 0, "overall": 0, "improvement_delta": 0,
    }
    final_eval = Evaluation.from_dict(final_eval_dict) if isinstance(final_eval_dict, dict) else final_eval_dict

    recommendation = FinalRecommendation(
        task_id=task_id,
        total_iterations=len(history),
        mode=mode,
        recommended_concept=data.get("recommended_concept", best_concept),
        justification=data.get("justification", []),
        fallback_concepts=data.get("fallback_concepts", []),
        risks=data.get("risks", []),
        final_evaluation=final_eval,
        stop_reason=data.get("stop_reason", stop_decision.value),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        execution_time_sec=time.time() - start_time,
    )

    entry = MetricEntry.create(
        role="provisor_synthesize",
        latency_sec=recommendation.execution_time_sec,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        task_id=task_id,
        iteration=len(history),
        mode=mode,
        status="success",
        final_overall=final_eval.overall,
    )
    logger.log(entry)

    return recommendation


def _rule_based_synthesize(
    history: List[Dict[str, Any]],
    best_concept: Dict[str, Any],
) -> Dict[str, Any]:
    """Rule-based синтез при отказе LLM."""
    all_concepts = []
    for record in history:
        all_concepts.extend(record.get("generator_output", {}).get("concepts", []))

    fallback = [c for c in all_concepts if c.get("id") != best_concept.get("id")][:2]

    return {
        "recommended_concept": best_concept,
        "justification": [
            f"Максимальная идеальность: "
            f"{best_concept.get('estimated_metrics', {}).get('idealness', '?')}",
            "Выбрано rule-based синтезатором (LLM недоступен)",
        ],
        "fallback_concepts": fallback,
        "risks": [],
        "stop_reason": "rule_based_synthesis",
    }


# ============================================================
# ПОЛНЫЙ ЦИКЛ ТРИЗ-АГЕНТА
# ============================================================

def run_triz_cycle(
    task_id: str,
    task_query: str,
    context: Dict[str, Any],
    mode: str,
    generator_fn: Callable,
    critic_fn: Callable,
    llm_client: Any = None,
    model: str = None,
    user_callback: Optional[Callable] = None,
    task_input: Any = None,
) -> FinalRecommendation:
    """
    Полный цикл ТРИЗ-агента.

    llm_client: None → RealLLMClient(role="provisor")
    model: None → из клиента
    task_input: Optional[FactPack] — структурированный вход (домен, сущности, материалы)
    """
    llm_client, model = _resolve_llm(llm_client, model, "provisor")
    from memory import TRIZ_MEMORY, ARIZ_MEMORY
    from memory.config import get_mode_config, WorkMode
    from kanban import KanbanOperations, TaskStatus
    from metrics import MetricsLogger, MetricEntry

    logger = MetricsLogger()
    kanban = KanbanOperations()
    config = get_mode_config(WorkMode(mode))

    # Извлекаем FactPack-данные, если есть
    fp_domain = getattr(task_input, 'domain', None) if task_input else None
    fp_goal_type = getattr(task_input, 'goal_type', None) if task_input else None
    fp_entities = getattr(task_input, 'entities', None) if task_input else None
    fp_materials = getattr(task_input, 'materials', None) if task_input else None
    fp_processes = getattr(task_input, 'processes', None) if task_input else None
    fp_existing_solutions = getattr(task_input, 'existing_solutions', None) if task_input else None

    kanban.create_task(
        query=task_query,
        context=context,
        mode=mode,
        max_iterations=config["max_iterations"],
        task_id=task_id,
        fact_pack=task_input.to_dict() if hasattr(task_input, 'to_dict') else None,
    )

    # ============================================================
    # ARIZ_FSM MODE: полный прогон через ArizFSM (выход сразу)
    # ============================================================
    if mode == WorkMode.ARIZ_FSM.value:
        logger = MetricsLogger()
        from ariz.ariz_fsm_integration import run_ariz_fsm as _fsm_run

        fsm_level = config.get("ariz_level", "detailed")
        use_branching = config.get("use_branching", True)

        try:
            fsm_output = _fsm_run(
                task_id=task_id,
                task_query=task_query,
                context=context,
                llm_client=llm_client,
                model=model,
                triz_memory=TRIZ_MEMORY,
                level=fsm_level,
                use_branching=use_branching,
                enable_research=True,
                enable_decomposition=True,
                enable_feedback=True,
            )

            logger.log(MetricEntry(
                task_id=task_id, iteration=0,
                tokens_in=fsm_output.tokens_in,
                tokens_out=fsm_output.tokens_out,
                phase="ariz_fsm",
                duration_s=fsm_output.execution_time_sec,
            ))

            concepts_with_metrics = [
                (c, c.estimated_metrics.get("idealness", 5.0))
                for c in fsm_output.concepts if c.estimated_metrics
            ] or [(c, 5.0) for c in fsm_output.concepts]

            best_concept = max(concepts_with_metrics, key=lambda x: x[1])

            kanban.update_task(
                task_id=task_id, status=TaskStatus.REVIEW,
                analysis_summary=(
                    f"ARIZ-FSM ({fsm_level}), {len(fsm_output.concepts)} концепций, "
                    f"лучшая: {best_concept[0].name} ({best_concept[1]:.1f})"
                ),
            )

            return FinalRecommendation(
                concepts=[c.to_dict() for c in fsm_output.concepts],
                analysis_steps=[f"Шаг {i+1}" for i in range(8)],
                metrics={
                    "fsm_level": fsm_level,
                    "branching": use_branching,
                    "concept_count": len(fsm_output.concepts),
                    "execution_time_sec": fsm_output.execution_time_sec,
                    "tokens_in": fsm_output.tokens_in,
                    "tokens_out": fsm_output.tokens_out,
                },
                risks=[],
                stop_reason="ariz_fsm_complete",
            )
        except Exception as e:
            import traceback
            return FinalRecommendation(
                concepts=[],
                analysis_steps=[f"ArizFSM failed: {e}", traceback.format_exc()],
                metrics={}, risks=[f"Ошибка ArizFSM: {e}"],
                stop_reason="ariz_fsm_error",
            )

    history = []
    iteration = 0
    previous_critique = None

    while iteration < config["max_iterations"]:
        try:
            if iteration == 0:
                generator_output = generator_fn(
                    task_id=task_id,
                    task_query=task_query,
                    context=context,
                    iteration=iteration,
                    mode=mode,
                    triz_memory=TRIZ_MEMORY,
                    ariz_memory=ARIZ_MEMORY,
                    llm_client=llm_client,
                    model=model,
                    domain=fp_domain,
                    goal_type=fp_goal_type,
                    entities=fp_entities,
                    materials=fp_materials,
                    processes=fp_processes,
                    existing_solutions=fp_existing_solutions,
                )
            else:
                generator_output = generator_fn(
                    task_id=task_id,
                    task_query=task_query,
                    context=context,
                    iteration=iteration,
                    mode=mode,
                    triz_memory=TRIZ_MEMORY,
                    ariz_memory=ARIZ_MEMORY,
                    llm_client=llm_client,
                    model=model,
                    previous_critique=previous_critique,
                )

            gen_output_dict = json.loads(generator_output.to_json()) if hasattr(generator_output, 'to_json') else dict(generator_output)
        except Exception as e:
            kanban.fail_task(task_id, f"Generator failed: {type(e).__name__}: {e}")
            raise

        kanban.move_task(task_id, TaskStatus.CRITIC)

        try:
            from skills.triz_critic import build_critic_input
            critic_input_kwargs = build_critic_input(
                task_id=task_id,
                task_query=task_query,
                context=context,
                iteration=iteration,
                mode=mode,
                generator_output=gen_output_dict,
            )
            critique_output = critic_fn(
                critic_input=critic_input_kwargs,
                llm_client=llm_client,
                model=model,
            )

            crit_output_dict = json.loads(critique_output.to_json()) if hasattr(critique_output, 'to_json') else dict(critique_output)
        except Exception as e:
            kanban.fail_task(task_id, f"Critic failed: {type(e).__name__}: {e}")
            raise

        evaluation = evaluate_iteration(
            task_id=task_id,
            task_query=task_query,
            iteration=iteration,
            generator_output=gen_output_dict,
            critique_output=crit_output_dict,
            history=history,
            llm_client=llm_client,
            model=model,
        )

        record = IterationRecord(
            iteration=iteration,
            generator_output=gen_output_dict,
            critique_output=crit_output_dict,
            evaluation=evaluation,
        )
        history.append(record.to_dict())
        kanban.update_task_iteration(task_id, record.to_dict())

        stop_decision = decide_continue(
            iteration=iteration + 1,
            history=history,
            mode=mode,
            llm_client=llm_client,
            user_callback=user_callback,
        )

        if stop_decision != StopDecision.CONTINUE:
            break

        previous_critique = crit_output_dict
        iteration += 1
        kanban.move_task(task_id, TaskStatus.REWORK)
        kanban.move_task(task_id, TaskStatus.GENERATOR)

    final = synthesize_final(
        task_id=task_id,
        task_query=task_query,
        mode=mode,
        history=history,
        stop_decision=stop_decision,
        llm_client=llm_client,
        model=model,
    )

    if final.recommended_concept:
        kanban.complete_task(task_id, json.loads(final.to_json()))

    return final