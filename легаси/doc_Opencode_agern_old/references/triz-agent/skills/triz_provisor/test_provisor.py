"""
Тестовый скрипт для навыка Провизора.
"""

import sys
import json
import os

_profile_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _profile_root not in sys.path:
    sys.path.insert(0, _profile_root)

from skills.triz_provisor.schemas import (
    Evaluation, StopDecision, FinalRecommendation, IterationRecord,
)
from skills.triz_provisor.metrics import (
    compute_completeness,
    compute_coherence,
    compute_overall,
    compute_improvement_delta,
    detect_plateau,
)
from skills.triz_provisor.rule_based import (
    rule_based_evaluate,
    rule_based_stop_decision,
    select_best_concept,
)
from skills.triz_provisor.handler import (
    evaluate_iteration,
    decide_continue,
    synthesize_final,
)


# ============================================================
# MOCK LLM CLIENT
# ============================================================

class MockLLMClient:
    """Mock LLM-клиент для тестирования."""

    def __init__(self, response_data=None):
        self.response_data = response_data or {
            "feasibility": 0.8,
            "novelty": 0.7,
            "comments": "Test evaluation",
        }
        self.call_count = 0

    def chat(self, model, messages, temperature=0.0, seed=None, response_format=None):
        self.call_count += 1
        return {
            "content": json.dumps(self.response_data, ensure_ascii=False),
            "usage": {"prompt_tokens": 500, "completion_tokens": 100},
        }


# ============================================================
# ТЕСТЫ МЕТРИК
# ============================================================

def test_compute_completeness():
    assert compute_completeness([{}, {}, {}], 3) == 1.0
    assert compute_completeness([{}, {}], 3) == 2 / 3
    assert compute_completeness([{}, {}, {}, {}], 3) == 1.0
    assert compute_completeness([], 3) == 0.0
    assert compute_completeness([{}, {}, {}], 0) == 1.0
    print("✓ compute_completeness")


def test_compute_coherence():
    assert compute_coherence({"analyst_issues": [], "designer_issues": []}, 6) == 1.0
    assert compute_coherence({"analyst_issues": [{}], "designer_issues": [{}, {}]}, 6) == 0.5
    assert compute_coherence(
        {"analyst_issues": [{}, {}, {}], "designer_issues": [{}, {}, {}]}, 6
    ) == 0.0
    print("✓ compute_coherence")


def test_compute_overall():
    assert compute_overall(1.0, 1.0, 1.0, 1.0) == 10.0
    assert compute_overall(0.5, 0.5, 0.5, 0.5) == 5.0
    assert compute_overall(1.0, 1.0, 0.0, 0.0) == 5.0
    print("✓ compute_overall")


def test_compute_improvement_delta():
    assert compute_improvement_delta(8.0, 7.0) == 1.0
    assert compute_improvement_delta(6.0, 7.0) == -1.0
    assert compute_improvement_delta(7.0, None) == 0.0
    print("✓ compute_improvement_delta")


def test_detect_plateau():
    # Плато: 2 последние дельты < 0.3
    h1 = [{"overall": 7.0}, {"overall": 7.1}, {"overall": 7.15}, {"overall": 7.18}]
    assert detect_plateau(h1, threshold=0.3, patience=2) is True

    # Не плато: есть улучшение 0.5
    h2 = [{"overall": 7.0}, {"overall": 7.5}, {"overall": 8.0}]
    assert detect_plateau(h2, threshold=0.3, patience=2) is False

    # Мало данных
    assert detect_plateau([{"overall": 7.0}], threshold=0.3, patience=2) is False
    assert detect_plateau([{"overall": 7.0}, {"overall": 7.0}], threshold=0.3, patience=2) is False

    # patience=1
    h3 = [{"overall": 7.0}, {"overall": 7.05}]
    assert detect_plateau(h3, threshold=0.3, patience=1) is True

    print("✓ detect_plateau")


# ============================================================
# ТЕСТЫ RULE-BASED
# ============================================================

