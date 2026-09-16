"""Typed registry admission validation for R0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from researcher_core.r0.commands import CommandEnvelope
from researcher_core.r0.entities import Claim, ClaimProposal, EvidenceSpan, Quantity, QuantityProposal, Source
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityId


RegistryEntity = Claim | Quantity | Source | EvidenceSpan | GraphEdge

CODE_BATCH_EMPTY = "R0V_BATCH_EMPTY"
CODE_BATCH_FIELD_TYPE = "R0V_BATCH_FIELD_TYPE"
CODE_BATCH_MEMBER_TYPE = "R0V_BATCH_MEMBER_TYPE"
CODE_DUPLICATE_BATCH_ENTITY_ID = "R0V_DUPLICATE_BATCH_ENTITY_ID"
CODE_DUPLICATE_EXISTING_ENTITY_ID = "R0V_DUPLICATE_EXISTING_ENTITY_ID"
CODE_EDGE_ENDPOINT_MISSING = "R0V_EDGE_ENDPOINT_MISSING"
CODE_ENTITY_ID_TYPE = "R0V_ENTITY_ID_TYPE"
CODE_EVIDENCE_SOURCE_MISSING = "R0V_EVIDENCE_SOURCE_MISSING"
CODE_PROPOSAL_EXTRACTION_RUN_ID = "R0V_PROPOSAL_EXTRACTION_RUN_ID"
CODE_REFERENCE_ID_TYPE = "R0V_REFERENCE_ID_TYPE"
CODE_RUN_ID_MISMATCH = "R0V_RUN_ID_MISMATCH"

_BATCH_FIELD_SPECS = (
    ("claims", ClaimProposal),
    ("quantities", QuantityProposal),
    ("sources", Source),
    ("evidence_spans", EvidenceSpan),
    ("edges", GraphEdge),
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Single machine-readable registry admission problem."""

    code: str
    path: str
    message: str
    entity_id: EntityId | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("validation issue code is required")
        if not self.path:
            raise ValueError("validation issue path is required")
        if not self.message:
            raise ValueError("validation issue message is required")
        if self.entity_id is not None and not isinstance(self.entity_id, EntityId):
            raise TypeError("entity_id must be EntityId when provided")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Immutable collection of validation issues."""

    issues: tuple[ValidationIssue, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(self.issues)
        if any(not isinstance(issue, ValidationIssue) for issue in normalized):
            raise TypeError("validation report issues must be ValidationIssue values")
        object.__setattr__(self, "issues", normalized)

    @property
    def is_valid(self) -> bool:
        return not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    def __str__(self) -> str:
        if self.is_valid:
            return "registry validation passed"
        rendered = "; ".join(f"{issue.code} at {issue.path}: {issue.message}" for issue in self.issues)
        return f"registry validation failed: {rendered}"


class RegistryValidationError(ValueError):
    """Raised when a proposal batch violates registry invariants before commit."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(str(report))


