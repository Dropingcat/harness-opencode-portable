"""
Тесты навыка Критика.
"""

import sys
import json
import time

sys.path.insert(0, '.')

from skills.triz_critic.schemas import (
    CriticInput, CriticReport, Issue, CheckResult, Severity, AffectedRole, CHECKLIST_ITEMS,
)
from skills.triz_critic.prompts import SYSTEM_PROMPT, build_critique_prompt
from skills.triz_critic.validator import (
    has_solution_verbs, validate_critic_output, _clean_report,
)
from skills.triz_critic.handler import (
    critique_generator_output, _parse_critic_report, build_critic_input,
)

# ============================================================
# MOCK LLM Client
# ============================================================

ALL_CHECKS_PASS = """{
  "check_results": [
    {"checklist_item_id": "domain_coverage", "passed": true, "score": 0.9, "findings": "Все аспекты покрыты", "issues": []},
    {"checklist_item_id": "fact_concept_consistency", "passed": true, "score": 0.8, "findings": "Факты согласованы", "issues": []},
    {"checklist_item_id": "concept_diversity", "passed": true, "score": 0.85, "findings": "Концепции разные", "issues": []},
    {"checklist_item_id": "source_specificity", "passed": true, "score": 0.7, "findings": "Источники указаны", "issues": []},
    {"checklist_item_id": "triz_correctness", "passed": true, "score": 0.9, "findings": "Приёмы корректны", "issues": []},
    {"checklist_item_id": "estimates_realism", "passed": true, "score": 0.8, "findings": "Оценки реалистичны", "issues": []}
  ],
  "analyst_issues": [],
  "designer_issues": [],
  "accepted": true,
  "overall_score": 0.85,
  "severity": 0.15,
  "missing_aspects": [],
  "recommendations": ["Рекомендация 1"]
}"""

ALL_CHECKS_FAIL = """{
  "check_results": [
    {"checklist_item_id": "domain_coverage", "passed": false, "score": 0.3, "findings": "Неполное покрытие", "issues": []},
    {"checklist_item_id": "fact_concept_consistency", "passed": false, "score": 0.4, "findings": "Несогласованность", "issues": []},
    {"checklist_item_id": "concept_diversity", "passed": true, "score": 0.8, "findings": "ok", "issues": []},
    {"checklist_item_id": "source_specificity", "passed": false, "score": 0.2, "findings": "Нет источников", "issues": []},
    {"checklist_item_id": "triz_correctness", "passed": true, "score": 0.75, "findings": "ok", "issues": []},
    {"checklist_item_id": "estimates_realism", "passed": true, "score": 0.7, "findings": "ok", "issues": []}
  ],
  "analyst_issues": [],
  "designer_issues": [],
  "accepted": false,
  "overall_score": 0.35,
  "severity": 0.75,
  "missing_aspects": ["Ресурсы", "Временные рамки"],
  "recommendations": ["Добавить покрытие", "Указать источники"]
}"""


class MockLLMClient:
    """Мок LLM-клиента для тестов Критика (единый интерфейс chat)."""
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def chat(self, model, messages, temperature=0.0, seed=None, response_format=None):
        self.call_count += 1
        idx = min(self.call_count - 1, len(self.responses) - 1)
        resp_text = self.responses[idx]
        return {
            "content": resp_text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }


# ============================================================
# ТЕСТЫ
# ============================================================

def test_schemas_serialization():
    """Тест сериализации CriticInput и CriticReport"""
    # CriticInput
    ci = CriticInput(
        task_id='t1',
        task_query='query',
        context={'key': 'val'},
        iteration=0,
        mode='sufficiency',
        generator_output={'concepts': []},
    )
    json_str = ci.to_json()
    ci2 = CriticInput.from_json(json_str)
    assert ci2.task_id == 't1'
    assert ci2.iteration == 0
    assert ci2.mode == 'sufficiency'

    # CriticReport
    cr = CriticReport(
        task_id='t1',
        iteration=0,
        accepted=True,
        overall_score=0.85,
        severity=0.15,
        check_results=[
            CheckResult(checklist_item_id='domain_coverage', passed=True, score=1.0, findings='ok')
        ],
    )
    json_str2 = cr.to_json()
    cr2 = CriticReport.from_json(json_str2)
    assert cr2.accepted == True
    assert abs(cr2.overall_score - 0.85) < 0.001
    assert len(cr2.check_results) == 1

    print("✓ Сериализация схем работает")


