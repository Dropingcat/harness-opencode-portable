"""
JSON-схемы входа и выхода Критика.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
import json


class Severity(Enum):
    """Серьёзность замечания"""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class AffectedRole(Enum):
    """Роль, к которой относится замечание"""
    ANALYST = "analyst"
    DESIGNER = "designer"


# ============================================================
# ЧЕК-ЛИСТ КРИТИКА (6 пунктов)
# ============================================================

CHECKLIST_ITEMS: List[Dict[str, str]] = [
    {
        "id": "domain_coverage",
        "name": "Полнота покрытия предметной области",
        "description": "Все ли аспекты предметной области учтены? (методы, источники, ограничения, ресурсы)",
        "validation": "Проверить наличие разделов: методы, источники, ограничения, ресурсы"
    },
    {
        "id": "fact_concept_consistency",
        "name": "Согласованность фактов и концепций",
        "description": "Ссылаются ли концепции на конкретные факты из анализа?",
        "validation": "Каждая концепция должна ссылаться минимум на 1 источник или факт"
    },
    {
        "id": "concept_diversity",
        "name": "Разнонаправленность концепций",
        "description": "Действительно ли концепции разные? (не вариации одной)",
        "validation": "Концепции должны разрешать разные противоречия или использовать разные приёмы ТРИЗ"
    },
    {
        "id": "source_specificity",
        "name": "Конкретность источников",
        "description": "Есть ли конкретные источники (DOI, URL, названия)?",
        "validation": "Минимум 1 источник с DOI или URL"
    },
    {
        "id": "triz_correctness",
        "name": "Корректность применения приёмов ТРИЗ",
        "description": "Соответствуют ли применённые приёмы матрице противоречий?",
        "validation": "Номера приёмов должны быть валидными (1-40) и соответствовать противоречиям"
    },
    {
        "id": "estimates_realism",
        "name": "Реалистичность оценок",
        "description": "Реалистичны ли оценки стоимости/времени?",
        "validation": "Оценки должны быть в разумных пределах для заданного контекста"
    },
]


@dataclass
class Issue:
    """Замечание Критика"""
    id: str
    checklist_item_id: str
    severity: str                             # critical | major | minor
    affected_role: str                        # analyst | designer
    description: str
    evidence: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Issue':
        return cls(**data)


@dataclass
class CheckResult:
    """Результат проверки одного пункта чек-листа"""
    checklist_item_id: str
    passed: bool
    score: float                              # 0.0 - 1.0
    findings: str
    issues: List[Issue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checklist_item_id": self.checklist_item_id,
            "passed": self.passed,
            "score": self.score,
            "findings": self.findings,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class CriticInput:
    """Входные данные для Критика"""
    task_id: str
    task_query: str
    context: Dict[str, Any]
    iteration: int
    mode: str                                 # sufficiency | optimality
    generator_output: Dict[str, Any]          # JSON-выход Генератора
    checklist: List[Dict[str, str]] = field(default_factory=lambda: CHECKLIST_ITEMS)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'CriticInput':
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class CriticReport:
    """Отчёт Критика — результат проверки"""
    task_id: str
    iteration: int
    accepted: bool
    overall_score: float                      # 0.0 - 1.0
    severity: float                           # 0.0 - 1.0
    check_results: List[CheckResult] = field(default_factory=list)
    analyst_issues: List[Issue] = field(default_factory=list)
    designer_issues: List[Issue] = field(default_factory=list)
    missing_aspects: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    execution_time_sec: float = 0.0

    def to_json(self) -> str:
        data = {
            "task_id": self.task_id,
            "iteration": self.iteration,
            "accepted": self.accepted,
            "overall_score": self.overall_score,
            "severity": self.severity,
            "check_results": [cr.to_dict() for cr in self.check_results],
            "analyst_issues": [i.to_dict() for i in self.analyst_issues],
            "designer_issues": [i.to_dict() for i in self.designer_issues],
            "missing_aspects": self.missing_aspects,
            "recommendations": self.recommendations,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "execution_time_sec": self.execution_time_sec,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'CriticReport':
        data = json.loads(json_str)

        # Восстановление CheckResult
        check_results = []
        for cr_data in data.get("check_results", []):
            issues = [Issue.from_dict(i) for i in cr_data.get("issues", [])]
            cr = CheckResult(
                checklist_item_id=cr_data["checklist_item_id"],
                passed=cr_data["passed"],
                score=cr_data["score"],
                findings=cr_data["findings"],
                issues=issues,
            )
            check_results.append(cr)
        data["check_results"] = check_results

        data["analyst_issues"] = [Issue.from_dict(i) for i in data.get("analyst_issues", [])]
        data["designer_issues"] = [Issue.from_dict(i) for i in data.get("designer_issues", [])]

        return cls(**data)

    def validate(self) -> List[str]:
        """Валидация отчёта. Возвращает список ошибок."""
        errors = []

        all_issues = self.analyst_issues + self.designer_issues
        has_critical = any(i.severity == "critical" for i in all_issues)
        major_count = sum(1 for i in all_issues if i.severity == "major")

        if has_critical and self.accepted:
            errors.append("accepted=True but has critical issues")
        if major_count >= 2 and self.accepted:
            errors.append(f"accepted=True but has {major_count} major issues (>=2)")

        checked_ids = {cr.checklist_item_id for cr in self.check_results}
        expected_ids = {item["id"] for item in CHECKLIST_ITEMS}
        missing = expected_ids - checked_ids
        if missing:
            errors.append(f"Missing checks for: {missing}")

        return errors

    def get_summary(self) -> Dict[str, Any]:
        """Краткое резюме отчёта"""
        all_issues = self.analyst_issues + self.designer_issues
        return {
            "accepted": self.accepted,
            "overall_score": self.overall_score,
            "severity": self.severity,
            "total_issues": len(all_issues),
            "critical_count": sum(1 for i in all_issues if i.severity == "critical"),
            "major_count": sum(1 for i in all_issues if i.severity == "major"),
            "minor_count": sum(1 for i in all_issues if i.severity == "minor"),
            "passed_checks": sum(1 for cr in self.check_results if cr.passed),
            "total_checks": len(self.check_results),
        }