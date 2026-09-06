"""
Тестовый скрипт для навыка Генератора.
Использует mock LLM-клиент для тестирования без реальных вызовов.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

# Обеспечиваем доступ к modules profile root
_profile_root = str(Path(__file__).resolve().parents[2])
if _profile_root not in sys.path:
    sys.path.insert(0, _profile_root)

from memory import TRIZ_MEMORY, ARIZ_MEMORY

from .schemas import (
    GeneratorInput,
    GeneratorOutput,
    Concept,
    LinearizationStep,
    Source,
)
from .prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_refinement_prompt,
    build_linearization_prompt,
)
from .handler import (
    generate_concepts,
    refine_concepts,
    run_ariz_full,
    run_ariz_two_pass,
)


# ============================================================
# MOCK LLM CLIENT
# ============================================================


class MockLLMClient:
    """Mock LLM-клиент для тестирования"""

    def __init__(self, response_data: Dict[str, Any] = None):
        self.response_data = response_data or self._default_response()
        self.call_count = 0
        self.last_messages = None

    def chat(self, model: str, messages: list, temperature: float = 0.0,
             seed: int = None, response_format: Dict = None) -> Dict[str, Any]:
        """Mock вызов LLM"""
        self.call_count += 1
        self.last_messages = messages

        return {
            "content": json.dumps(self.response_data, ensure_ascii=False),
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
            }
        }

    def _default_response(self) -> Dict[str, Any]:
        """Дефолтный ответ с 2 концепциями"""
        return {
            "task_model": {"system": "Метеостанция", "subsystems": ["датчик", "регистратор"]},
            "enhanced_model": {"conflicts": ["точность vs стоимость"]},
            "conflicting_pairs": [{"a": "точность", "b": "стоимость"}],
            "ikr": "Ветер сам регистрирует свои параметры",
            "technical_contradictions": [{"id": "tc_001", "description": "..."}],
            "physical_contradictions": [{"id": "pc_001", "description": "..."}],
            "operational_zone": {"space": "территория школы", "height": "2-10 м"},
            "operational_time": "3 месяца",
            "resources": {"вещественные": ["анемометр"], "информационные": ["Open-Meteo"]},
            "raw_solutions": [{"id": "rs_001", "description": "..."}],
            "concepts": [
                {
                    "id": "concept_001",
                    "name": "Минималистичная",
                    "description": "Простой датчик + калибровка по открытым данным",
                    "resolved_contradictions": ["pc_001"],
                    "triz_principles_used": [22, 26],
                    "estimated_metrics": {
                        "idealness": 9.0,
                        "feasibility": 10.0,
                        "cost_rub": 2000,
                        "time_days": 90
                    }
                },
                {
                    "id": "concept_002",
                    "name": "Гибридная",
                    "description": "Arduino + ESP32 + сравнение с rp5.ru",
                    "resolved_contradictions": ["pc_001"],
                    "triz_principles_used": [7, 17],
                    "estimated_metrics": {
                        "idealness": 7.0,
                        "feasibility": 8.0,
                        "cost_rub": 8000,
                        "time_days": 100
                    }
                }
            ],
            "contradictions_resolved": [
                {
                    "id": "pc_001",
                    "contradiction_type": "physical",
                    "improving_parameter": "точность",
                    "worsening_parameter": "стоимость",
                    "description": "Датчик должен быть точным и дешёвым"
                }
            ],
            "sources": [
                {
                    "title": "Методы измерения скорости ветра",
                    "doi": "10.1234/example",
                    "url": "https://example.com",
                    "verified": False
                }
            ]
        }


# ============================================================
# ТЕСТЫ СХЕМ
# ============================================================


def test_generator_input_serialization():
    """Тест сериализации GeneratorInput"""
    input_data = GeneratorInput(
        task_id="test_001",
        task_query="Тестовая задача",
        context={"бюджет": 5000},
        iteration=0,
        mode="sufficiency",
        triz_memory=TRIZ_MEMORY,
        ariz_memory=ARIZ_MEMORY,
    )

    json_str = input_data.to_json()
    assert isinstance(json_str, str)
    assert len(json_str) > 0

    # Десериализация
    restored = GeneratorInput.from_json(json_str)
    assert restored.task_id == "test_001"
    assert restored.task_query == "Тестовая задача"

    print("✓ GeneratorInput сериализация работает")


def test_generator_output_serialization():
    """Тест сериализации GeneratorOutput"""
    output = GeneratorOutput(
        task_id="test_001",
        concepts=[
            Concept(
                id="concept_001",
                name="Тестовая концепция",
                description="Описание",
                resolved_contradictions=["contr_001"],
                triz_principles_used=[1, 2],
                linearization=[
                    LinearizationStep(
                        id="step_001",
                        title="Шаг 1",
                        description="Описание шага",
                        success_criteria="Критерий"
                    )
                ],
                estimated_metrics={"idealness": 8.0}
            )
        ],
        sources=[Source(title="Источник", verified=False)],
    )

    json_str = output.to_json()
    assert isinstance(json_str, str)

    # Десериализация
    restored = GeneratorOutput.from_json(json_str)
    assert restored.task_id == "test_001"
    assert len(restored.concepts) == 1
    assert restored.concepts[0].name == "Тестовая концепция"
    assert len(restored.concepts[0].linearization) == 1
    assert len(restored.sources) == 1
    assert restored.sources[0].verified is False

    print("✓ GeneratorOutput сериализация работает")


def test_output_validation():
    """Тест валидации GeneratorOutput"""
    # Валидный выход
    output = GeneratorOutput(
        task_id="test_001",
        concepts=[
            Concept(id="c1", name="A", description="...", linearization=[
                LinearizationStep(id="s1", title="1", description="..."),
                LinearizationStep(id="s2", title="2", description="..."),
                LinearizationStep(id="s3", title="3", description="..."),
            ]),
            Concept(id="c2", name="B", description="...", linearization=[
                LinearizationStep(id="s1", title="1", description="..."),
                LinearizationStep(id="s2", title="2", description="..."),
                LinearizationStep(id="s3", title="3", description="..."),
            ]),
        ],
        sources=[Source(title="Источник", verified=False)],
    )

    errors = output.validate()
    assert len(errors) == 0, f"Expected no errors, got: {errors}"

    # Невалидный: меньше 2 концепций
    output_invalid = GeneratorOutput(
        task_id="test_001",
        concepts=[Concept(id="c1", name="A", description="...")],
    )

    errors = output_invalid.validate()
    assert len(errors) > 0
    assert any("at least 2 concepts" in e for e in errors)

    # Невалидный: источник verified=true
    output_invalid2 = GeneratorOutput(
        task_id="test_001",
        concepts=[
            Concept(id="c1", name="A", description="...", linearization=[
                LinearizationStep(id="s1", title="1", description="..."),
                LinearizationStep(id="s2", title="2", description="..."),
                LinearizationStep(id="s3", title="3", description="..."),
            ]),
            Concept(id="c2", name="B", description="...", linearization=[
                LinearizationStep(id="s1", title="1", description="..."),
                LinearizationStep(id="s2", title="2", description="..."),
                LinearizationStep(id="s3", title="3", description="..."),
            ]),
        ],
        sources=[Source(title="Источник", verified=True)],
    )

    errors = output_invalid2.validate()
    assert len(errors) > 0
    assert any("marked as verified" in e for e in errors)

    print("✓ Валидация GeneratorOutput работает")


# ============================================================
# ТЕСТЫ ПРОМПТОВ
# ============================================================


def test_system_prompt():
    """Тест системного промпта"""
    assert len(SYSTEM_PROMPT) > 0
    assert "8 шагам АРИЗ" in SYSTEM_PROMPT or "8 шагов АРИЗ" in SYSTEM_PROMPT
    assert "МИНИМУМ 2 концепции" in SYSTEM_PROMPT
    assert "verified: false" in SYSTEM_PROMPT

    print("✓ Системный промпт корректен")


def test_build_generation_prompt():
    """Тест построения промпта генерации"""
    prompt = build_generation_prompt(
        task_query="Тестовая задача",
        context={"бюджет": 5000},
        triz_memory=TRIZ_MEMORY,
        ariz_memory=ARIZ_MEMORY
    )

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "Тестовая задача" in prompt
    assert "5000" in prompt

    print("✓ Промпт генерации строится корректно")


def test_build_refinement_prompt():
    """Тест построения промпта доработки"""
    previous_output = {
        "concepts": [
            {"name": "Концепция 1", "description": "Описание 1"}
        ]
    }
    previous_critique = {
        "designer_issues": [
            {"severity": "major", "description": "Недостаточно деталей"}
        ],
        "missing_aspects": ["Аспект 1"],
        "recommendations": ["Добавить детали"]
    }

    prompt = build_refinement_prompt(
        task_query="Тестовая задача",
        context={"бюджет": 5000},
        previous_output=previous_output,
        previous_critique=previous_critique,
        triz_memory=TRIZ_MEMORY
    )

    assert isinstance(prompt, str)
    assert "Критика от Критика" in prompt
    assert "Недостаточно деталей" in prompt

    print("✓ Промпт доработки строится корректно")


def test_build_linearization_prompt():
    """Тест построения промпта линеаризации"""
    concept = {
        "id": "concept_001",
        "name": "Тестовая концепция",
        "description": "Описание",
        "resolved_contradictions": ["contr_001"],
        "triz_principles_used": [1, 2]
    }

    prompt = build_linearization_prompt(concept)

    assert isinstance(prompt, str)
    assert "concept_001" in prompt
    assert "Тестовая концепция" in prompt

    print("✓ Промпт линеаризации строится корректно")


# ============================================================
# ТЕСТЫ HANDLER
# ============================================================


def test_generate_concepts():
    """Тест генерации концепций"""
    mock_client = MockLLMClient()

    output = generate_concepts(
        task_id="test_001",
        task_query="Тестовая задача",
        context={"бюджет": 5000},
        iteration=0,
        mode="sufficiency",
        triz_memory=TRIZ_MEMORY,
        ariz_memory=ARIZ_MEMORY,
        llm_client=mock_client,
        model="mock-model"
    )

    assert isinstance(output, GeneratorOutput)
    assert output.task_id == "test_001"
    assert len(output.concepts) == 2
    assert output.concepts[0].name == "Минималистичная"
    assert output.concepts[1].name == "Гибридная"
    assert len(output.sources) == 1
    assert output.sources[0].verified is False
    assert mock_client.call_count == 1

    print("✓ generate_concepts работает")


def test_refine_concepts():
    """Тест доработки концепций"""
    mock_client = MockLLMClient()

    previous_output = GeneratorOutput(
        task_id="test_001",
        concepts=[
            Concept(id="c1", name="Старая концепция", description="...")
        ]
    )

    previous_critique = {
        "designer_issues": [
            {"severity": "major", "description": "Недостаточно деталей"}
        ],
        "missing_aspects": [],
        "recommendations": []
    }

    output = refine_concepts(
        task_id="test_001",
        task_query="Тестовая задача",
        context={"бюджет": 5000},
        iteration=1,
        mode="sufficiency",
        previous_output=previous_output,
        previous_critique=previous_critique,
        triz_memory=TRIZ_MEMORY,
        llm_client=mock_client,
        model="mock-model"
    )

    assert isinstance(output, GeneratorOutput)
    assert output.task_id == "test_001"
    assert mock_client.call_count == 1

    print("✓ refine_concepts работает")


def test_run_ariz_full():
    """Тест полного прохода АРИЗ"""
    # Mock с линеаризацией — возвращает разные ответы на последовательные вызовы
    class SmartMockClient:
        def __init__(self):
            self.call_count = 0

        def chat(self, **kwargs):
            self.call_count += 1
            if self.call_count == 1:
                # Первый вызов: generate_concepts — концепции без линеаризации
                resp = MockLLMClient()._default_response()
                for c in resp["concepts"]:
                    c.pop("linearization", None)
                return {
                    "content": json.dumps(resp, ensure_ascii=False),
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 500}
                }
            else:
                # Второй/третий вызов: линеаризация концепции
                return {
                    "content": json.dumps({
                        "concept_id": f"concept_{self.call_count-1:03d}",
                        "linearization": [
                            {"id": "s1", "title": "Шаг 1", "description": "Собрать данные",
                             "required_skills": [], "dependencies": [],
                             "success_criteria": "Готово", "failure_handling": "Повторить",
                             "estimated_time_sec": 3600},
                            {"id": "s2", "title": "Шаг 2", "description": "Обработать",
                             "required_skills": [], "dependencies": ["s1"],
                             "success_criteria": "Готово", "failure_handling": "Повторить",
                             "estimated_time_sec": 7200},
                            {"id": "s3", "title": "Шаг 3", "description": "Внедрить",
                             "required_skills": [], "dependencies": ["s1", "s2"],
                             "success_criteria": "Готово", "failure_handling": "Повторить",
                             "estimated_time_sec": 10800},
                        ]
                    }),
                    "usage": {"prompt_tokens": 200, "completion_tokens": 150}
                }

    mock_client = SmartMockClient()

    output = run_ariz_full(
        task_id="test_001",
        task_query="Тестовая задача",
        context={"бюджет": 5000},
        iteration=0,
        mode="sufficiency",
        triz_memory=TRIZ_MEMORY,
        ariz_memory=ARIZ_MEMORY,
        llm_client=mock_client,
        model="mock-model"
    )

    assert isinstance(output, GeneratorOutput)
    assert len(output.concepts) == 2
    # Каждая концепция должна иметь линеаризацию
    for concept in output.concepts:
        assert len(concept.linearization) >= 3, f"Concept {concept.id} has {len(concept.linearization)} steps"

    # 1 вызов на генерацию + 2 на линеаризацию = 3
    assert mock_client.call_count == 3

    print("✓ run_ariz_full работает")


def test_run_ariz_two_pass():
    """Тест двухпроходного АРИЗ"""
    # Mock для прохода 1
    pass1_response = {
        "task_model": {"system": "Тест"},
        "enhanced_model": {"conflicts": []},
        "conflicting_pairs": [],
        "ikr": "ИКР",
        "technical_contradictions": [],
        "physical_contradictions": [],
    }

    # Mock для прохода 2
    pass2_response = MockLLMClient()._default_response()

    class TwoPassMockClient:
        def __init__(self):
            self.call_count = 0

        def chat(self, **kwargs):
            self.call_count += 1
            if self.call_count == 1:
                return {
                    "content": json.dumps(pass1_response, ensure_ascii=False),
                    "usage": {"prompt_tokens": 500, "completion_tokens": 250}
                }
            else:
                return {
                    "content": json.dumps(pass2_response, ensure_ascii=False),
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 500}
                }

    mock_client = TwoPassMockClient()

    output = run_ariz_two_pass(
        task_id="test_001",
        task_query="Тестовая задача",
        context={"бюджет": 5000},
        iteration=0,
        mode="optimality",
        triz_memory=TRIZ_MEMORY,
        ariz_memory=ARIZ_MEMORY,
        llm_client=mock_client,
        model="mock-model"
    )

    assert isinstance(output, GeneratorOutput)
    assert len(output.concepts) == 2
    assert mock_client.call_count == 2
    assert output.tokens_in == 1500  # 500 + 1000
    assert output.tokens_out == 750  # 250 + 500

    print("✓ run_ariz_two_pass работает")


def test_metrics_logging():
    """Тест логирования метрик"""
    from metrics import MetricsLogger

    logger = MetricsLogger()

    # Фиксируем количество записей до теста
    before = len(logger.read_all())

    mock_client = MockLLMClient()

    output = generate_concepts(
        task_id="test_metrics_001",
        task_query="Тестовая задача",
        context={},
        iteration=0,
        mode="sufficiency",
        triz_memory=TRIZ_MEMORY,
        ariz_memory=ARIZ_MEMORY,
        llm_client=mock_client,
        model="mock-model"
    )

    # Проверка, что метрика записана
    entries = logger.read_by_task("test_metrics_001")
    assert len(entries) >= 1

    entry = entries[0]
    assert entry.role == "generator"
    assert entry.task_id == "test_metrics_001"
    assert entry.iteration == 0
    assert entry.mode == "sufficiency"
    assert entry.status == "success"
    assert entry.tokens_in > 0
    assert entry.tokens_out > 0

    print("✓ Метрики логируются корректно")


if __name__ == "__main__":
    print("Запуск тестов навыка Генератора...\n")

    # Тесты схем
    test_generator_input_serialization()
    test_generator_output_serialization()
    test_output_validation()

    # Тесты промптов
    test_system_prompt()
    test_build_generation_prompt()
    test_build_refinement_prompt()
    test_build_linearization_prompt()

    # Тесты handler
    test_generate_concepts()
    test_refine_concepts()
    test_run_ariz_full()
    test_run_ariz_two_pass()
    test_metrics_logging()

    print("\n✅ Все тесты навыка Генератора пройдены")