def test_checklist_structure():
    """Тест структуры чек-листа"""
    assert len(CHECKLIST_ITEMS) == 6, f"Expected 6 items, got {len(CHECKLIST_ITEMS)}"

    expected_ids = [
        "domain_coverage", "fact_concept_consistency",
        "concept_diversity", "source_specificity",
        "triz_correctness", "estimates_realism",
    ]
    for i, item in enumerate(CHECKLIST_ITEMS):
        assert item["id"] == expected_ids[i], f"Item {i} id mismatch: {item['id']}"
        assert "name" in item
        assert "description" in item
        assert "validation" in item

    print(f"✓ Чек-лист: {len(CHECKLIST_ITEMS)} пунктов")


def test_severity_enum():
    """Тест enum Severity"""
    assert Severity.CRITICAL.value == "critical"
    assert Severity.MAJOR.value == "major"
    assert Severity.MINOR.value == "minor"
    print("✓ Severity enum работает")


def test_affected_role_enum():
    """Тест enum AffectedRole"""
    assert AffectedRole.ANALYST.value == "analyst"
    assert AffectedRole.DESIGNER.value == "designer"
    print("✓ AffectedRole enum работает")


def test_issue_dataclass():
    """Тест Issue dataclass"""
    issue = Issue(
        id="i1",
        checklist_item_id="domain_coverage",
        severity="major",
        affected_role="analyst",
        description="Неполное покрытие",
        evidence="Не учтены ограничения",
        recommendation="Добавить раздел ограничений",
    )
    d = issue.to_dict()
    assert d["id"] == "i1"
    assert d["severity"] == "major"

    issue2 = Issue.from_dict(d)
    assert issue2.severity == "major"
    assert issue2.description == "Неполное покрытие"
    print("✓ Issue dataclass работает")


def test_system_prompt():
    """Тест системного промпта"""
    assert len(SYSTEM_PROMPT) > 500, "SYSTEM_PROMPT too short"
    assert "Критик" in SYSTEM_PROMPT
    assert "check_results" in SYSTEM_PROMPT
    assert "accepted" in SYSTEM_PROMPT
    assert "domain_coverage" in SYSTEM_PROMPT
    print(f"✓ Системный промпт корректен ({len(SYSTEM_PROMPT)} символов)")


def test_prompt_building():
    """Тест сборки промпта для критика"""
    ci = CriticInput(
        task_id='test-1',
        task_query='Оптимизировать процесс',
        context={'domain': 'IT'},
        iteration=1,
        mode='optimality',
        generator_output={'concepts': [{'id': 'c1', 'name': 'Концепция 1'}]},
    )
    prompt = build_critique_prompt(ci)

    assert 'test-1' in prompt
    assert 'Оптимизировать процесс' in prompt
    assert 'optimality' in prompt
    assert 'domain_coverage' in prompt
    assert len(prompt) > 400, "Prompt too short"

    print(f"✓ Промпт критика строится корректно ({len(prompt)} символов)")


def test_clean_report():
    """Тест очистки отчёта"""
    # Удаление ```json
    cleaned = _clean_report("```json\n{\"a\": 1}\n```")
    assert cleaned == "{\"a\": 1}", f"Got: {cleaned}"

    # Удаление ``` без json
    cleaned = _clean_report("```\n{\"a\": 1}\n```")
    assert cleaned == "{\"a\": 1}", f"Got: {cleaned}"

    # Обрезка пробелов
    cleaned = _clean_report("  {\"a\": 1}  ")
    assert cleaned == "{\"a\": 1}", f"Got: {cleaned}"

    # Удаление пояснений до JSON
    cleaned = _clean_report("Вот результат:\n{\"a\": 1}")
    assert cleaned == "{\"a\": 1}", f"Got: {cleaned}"

    # Пустая строка
    cleaned = _clean_report("")
    assert cleaned == ""

    # Хвост после JSON
    cleaned = _clean_report("{\"a\": 1}\nи ещё текст")
    assert cleaned == "{\"a\": 1}", f"Got: {cleaned}"

    print("✓ Очистка отчёта работает")


def test_solution_verbs():
    """Тест проверки глаголов-действий"""
    assert has_solution_verbs("разделить задачу", threshold=1)
    assert has_solution_verbs("объединить и извлечь", threshold=2)
    assert not has_solution_verbs("")
    assert not has_solution_verbs("просто текст", threshold=1)
    assert not has_solution_verbs(None, threshold=1)

    # Длинный текст с глаголами
    long_text = "разделить процесс на этапы и объединить результаты"
    assert has_solution_verbs(long_text, threshold=2)

    print("✓ has_solution_verbs работает")


