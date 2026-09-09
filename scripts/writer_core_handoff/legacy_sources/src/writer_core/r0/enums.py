"""Closed vocabularies for writer-core R0."""

from __future__ import annotations

from enum import Enum


class _StrictStrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class WriterUnitType(_StrictStrEnum):
    """Granularity of a writer unit."""

    SECTION = "section"
    PARAGRAPH = "paragraph"
    ASSERTION = "assertion"
    OBJECT = "object"


class WriterUnitStatus(_StrictStrEnum):
    """Lifecycle state of a writer unit."""

    DRAFT = "draft"
    SELF_CHECKED = "self_checked"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class ObjectKind(_StrictStrEnum):
    """Type of structured object inside an OBJECT unit."""

    NUMBER = "number"           # value + unit + dimension
    FORMULA = "formula"         # LaTeX/math + variables
    CITATION = "citation"       # bibliographic ref (ГОСТ)
    TERM = "term"               # definition of a term
    TABLE = "table"             # structured table
    FIGURE = "figure"           # image/diagram reference


class WriterEligibility(_StrictStrEnum):
    """Whether a unit may enter the final document."""

    ALLOWED = "allowed"
    QUALIFIED = "qualified"
    FORBIDDEN_AS_FACT = "forbidden_as_fact"
    FORBIDDEN_AS_RECOMMENDATION = "forbidden_as_recommendation"


class ValidationResult(_StrictStrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    UNKNOWN = "unknown"


ValidationOutcome = ValidationResult


class CommitPolicy(_StrictStrEnum):
    ALL_OR_NOTHING = "all_or_nothing"
    DEPENDENCY_CLOSED_PARTIAL = "dependency_closed_partial"


class ToulminRole(_StrictStrEnum):
    """Argumentation role per Toulmin model."""

    CLAIM = "claim"
    DATA = "data"
    WARRANT = "warrant"
    BACKING = "backing"
    QUALIFIER = "qualifier"
    REBUTTAL = "rebuttal"


class WriterUnitRole(_StrictStrEnum):
    """Semantic role of a paragraph/section."""

    INTRODUCTION = "introduction"
    HOOK = "hook"
    GOAL = "goal"
    OBJECT_SUBJECT = "object_subject"
    HYPOTHESIS = "hypothesis"
    NOVELTY = "novelty"
    POSITIONS = "positions"
    APPROBATION = "approbation"
    STATE_OF_ART = "state_of_art"
    GAP_DECLARATION = "gap_declaration"
    METHOD = "method"
    TOOLS = "tools"
    APPROACH = "approach"
    MAIN_RESULTS = "main_results"
    ANALYSIS = "analysis"
    DETAIL = "detail"
    INTERPRETATION = "interpretation"
    LIMITATIONS = "limitations"
    FUTURE_WORK = "future_work"
    SUMMARY = "summary"
    CONCLUSION = "conclusion"
    BIBLIOGRAPHY = "bibliography"
    LITERATURE = "literature"
    HOOK = "hook"
    RELEVANCE = "relevance"
    OBJECT_SUBJECT = "object_subject"
    HYPOTHESIS = "hypothesis"
    NOVELTY = "novelty"
    POSITIONS = "positions"
    APPROBATION = "approbation"
    STATE_OF_ART = "state_of_art"
    GAP_DECLARATION = "gap_declaration"