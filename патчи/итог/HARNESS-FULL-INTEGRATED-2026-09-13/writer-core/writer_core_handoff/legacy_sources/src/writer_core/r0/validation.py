"""Validation helpers and RegistryValidator for writer-core R0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from writer_core.r0.enums import ValidationResult


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"  # error | warn | info


@dataclass(frozen=True, slots=True)
class ValidationReport:
    result: ValidationResult
    issues: tuple[ValidationIssue, ...] = ()


class RegistryValidationError(ValueError):
    """Raised when a registry operation violates invariants."""


class RegistryValidator:
    """Base validator for registry operations (extend per entity type)."""

    def validate_put(self, entity_id: str, row: dict) -> ValidationReport:
        return ValidationReport(ValidationResult.PASS)

    def validate_delete(self, entity_id: str) -> ValidationReport:
        return ValidationReport(ValidationResult.PASS)


class ValidationOutcome:
    """Simple container for validation results."""

    def __init__(self, result: str, reason_codes: tuple = (), findings: tuple = ()):
        self.result = result
        self.reason_codes = reason_codes
        self.findings = findings

    def __repr__(self):
        return f"ValidationOutcome(result={self.result}, codes={self.reason_codes})"