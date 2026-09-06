"""
Пост-валидация выхода Критика.
Содержит функции очистки, проверки глаголов и валидации JSON.
"""

import json
import re
from typing import Any, Dict, Optional

from .schemas import CriticReport, CheckResult, Issue


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

SOLUTION_VERBS: list = [
    "разделить", "объединить", "извлечь", "заменить",
    "изменить", "адаптировать", "оптимизировать", "декомпозировать",
    "синтезировать", "интегрировать", "автоматизировать", "сократить",
    "расширить", "перераспределить", "упорядочить", "стандартизировать",
]


def has_solution_verbs(text: str, threshold: int = 2) -> bool:
    """
    Проверяет, содержит ли текст достаточное количество глаголов-действий,
    характерных для решений и концепций.

    Args:
        text: Текст для проверки
        threshold: Минимальное количество глаголов (default: 2)

    Returns:
        True если найдено >= threshold глаголов
    """
    if not text:
        return False

    text_lower = text.lower()
    count = 0
    for verb in SOLUTION_VERBS:
        count += text_lower.count(verb.lower())

    return count >= threshold


def _clean_report(text: str) -> str:
    """
    Очищает сырой ответ LLM от markdown-разметки.
    Удаляет ```json ... ```, ``` ... ``` и лидирующие/замыкающие пробелы.

    Args:
        text: Сырой текст от LLM

    Returns:
        Очищенный текст, готовый к JSON-парсингу
    """
    if not text:
        return ""

    text = text.strip()

    # Удалить ```json ... ```
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()

    # Удалить возможные пояснения до JSON (ищем первую {)
    brace_start = text.find('{')
    if brace_start > 0:
        text = text[brace_start:]

    # Удалить всё после последней }
    brace_end = text.rfind('}')
    if brace_end > 0 and brace_end < len(text) - 1:
        text = text[:brace_end + 1]

    return text.strip()


# ============================================================
# ОСНОВНАЯ ВАЛИДАЦИЯ
# ============================================================

def validate_critic_output(raw_text: str) -> Optional[CriticReport]:
    """
    Парсит и валидирует сырой ответ LLM в CriticReport.

    Шаги:
    1. Очистка текста от разметки
    2. Парсинг JSON
    3. Создание CriticReport из данных
    4. Валидация отчёта

    Args:
        raw_text: Сырой JSON-ответ от LLM

    Returns:
        CriticReport если валидация успешна, None если ошибка
    """
    # Шаг 1: Очистка
    cleaned = _clean_report(raw_text)
    if not cleaned:
        return None

    # Шаг 2: Парсинг JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    # Шаг 3: Валидация полей
    if "check_results" not in data:
        return None

    if "accepted" not in data:
        return None

    if "overall_score" not in data:
        return None

    if "severity" not in data:
        return None

    # Шаг 4: Сборка CheckResult'ов
    check_results = []
    for cr_data in data.get("check_results", []):
        issues = []
        for issue_data in cr_data.get("issues", []):
            issue = Issue(
                id=issue_data.get("id", ""),
                checklist_item_id=issue_data.get("checklist_item_id", cr_data.get("checklist_item_id", "")),
                severity=issue_data.get("severity", "minor"),
                affected_role=issue_data.get("affected_role", "analyst"),
                description=issue_data.get("description", ""),
                evidence=issue_data.get("evidence", ""),
                recommendation=issue_data.get("recommendation", ""),
            )
            issues.append(issue)

        check_result = CheckResult(
            checklist_item_id=cr_data.get("checklist_item_id", ""),
            passed=cr_data.get("passed", False),
            score=cr_data.get("score", 0.0),
            findings=cr_data.get("findings", ""),
            issues=issues,
        )
        check_results.append(check_result)

    # Шаг 5: Сборка issue'ов
    analyst_issues = [
        Issue.from_dict(i) for i in data.get("analyst_issues", [])
    ]
    designer_issues = [
        Issue.from_dict(i) for i in data.get("designer_issues", [])
    ]

    # Шаг 6: Создание отчёта
    report = CriticReport(
        task_id=data.get("task_id", ""),
        iteration=data.get("iteration", 0),
        accepted=data.get("accepted", False),
        overall_score=float(data.get("overall_score", 0.0)),
        severity=float(data.get("severity", 0.0)),
        check_results=check_results,
        analyst_issues=analyst_issues,
        designer_issues=designer_issues,
        missing_aspects=data.get("missing_aspects", []),
        recommendations=data.get("recommendations", []),
        tokens_in=data.get("tokens_in", 0),
        tokens_out=data.get("tokens_out", 0),
        execution_time_sec=float(data.get("execution_time_sec", 0.0)),
    )

    # Шаг 7: Внутренняя валидация
    errors = report.validate()
    if errors:
        # Если есть ошибки валидации, помечаем accepted=False
        report.accepted = False
        for err in errors:
            report.recommendations.append(f"⚠️ Ошибка валидации: {err}")

    return report