def test_validate_output():
    """Тест валидации выхода Критика"""
    # Валидный JSON со всеми 6 проверками
    report = validate_critic_output(ALL_CHECKS_PASS)
    assert report is not None
    assert report.accepted == True
    assert abs(report.overall_score - 0.85) < 0.001
    assert len(report.check_results) == 6
    assert len(report.recommendations) == 1

    # Невалидный ответ
    assert validate_critic_output("not json") is None
    assert validate_critic_output("") is None

    # Пустой JSON
    assert validate_critic_output("{}") is None

    # Отклонённый отчёт
    report2 = validate_critic_output(ALL_CHECKS_FAIL)
    assert report2 is not None
    assert report2.accepted == False
    assert len(report2.missing_aspects) == 2

    # LLM-ответ с ```json разметкой
    wrapped = "```json\n" + ALL_CHECKS_PASS + "\n```"
    report3 = validate_critic_output(wrapped)
    assert report3 is not None
    assert report3.accepted == True

    print("✓ Валидация выхода Критика работает")


def test_parse_critic_report():
    """Тест парсинга отчёта Критика"""
    # Успешный парсинг
    report = _parse_critic_report(
        ALL_CHECKS_PASS, "t1", 0,
        tokens_in=100, tokens_out=50, execution_time_sec=1.5,
    )
    assert report.accepted == True
    assert report.task_id == "t1"
    assert report.iteration == 0
    assert report.tokens_in == 100
    assert report.tokens_out == 50
    assert abs(report.execution_time_sec - 1.5) < 0.001

    # Fallback при ошибке парсинга
    report2 = _parse_critic_report("garbage", "t2", 1)
    assert report2.accepted == False
    assert report2.overall_score == 0.0
    assert report2.severity == 1.0
    assert "Не удалось распарсить" in report2.recommendations[0]

    print("✓ Парсинг отчёта Критика работает")


def test_critic_report_validate():
    """Тест валидации CriticReport"""
    # Валидный отчёт — все 6 чеков, нет critical
    cr = CriticReport(
        task_id="t1", iteration=0, accepted=True,
        overall_score=0.85, severity=0.15,
        check_results=[
            CheckResult(checklist_item_id=cid, passed=True, score=1.0, findings="ok")
            for cid in ["domain_coverage", "fact_concept_consistency", "concept_diversity",
                         "source_specificity", "triz_correctness", "estimates_realism"]
        ],
    )
    errors = cr.validate()
    assert len(errors) == 0, f"Unexpected errors: {errors}"

    # Отчёт с неполным чек-листом
    cr2 = CriticReport(
        task_id="t2", iteration=0, accepted=True,
        overall_score=0.5, severity=0.5,
        check_results=[
            CheckResult(checklist_item_id="domain_coverage", passed=True, score=1.0, findings="ok")
        ],
    )
    errors2 = cr2.validate()
    assert len(errors2) > 0  # Missing 5 checks

    # Отчёт с critical-issue при accepted=True
    cr3 = CriticReport(
        task_id="t3", iteration=0, accepted=True,
        overall_score=0.8, severity=0.8,
        check_results=[],
        analyst_issues=[
            Issue(id="i1", checklist_item_id="domain_coverage", severity="critical",
                  affected_role="analyst", description="x"),
        ],
    )
    errors3 = cr3.validate()
    assert any("critical" in e for e in errors3)

    print("✓ Валидация CriticReport работает")


def test_critic_report_summary():
    """Тест резюме CriticReport"""
    cr = CriticReport(
        task_id="t1", iteration=0, accepted=True,
        overall_score=0.85, severity=0.15,
        check_results=[
            CheckResult(checklist_item_id="domain_coverage", passed=True, score=0.9, findings="ok"),
            CheckResult(checklist_item_id="triz_correctness", passed=False, score=0.3, findings="bad"),
        ],
        analyst_issues=[
            Issue(id="i1", checklist_item_id="triz_correctness", severity="critical",
                  affected_role="analyst", description="x"),
        ],
        designer_issues=[
            Issue(id="i2", checklist_item_id="domain_coverage", severity="minor",
                  affected_role="designer", description="y"),
        ],
    )
    summary = cr.get_summary()
    assert summary["accepted"] == True
    assert summary["total_issues"] == 2
    assert summary["critical_count"] == 1
    assert summary["major_count"] == 0
    assert summary["minor_count"] == 1
    assert summary["passed_checks"] == 1
    assert summary["total_checks"] == 2

    print("✓ Резюме CriticReport работает")


