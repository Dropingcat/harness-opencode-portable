#!/usr/bin/env python3
"""
ТРИЗ-агент — CLI интерфейс.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

PROFILE_DIR = "/home/orangepi/.hermes/profiles/triz-agent"
sys.path.insert(0, PROFILE_DIR)

from skills.triz_generator import run_ariz_full, run_ariz_two_pass
from skills.triz_provisor import run_triz_cycle
from kanban import KanbanOperations
from metrics import MetricsAggregator


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ
# ============================================================

def _analyze_task(task_text: str, deep_search: bool = False) -> Optional["FactPack"]:
    """
    Проанализировать задачу через StructuredInputAnalyzer.
    Возвращает FactPack или None (если анализатор не доступен).
    """
    try:
        from input import StructuredInputAnalyzer
        from input.local_search import LocalSearchEngine

        local_engine = LocalSearchEngine()
        analyzer = StructuredInputAnalyzer(
            local_engine=local_engine,
            external_engine=None,
            llm_fn=None,
            deep_search_default=deep_search,
        )
        return analyzer.analyze(task_text, deep_search=deep_search)
    except Exception as e:
        print(f"  ⚠️ Анализ задачи временно недоступен: {type(e).__name__}: {e}")
        return None


# ============================================================
# КОМАНДЫ CLI
# ============================================================

def cmd_submit(args):
    """Команда: отправить задачу"""

    task_id = str(uuid.uuid4())[:8]

    print(f"📝 Отправка задачи: {args.task}")
    print(f"   ID: {task_id}")
    print(f"   Режим: {args.mode}")
    print()

    context = {}
    if args.context:
        try:
            context = json.loads(args.context)
        except json.JSONDecodeError:
            print(f"❌ Ошибка парсинга контекста: {args.context}")
            return

    # Анализ задачи
    task_input = _analyze_task(args.task, deep_search=(args.mode == "optimality"))
    if task_input:
        print(f"   📊 Анализ: domain={task_input.domain}, "
              f"goal_type={task_input.goal_type}, "
              f"entities={len(task_input.entities)}, "
              f"sources={len(task_input.sources)}")
        print()

    try:
        from skills.triz_critic import critique_generator_output

        result = run_triz_cycle(
            task_id=task_id,
            task_query=args.task,
            context=context,
            mode=args.mode,
            generator_fn=run_ariz_full if args.mode == "sufficiency" else run_ariz_two_pass,
            critic_fn=critique_generator_output,
            task_input=task_input,
        )

        print()
        print("=" * 60)
        print("✅ ЗАДАЧА ЗАВЕРШЕНА")
        print("=" * 60)
        print(f"   Итераций: {result.total_iterations}")
        print(f"   Остановка: {result.stop_reason}")
        if result.final_evaluation:
            print(f"   Финальная оценка: {result.final_evaluation.overall:.1f}/10")
        print()
        print("📌 РЕКОМЕНДУЕМАЯ КОНЦЕПЦИЯ:")
        print(f"   Название: {result.recommended_concept.get('name', '?')}")
        print(f"   Описание: {result.recommended_concept.get('description', '?')}")
        print()

        if result.justification:
            print("💡 Обоснование:")
            for j in result.justification:
                print(f"   - {j}")
            print()

        if result.fallback_concepts:
            print("🔄 Запасные варианты:")
            for fc in result.fallback_concepts[:2]:
                nm = fc.get("name", "?")
                desc = fc.get("description", "?")
                print(f"   - {nm}: {desc[:100]}")
            print()

        if result.risks:
            print("⚠️  Риски:")
            for risk in result.risks:
                print(f"   - {risk.get('description', '?')}")
            print()

        print(f"📊 Результат сохранён в канбане: task_id={task_id}")

    except Exception as e:
        print(f"❌ Ошибка выполнения: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def cmd_status(args):
    """Команда: статус задачи"""
    kanban = KanbanOperations()
    task = kanban.get_task(args.task_id)

    if not task:
        print(f"❌ Задача {args.task_id} не найдена")
        return

    print(f"📋 Задача: {task.id}")
    print(f"   Запрос: {task.query}")
    print(f"   Статус: {task.status.value}")
    print(f"   Режим: {task.mode}")
    print(f"   Итераций: {task.current_iteration}/{task.max_iterations}")
    print(f"   Создана: {task.created_at}")
    print(f"   Обновлена: {task.updated_at}")

    if task.result:
        print()
        print("✅ Результат:")
        print(json.dumps(task.result, ensure_ascii=False, indent=2))

    if task.error:
        print()
        print(f"❌ Ошибка: {task.error}")


def cmd_metrics(args):
    """Команда: метрики"""
    aggregator = MetricsAggregator()

    print("📊 МЕТРИКИ СИСТЕМЫ")
    print("=" * 60)

    for role in ["generator", "critic", "provisor_evaluate", "provisor_synthesize"]:
        stats = aggregator.aggregate_by_role(role)
        if "error" not in stats:
            print(f"\n{role.upper()}:")
            print(f"  Вызовов: {stats.get('total_calls', 0)}")
            print(f"  Всего токенов: {stats.get('total_tokens', 0)}")
            avg_lat = stats.get("average_latency_sec", 0)
            print(f"  Средняя latency: {avg_lat:.2f} сек")

    model_prices = {
        "generator": {"input": 0.00003, "output": 0.00006},
        "critic": {"input": 0.00003, "output": 0.00006},
        "provisor_evaluate": {"input": 0.00003, "output": 0.00006},
        "provisor_synthesize": {"input": 0.00003, "output": 0.00006},
    }
    total_cost = aggregator.total_cost(model_prices)
    print(f"\n💰 Общая стоимость: ${total_cost:.4f}")


def cmd_list(args):
    """Команда: список задач"""
    kanban = KanbanOperations()

    tasks = []
    tasks.extend(kanban.get_queue_tasks())
    tasks.extend(kanban.get_in_progress_tasks())
    tasks.extend(kanban.get_done_tasks())

    if not tasks:
        print("📭 Нет задач")
        return

    print(f"📋 Задачи ({len(tasks)}):")
    print()

    for task in tasks:
        status_icons = {
            "queue": "⏳",
            "generator": "🔄",
            "critic": "🔍",
            "rework": "🔧",
            "done": "✅",
            "failed": "❌",
        }
        icon = status_icons.get(task.status.value, "?")
        print(f"{icon} [{task.id}] {task.query[:50]}")
        print(f"   Статус: {task.status.value}, "
              f"Итераций: {task.current_iteration}/{task.max_iterations}")
        print()


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="ТРИЗ-агент — анализ задач и генерация концепций решений",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Примеры:
  %(prog)s submit "Школьный проект по ветру" --mode sufficiency
  %(prog)s submit "Оптимизация CI/CD" --mode optimality --context '{"repo": "my/project"}'
  %(prog)s status abc123
  %(prog)s metrics
  %(prog)s list
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Команды")

    # submit
    p_sub = subparsers.add_parser("submit", help="Отправить задачу")
    p_sub.add_argument("task", type=str, help="Текст задачи")
    p_sub.add_argument("--mode", type=str, default="sufficiency",
                       choices=["sufficiency", "optimality"],
                       help="Режим работы (по умолчанию: sufficiency)")
    p_sub.add_argument("--context", type=str, default=None,
                       help="Контекст в JSON-формате")
    p_sub.set_defaults(func=cmd_submit)

    # status
    p_st = subparsers.add_parser("status", help="Статус задачи")
    p_st.add_argument("task_id", type=str, help="ID задачи")
    p_st.set_defaults(func=cmd_status)

    # metrics
    p_met = subparsers.add_parser("metrics", help="Метрики системы")
    p_met.set_defaults(func=cmd_metrics)

    # list
    p_ls = subparsers.add_parser("list", help="Список задач")
    p_ls.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()