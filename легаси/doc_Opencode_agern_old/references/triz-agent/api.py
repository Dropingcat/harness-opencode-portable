#!/usr/bin/env python3
"""
API-сервер ТРИЗ-агента (Flask).
Синхронизирован с main.py — использует StructuredInputAnalyzer.
"""

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

PROFILE_DIR = str(Path(__file__).resolve().parent)
if PROFILE_DIR not in sys.path:
    sys.path.insert(0, PROFILE_DIR)

from skills.triz_generator import run_ariz_full, run_ariz_two_pass
from skills.triz_provisor import run_triz_cycle
from kanban import KanbanOperations
from metrics import MetricsAggregator
from skills.triz_critic import critique_generator_output


app = Flask(__name__)
CORS(app)


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ
# ============================================================

def _analyze_task(task_text: str, deep_search: bool = False) -> Any:
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
# ЭНДПОИНТЫ
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({"status": "ok", "version": "1.2.0"})


@app.route("/submit", methods=["POST"])
def submit():
    """Отправка задачи"""
    data = request.json

    if not data or "task" not in data:
        return jsonify({"error": "Missing 'task' field"}), 400

    task_id = str(uuid.uuid4())[:8]
    task_query = data["task"]
    context = data.get("context", {})
    mode = data.get("mode", "sufficiency")
    deep_search = data.get("deep_search", False)

    # Анализ задачи через StructuredInputAnalyzer
    task_input = _analyze_task(task_query, deep_search=deep_search)
    if task_input is not None:
        print(f"  📊 Анализ задачи: domain={task_input.domain}, "
              f"goal={task_input.goal_type}, entities={len(task_input.entities)}")
        # Обогащаем context данными FactPack
        context["fact_pack"] = task_input.to_dict()
    else:
        print(f"  ⚠️ Анализ задачи недоступен, работа по сырому запросу")

    try:
        result = run_triz_cycle(
            task_id=task_id,
            task_query=task_query,
            context=context,
            mode=mode,
            generator_fn=run_ariz_full if mode == "sufficiency" else run_ariz_two_pass,
            critic_fn=critique_generator_output,
            llm_client=None,
            task_input=task_input,
        )

        response = {
            "task_id": task_id,
            "status": "completed",
            "result": json.loads(result.to_json()),
        }
        if task_input is not None:
            response["analysis"] = {
                "domain": task_input.domain,
                "goal_type": task_input.goal_type,
                "entities": task_input.entities,
                "materials": task_input.materials,
                "processes": task_input.processes,
                "knowledge_gaps": task_input.knowledge_gaps,
            }
        return jsonify(response)

    except Exception as e:
        return jsonify({
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
        }), 500


@app.route("/status/<task_id>", methods=["GET"])
def status(task_id):
    """Статус задачи"""
    kanban = KanbanOperations()
    task = kanban.get_task(task_id)

    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({
        "task_id": task.id,
        "query": task.query,
        "status": task.status.value,
        "mode": task.mode,
        "iteration": task.current_iteration,
        "max_iterations": task.max_iterations,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "result": task.result,
        "error": task.error,
    })


@app.route("/result/<task_id>", methods=["GET"])
def result(task_id):
    """Результат задачи"""
    kanban = KanbanOperations()
    task = kanban.get_task(task_id)

    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not task.result:
        return jsonify({"error": "Task has no result yet"}), 404

    return jsonify(json.loads(task.result))


@app.route("/metrics", methods=["GET"])
def metrics():
    """Метрики"""
    aggregator = MetricsAggregator()
    stats = aggregator.aggregate()

    return jsonify({
        "total_tasks": stats.get("total_tasks", 0),
        "avg_iterations": round(stats.get("avg_iterations", 0), 2),
        "avg_duration_sec": round(stats.get("avg_duration_sec", 0), 2),
        "total_tokens": stats.get("total_tokens", 0),
        "total_cost": round(stats.get("total_cost", 0), 4),
        "by_mode": stats.get("by_mode", {}),
    })


@app.route("/kanban", methods=["GET"])
def kanban():
    """Канбан-доска"""
    kanban = KanbanOperations()
    tasks = kanban.list_tasks()

    return jsonify({
        "tasks": [
            {
                "id": t.id,
                "query": t.query,
                "status": t.status.value,
                "mode": t.mode,
                "iteration": t.current_iteration,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