def test_rule_based_evaluate():
    generator_output = {"concepts": [{}, {}, {}]}
    critique_output = {"analyst_issues": [], "designer_issues": []}

    evaluation = rule_based_evaluate(
        iteration=0,
        generator_output=generator_output,
        critique_output=critique_output,
        history=[],
    )

    assert abs(evaluation.completeness - 1.0) < 0.01
    assert abs(evaluation.coherence - 1.0) < 0.01
    assert abs(evaluation.feasibility - 0.5) < 0.01
    assert abs(evaluation.novelty - 0.5) < 0.01
    assert abs(evaluation.overall - 7.5) < 0.01
    assert evaluation.iteration == 0
    assert "LLM unavailable" in evaluation.comments

    print("✓ rule_based_evaluate")


def test_rule_based_stop_decision():
    config = {
        "max_iterations": 5,
        "quality_threshold": 7.0,
        "plateau_threshold": 0.3,
        "plateau_patience": 2,
    }

    # STOP_QUALITY
    history = [{"evaluation": {"overall": 8.0}}]
    assert rule_based_stop_decision(1, history, config) == StopDecision.STOP_QUALITY

    # STOP_LIMIT
    history = [{"evaluation": {"overall": 5.0}}]
    assert rule_based_stop_decision(5, history, config) == StopDecision.STOP_LIMIT

    # STOP_PLATEAU (iteration < max_iterations)
    history = [
        {"evaluation": {"overall": 5.0}},
        {"evaluation": {"overall": 5.1}},
        {"evaluation": {"overall": 5.15}},
    ]
    assert rule_based_stop_decision(3, history, config) == StopDecision.STOP_PLATEAU

    # CONTINUE
    history = [{"evaluation": {"overall": 5.0}}]
    assert rule_based_stop_decision(1, history, config) == StopDecision.CONTINUE

    # Пустая история
    assert rule_based_stop_decision(0, [], config) == StopDecision.CONTINUE

    print("✓ rule_based_stop_decision")


def test_select_best_concept():
    history = [
        {
            "generator_output": {
                "concepts": [
                    {"id": "c1", "estimated_metrics": {"idealness": 7.0}},
                    {"id": "c2", "estimated_metrics": {"idealness": 9.0}},
                ]
            }
        },
        {
            "generator_output": {
                "concepts": [
                    {"id": "c3", "estimated_metrics": {"idealness": 8.0}},
                ]
            }
        },
    ]

    best = select_best_concept(history)
    assert best["id"] == "c2"
    assert best["estimated_metrics"]["idealness"] == 9.0

    assert select_best_concept([]) is None

    print("✓ select_best_concept")


# ============================================================
# ТЕСТЫ HANDLER
# ============================================================

def test_evaluate_iteration():
    mock_client = MockLLMClient()

    evaluation = evaluate_iteration(
        task_id="test_001",
        task_query="Тест",
        iteration=0,
        generator_output={"concepts": [{}, {}, {}]},
        critique_output={"analyst_issues": [], "designer_issues": []},
        history=[],
        llm_client=mock_client,
        model="mock-model",
    )

    assert isinstance(evaluation, Evaluation)
    assert abs(evaluation.completeness - 1.0) < 0.01
    assert abs(evaluation.feasibility - 0.8) < 0.01
    assert abs(evaluation.novelty - 0.7) < 0.01
    assert abs(evaluation.overall - 8.75) < 0.01
    assert evaluation.iteration == 0
    assert mock_client.call_count == 1

    print("✓ evaluate_iteration")


def test_evaluate_iteration_fallback():
    """Тест rule-based fallback при отказе LLM."""

    class FailingClient:
        def chat(self, **kwargs):
            raise RuntimeError("LLM unavailable")

    evaluation = evaluate_iteration(
        task_id="test_fallback",
        task_query="Тест",
        iteration=0,
        generator_output={"concepts": [{}, {}, {}]},
        critique_output={"analyst_issues": [], "designer_issues": []},
        history=[],
        llm_client=FailingClient(),
        model="mock-model",
    )

    # Должен сработать fallback: feasibility=0.5, novelty=0.5
    assert isinstance(evaluation, Evaluation)
    assert abs(evaluation.feasibility - 0.5) < 0.01
    assert abs(evaluation.novelty - 0.5) < 0.01
    assert abs(evaluation.overall - 7.5) < 0.01
    assert "LLM unavailable" in evaluation.comments

    print("✓ evaluate_iteration fallback")