class RegistryValidator:
    """Dependency-free validator for the registry write boundary."""

    def validate(
        self,
        batch: object,
        command: CommandEnvelope,
        existing_state: Mapping[EntityId, RegistryEntity],
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        raw_items = self._collect_raw_items(batch, issues)
        if all(not items for items in raw_items.values()):
            issues.append(ValidationIssue(CODE_BATCH_EMPTY, "proposal_batch", "proposal batch must not be empty"))

        typed_items = self._collect_typed_items(raw_items, issues)
        self._validate_proposal_runs(typed_items["claims"], "claims", issues)
        self._validate_proposal_runs(typed_items["quantities"], "quantities", issues)
        batch_ids = self._validate_prebuilt_entities(command, existing_state, typed_items, issues)
        known_ids = set(existing_state.keys()) | set(batch_ids)
        self._validate_evidence_references(typed_items["evidence_spans"], known_ids, issues)
        self._validate_edge_references(typed_items["edges"], known_ids, issues)
        return ValidationReport(tuple(issues))

    def _collect_raw_items(self, batch: object, issues: list[ValidationIssue]) -> dict[str, tuple[object, ...]]:
        raw_items: dict[str, tuple[object, ...]] = {}
        for field_name, _expected_type in _BATCH_FIELD_SPECS:
            value = getattr(batch, field_name, None)
            if not isinstance(value, tuple):
                issues.append(
                    ValidationIssue(
                        CODE_BATCH_FIELD_TYPE,
                        f"proposal_batch.{field_name}",
                        f"proposal batch field {field_name!r} must be a tuple",
                    )
                )
                raw_items[field_name] = ()
                continue
            raw_items[field_name] = value
        return raw_items

    def _collect_typed_items(
        self,
        raw_items: Mapping[str, tuple[object, ...]],
        issues: list[ValidationIssue],
    ) -> dict[str, tuple[object, ...]]:
        typed_items: dict[str, tuple[object, ...]] = {}
        for field_name, expected_type in _BATCH_FIELD_SPECS:
            valid: list[object] = []
            for index, item in enumerate(raw_items[field_name]):
                if not isinstance(item, expected_type):
                    issues.append(
                        ValidationIssue(
                            CODE_BATCH_MEMBER_TYPE,
                            f"proposal_batch.{field_name}[{index}]",
                            f"expected {expected_type.__name__}, got {type(item).__name__}",
                        )
                    )
                    continue
                valid.append(item)
            typed_items[field_name] = tuple(valid)
        return typed_items

    def _validate_proposal_runs(self, proposals: tuple[object, ...], field_name: str, issues: list[ValidationIssue]) -> None:
        for index, proposal in enumerate(proposals):
            extraction_run_id = getattr(proposal, "extraction_run_id", None)
            if not isinstance(extraction_run_id, EntityId) or extraction_run_id.namespace != "OPR":
                issues.append(
                    ValidationIssue(
                        CODE_PROPOSAL_EXTRACTION_RUN_ID,
                        f"proposal_batch.{field_name}[{index}].extraction_run_id",
                        "proposal extraction_run_id must use OPR prefix",
                    )
                )

    def _validate_prebuilt_entities(
        self,
        command: CommandEnvelope,
        existing_state: Mapping[EntityId, RegistryEntity],
        typed_items: Mapping[str, tuple[object, ...]],
        issues: list[ValidationIssue],
    ) -> dict[EntityId, str]:
        existing_ids = set(existing_state.keys())
        batch_ids: dict[EntityId, str] = {}
        for field_name in ("sources", "evidence_spans", "edges"):
            for index, entity in enumerate(typed_items[field_name]):
                path = f"proposal_batch.{field_name}[{index}]"
                entity_id = self._entity_id(entity)
                if not isinstance(entity_id, EntityId):
                    issues.append(ValidationIssue(CODE_ENTITY_ID_TYPE, f"{path}.meta.id", "prebuilt entity id must be EntityId"))
                    continue
                if entity_id in batch_ids:
                    issues.append(
                        ValidationIssue(
                            CODE_DUPLICATE_BATCH_ENTITY_ID,
                            f"{path}.meta.id",
                            f"prebuilt entity id duplicates {batch_ids[entity_id]}",
                            entity_id,
                        )
                    )
                else:
                    batch_ids[entity_id] = f"{path}.meta.id"
                if entity_id in existing_ids:
                    issues.append(
                        ValidationIssue(
                            CODE_DUPLICATE_EXISTING_ENTITY_ID,
                            f"{path}.meta.id",
                            "prebuilt entity id already exists in registry state",
                            entity_id,
                        )
                    )
                run_id = self._entity_run_id(entity)
                if run_id != command.run_id:
                    issues.append(
                        ValidationIssue(
                            CODE_RUN_ID_MISMATCH,
                            f"{path}.meta.run_id",
                            "prebuilt entity run_id must match command run_id",
                            entity_id,
                        )
                    )
        return batch_ids

    def _validate_evidence_references(
        self,
        evidence_spans: tuple[object, ...],
        known_ids: set[EntityId],
        issues: list[ValidationIssue],
    ) -> None:
        for index, evidence in enumerate(evidence_spans):
            source_id = getattr(evidence, "source_id", None)
            if not isinstance(source_id, EntityId):
                issues.append(
                    ValidationIssue(
                        CODE_REFERENCE_ID_TYPE,
                        f"proposal_batch.evidence_spans[{index}].source_id",
                        "evidence source_id must be EntityId",
                    )
                )
                continue
            if source_id not in known_ids:
                issues.append(
                    ValidationIssue(
                        CODE_EVIDENCE_SOURCE_MISSING,
                        f"proposal_batch.evidence_spans[{index}].source_id",
                        "evidence source_id does not exist in registry state or this batch",
                        source_id,
                    )
                )

    def _validate_edge_references(self, edges: tuple[object, ...], known_ids: set[EntityId], issues: list[ValidationIssue]) -> None:
        for index, edge in enumerate(edges):
            self._validate_edge_endpoint(edge, "source_id", index, known_ids, issues)
            self._validate_edge_endpoint(edge, "target_id", index, known_ids, issues)

    def _validate_edge_endpoint(
        self,
        edge: object,
        attribute_name: str,
        index: int,
        known_ids: set[EntityId],
        issues: list[ValidationIssue],
    ) -> None:
        endpoint_id = getattr(edge, attribute_name, None)
        path = f"proposal_batch.edges[{index}].{attribute_name}"
        if not isinstance(endpoint_id, EntityId):
            issues.append(ValidationIssue(CODE_REFERENCE_ID_TYPE, path, "edge endpoint id must be EntityId"))
            return
        if endpoint_id not in known_ids:
            issues.append(
                ValidationIssue(
                    CODE_EDGE_ENDPOINT_MISSING,
                    path,
                    "edge endpoint does not exist in registry state or this batch",
                    endpoint_id,
                )
            )

    def _entity_id(self, entity: object) -> EntityId | None:
        meta = getattr(entity, "meta", None)
        return getattr(meta, "id", None)

    def _entity_run_id(self, entity: object) -> EntityId | None:
        meta = getattr(entity, "meta", None)
        return getattr(meta, "run_id", None)