def test_build_critic_input():
    """Тест сборки CriticInput"""
    # Полный чек-лист
    ci = build_critic_input(
        task_id="t1",
        task_query="query",
        context={"domain": "IT"},
        iteration=0,
        mode="sufficiency",
        generator_output={"concepts": []},
    )
    assert ci.task_id == "t1"
    assert ci.iteration == 0
    assert len(ci.checklist) == 6

    # С исключением пунктов
    ci2 = build_critic_input(
        task_id="t2",
        task_query="q",
        context={},
        iteration=1,
        mode="optimality",
        generator_output={},
        skip_checks=["estimates_realism", "source_specificity"],
    )
    assert len(ci2.checklist) == 4
    ids = [item["id"] for item in ci2.checklist]
    assert "estimates_realism" not in ids
    assert "source_specificity" not in ids

    print("✓ build_critic_input работает")


def test_critique_generator_output():
    """Тест полного цикла работы Критика"""
    ci = CriticInput(
        task_id="t1",
        task_query="query",
        context={},
        iteration=0,
        mode="sufficiency",
        generator_output={"concepts": []},
    )

    # Успешная критика
    mock = MockLLMClient([ALL_CHECKS_PASS])
    logs = []

    def logger(data):
        logs.append(data)

    report = critique_generator_output(
        critic_input=ci,
        llm_client=mock,
        model="mock-model",
        logger=logger,
    )
    assert report.accepted == True
    assert abs(report.overall_score - 0.85) < 0.001
    assert report.tokens_in == 100
    assert report.tokens_out == 50
    assert mock.call_count == 1

    # Проверка логов
    assert len(logs) == 1
    assert logs[0]["event"] == "critic_completed"
    assert logs[0]["accepted"] == True
    assert logs[0]["total_issues"] == 0

    # Отклонённая критика
    mock2 = MockLLMClient([ALL_CHECKS_FAIL])
    report2 = critique_generator_output(
        critic_input=ci,
        llm_client=mock2,
        model="mock-model",
        logger=logger,
    )
    assert report2.accepted == False
    assert len(report2.missing_aspects) == 2

    print("✓ Полный цикл Критика работает")


def test_severity_auto_fix():
    """Тест auto-fix: accepted=False при critical issue"""
    # Отчёт с critical issue и accepted=True должен быть переключён
    critical_json = """{
      "check_results": [
        {"checklist_item_id": "domain_coverage", "passed": false, "score": 0.2, "findings": "bad",
          "issues": [{"id": "i1", "checklist_item_id": "domain_coverage", "severity": "critical", "affected_role": "analyst", "description": "x", "evidence": "-", "recommendation": "fix"}]},
        {"checklist_item_id": "fact_concept_consistency", "passed": true, "score": 0.8, "findings": "ok", "issues": []},
        {"checklist_item_id": "concept_diversity", "passed": true, "score": 0.8, "findings": "ok", "issues": []},
        {"checklist_item_id": "source_specificity", "passed": true, "score": 0.8, "findings": "ok", "issues": []},
        {"checklist_item_id": "triz_correctness", "passed": true, "score": 0.8, "findings": "ok", "issues": []},
        {"checklist_item_id": "estimates_realism", "passed": true, "score": 0.8, "findings": "ok", "issues": []}
      ],
      "analyst_issues": [{"id": "i1", "checklist_item_id": "domain_coverage", "severity": "critical", "affected_role": "analyst", "description": "x", "evidence": "-", "recommendation": "fix"}],
      "designer_issues": [],
      "accepted": true,
      "overall_score": 0.3,
      "severity": 0.9,
      "missing_aspects": [],
      "recommendations": []
    }"""
    report = _parse_critic_report(critical_json, "t1", 0)
    assert report.accepted == False, "Critical issue should force accepted=False"
    assert any("Ошибка валидации" in r for r in report.recommendations)

    print("✓ Auto-fix critical → accepted=False работает")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("Запуск тестов навыка Критика...\n")

    test_schemas_serialization()
    test_checklist_structure()
    test_severity_enum()
    test_affected_role_enum()
    test_issue_dataclass()
    test_system_prompt()
    test_prompt_building()
    test_clean_report()
    test_solution_verbs()
    test_validate_output()
    test_parse_critic_report()
    test_critic_report_validate()
    test_critic_report_summary()
    test_build_critic_input()
    test_critique_generator_output()
    test_severity_auto_fix()

    print("\n✅ Все тесты навыка Критика пройдены")