def test_decide_continue():


    # Sufficiency: CONTINUE
    history = [{"evaluation": {"overall": 5.0}}]
    decision = decide_continue(1, history, "sufficiency")
    assert decision == StopDecision.CONTINUE

    # Sufficiency: STOP_QUALITY
    history = [{"evaluation": {"overall": 8.0}}]
    decision = decide_continue(1, history, "sufficiency")
    assert decision == StopDecision.STOP_QUALITY

    print("✓ decide_continue")


def test_schemas_serialization():
    # Evaluation
    evaluation = Evaluation(
        iteration=0,
        completeness=1.0,
        coherence=1.0,
        feasibility=0.8,
        novelty=0.7,
        overall=8.75,
        improvement_delta=0.0,
    )

    data = evaluation.to_dict()
    restored = Evaluation.from_dict(data)
    assert restored.overall == 8.75
    assert restored.iteration == 0

    # IterationRecord
    record = IterationRecord(
        iteration=0,
        generator_output={"concepts": []},
        critique_output={"analyst_issues": []},
        evaluation=evaluation,
    )
    data = record.to_dict()
    restored = IterationRecord.from_dict(data)
    assert restored.iteration == 0
    assert restored.evaluation.overall == 8.75

    # FinalRecommendation
    final = FinalRecommendation(
        task_id="t1",
        total_iterations=2,
        mode="sufficiency",
        recommended_concept={"id": "c1"},
        final_evaluation=evaluation,
    )
    json_str = final.to_json()
    restored = FinalRecommendation.from_json(json_str)
    assert restored.recommended_concept["id"] == "c1"
    assert restored.final_evaluation.overall == 8.75

    # ProvisorInput
    from skills.triz_provisor.schemas import ProvisorInput

    pi = ProvisorInput(
        task_id="t1",
        task_query="q",
        context={},
        mode="sufficiency",
        triz_memory={},
        ariz_memory={},
    )
    json_str = pi.to_json()
    restored = ProvisorInput.from_json(json_str)
    assert restored.task_id == "t1"

    print("✓ Сериализация схем")


def test_synthesize_final():
    """Тест synthesize_final с mock LLM."""
    mock_client = MockLLMClient(response_data={
        "recommended_concept": {"id": "c1", "name": "Best"},
        "justification": ["Лучшая идеальность"],
        "fallback_concepts": [],
        "risks": [],
        "stop_reason": "stop_quality",
    })

    evaluation = Evaluation(
        iteration=0, completeness=1.0, coherence=1.0,
        feasibility=0.8, novelty=0.7, overall=8.75, improvement_delta=0.0,
    )

    history = [{
        "iteration": 0,
        "generator_output": {
            "concepts": [
                {"id": "c1", "name": "Best", "estimated_metrics": {"idealness": 9.0}},
            ]
        },
        "critique_output": {"analyst_issues": [], "designer_issues": []},
        "evaluation": evaluation.to_dict(),
    }]

    result = synthesize_final(
        task_id="test_synth",
        task_query="Тест",
        mode="sufficiency",
        history=history,
        stop_decision=StopDecision.STOP_QUALITY,
        llm_client=mock_client,
        model="mock-model",
    )

    assert isinstance(result, FinalRecommendation)
    assert result.recommended_concept["id"] == "c1"
    assert len(result.justification) > 0
    assert result.total_iterations == 1
    assert result.final_evaluation.overall == 8.75

    print("✓ synthesize_final")


if __name__ == "__main__":
    print("Запуск тестов навыка Провизора...\n")

    # Тесты метрик
    test_compute_completeness()
    test_compute_coherence()
    test_compute_overall()
    test_compute_improvement_delta()
    test_detect_plateau()

    # Тесты rule-based
    test_rule_based_evaluate()
    test_rule_based_stop_decision()
    test_select_best_concept()

    # Тесты handler
    test_evaluate_iteration()
    test_evaluate_iteration_fallback()
    test_decide_continue()
    test_synthesize_final()
    test_schemas_serialization()

    print("\n✅ Все тесты навыка Провизора пройдены")