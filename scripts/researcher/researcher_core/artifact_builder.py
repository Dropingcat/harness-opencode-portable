"""Build research-service-artifact/0.2 documents from R0 state.

Prod builder fills ``policy`` with ``policy_hash`` from ``Policy`` and
writes YAML via ``yaml.safe_dump`` with atomic ``write_artifact_atomic``.
Legacy ``render_minimal_yaml`` is kept for bubble-test compatibility.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import yaml

from researcher_core.r0.entities import Claim, EvidenceSpan, Quantity, Source
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.projections import Snapshot
from researcher_core.relation_assessment import RelationAssessment
from researcher_core.uncertainty_field import UncertaintyProfile, ReviewWorkField, uncertainty_profile_to_dict, review_work_field_to_dict


def build_minimal_service_artifact(
    snapshot: Snapshot,
    state: Mapping[str, Claim | Quantity | Source | EvidenceSpan | GraphEdge],
    title: str,
    policy: Any | None = None,
    relation_assessments: tuple[RelationAssessment, ...] = (),
    uncertainty_profiles: tuple[UncertaintyProfile, ...] = (),
    review_work_fields: tuple[ReviewWorkField, ...] = (),
) -> dict[str, Any]:
    claims: dict[str, Any] = {}
    quantities: dict[str, Any] = {}
    source_registry: dict[str, Any] = {}
    evidence_spans: dict[str, Any] = {}
    graph_edges: list[dict[str, Any]] = []
    for entity_id, entity in state.items():
        if isinstance(entity, Claim):
            claims[entity_id] = _claim_record(entity)
        if isinstance(entity, Quantity):
            quantities[entity_id] = _quantity_record(entity)
        if isinstance(entity, Source):
            source_registry[entity_id] = _source_record(entity)
        if isinstance(entity, EvidenceSpan):
            evidence_spans[entity_id] = _evidence_span_record(entity)
        if isinstance(entity, GraphEdge):
            graph_edges.append(_edge_record(entity))

    policy_record: dict[str, Any] = {}
    manifest_policy_hash = ""
    if policy is not None:
        policy_hash = getattr(policy, "policy_hash", "")
        policy_id = getattr(policy, "policy_id", "")
        policy_version = getattr(policy, "policy_version", "")
        if policy_hash:
            policy_record = {
                "policy_hash": str(policy_hash),
                "policy_id": str(policy_id) if policy_id else "",
                "policy_version": str(policy_version) if policy_version else "",
            }
            manifest_policy_hash = str(policy_hash)
    return {
        "schema_version": "research-service-artifact/0.2",
        "artifact_type": "MINIMAL_FIXTURE",
        "artifact_id": str(snapshot.snapshot_id),
        "fixture_id": "r0-dry-run-generated",
        "artifact_manifest": {
            "artifact_id": str(snapshot.snapshot_id),
            "run_id": _first_run_id(state),
            "title": title,
            "artifact_kind": "research_snapshot",
            "event_offset": snapshot.event_offset,
            "stop_reason": snapshot.stop_reason,
            "policy_hash": manifest_policy_hash,
        },
        "policy": policy_record,
        "source_versions": {},
        "document_registry": {},
        "source_registry": source_registry,
        "report_spans": {},
        "evidence_spans": evidence_spans,
        "claims": claims,
        "quantities": quantities,
        "graph_edges": graph_edges,
        "relation_assessments": {str(x.meta.id): _relation_assessment_record(x) for x in relation_assessments},
        "uncertainty_profiles": {str(x.meta.id): uncertainty_profile_to_dict(x) for x in uncertainty_profiles},
        "review_work_fields": {str(x.meta.id): review_work_field_to_dict(x) for x in review_work_fields},
        "gaps": {},
        "writer_context": {
            "allowed_claims": [],
            "qualified_claims": sorted(claims),
            "forbidden_claims": [],
            "blocked_recommendations": [],
            "citation_map": {},
        },
        "service_summary": {
            "status": "MINIMAL_GENERATED",
            "claim_count": len(claims),
            "quantity_count": len(quantities),
        },
    }


def _claim_record(claim: Claim) -> dict[str, Any]:
    return {
        "text": claim.proposition,
        "normalized_text": claim.normalized_proposition,
        "claim_kind": claim.claim_type,
        "origin_type": "local_capsule_or_fixture",
        "created_by": {
            "actor_type": claim.meta.created_by.actor_type,
            "actor_id": claim.meta.created_by.actor_id,
        },
        "created_at": claim.meta.created_at.isoformat().replace("+00:00", "Z"),
        "states": {
            "verifiability": "VERIFIABLE",
            "admission": "ADMITTED",
            "evidence_state": "UNASSESSED",
            "derivation_state": "NOT_DERIVED",
            "extrapolation_state": "NO_EXTRAPOLATION",
            "conflict_state": "NO_DIRECT_CONFLICT",
            "gap_state": "NO_OPEN_GAPS",
            "writer_eligibility": "QUALIFIED",
            "review_state": "AUTOMATED_ONLY",
        },
        "validation_summary": {
            "latest_event_refs": [],
            "blocking_gap_refs": [],
            "reason_codes": [],
        },
    }


def _quantity_record(quantity: Quantity) -> dict[str, Any]:
    return {
        "value": str(quantity.value),
        "unit": quantity.unit,
        "measured_property": quantity.measured_property,
        "created_at": quantity.meta.created_at.isoformat().replace("+00:00", "Z"),
    }


def _source_record(source: Source) -> dict[str, Any]:
    return {
        "source_type": source.source_type,
        "title": source.title,
        "locator": source.locator,
        "content_hash": source.content_hash,
        "created_at": source.meta.created_at.isoformat().replace("+00:00", "Z"),
    }


def _evidence_span_record(evidence: EvidenceSpan) -> dict[str, Any]:
    return {
        "source_id": str(evidence.source_id),
        "exact_text": evidence.exact_text,
        "locator": evidence.locator,
        "text_hash": evidence.text_hash,
        "created_at": evidence.meta.created_at.isoformat().replace("+00:00", "Z"),
    }


def _edge_record(edge: GraphEdge) -> dict[str, Any]:
    return {
        "id": str(edge.meta.id),
        "source_id": str(edge.source_id),
        "target_id": str(edge.target_id),
        "edge_kind": edge.edge_kind.value,
        "state": edge.state.value,
        "revision": edge.meta.revision,
        "created_at": edge.meta.created_at.isoformat().replace("+00:00", "Z"),
    }



def _relation_assessment_record(assessment: RelationAssessment) -> dict[str, Any]:
    return {
        "edge_id": str(assessment.edge_id),
        "assessed_edge_revision": assessment.assessed_edge_revision,
        "edge_kind": assessment.edge_kind.value,
        "verdict": assessment.verdict.value,
        "use_state": assessment.use_state.value,
        "reason_codes": list(assessment.reason_codes),
        "findings": list(assessment.findings),
        "supporting_refs": [str(x) for x in assessment.supporting_refs],
        "validator_versions": dict(assessment.validator_versions),
    }

def _first_run_id(state: Mapping[str, Claim | Quantity | Source | EvidenceSpan | GraphEdge]) -> str:
    for entity in state.values():
        return str(entity.meta.run_id)
    return ""


def render_artifact_yaml(artifact: Mapping[str, Any]) -> str:
    """Prod YAML renderer via ``yaml.safe_dump`` — handles all escaping and unicode."""

    return yaml.safe_dump(dict(artifact), sort_keys=False, allow_unicode=True, default_flow_style=False)


def write_artifact_atomic(path: Path, artifact: Mapping[str, Any]) -> None:
    """Atomic write: temp file + fsync + rename, as in legacy writer_server."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_artifact_yaml(artifact)
    # debt-scan: ignore-line -- mkstemp suffix is file type, not heuristic
    fd, tmp_name = tempfile.mkstemp(suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass  # debt-scan: ignore-line -- best-effort cleanup of temp file, error intentionally ignored


def render_minimal_yaml(value: Any, indent: int = 0) -> str:
    """Small YAML renderer for generated dependency-free fixtures."""

    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, nested in value.items():
            if isinstance(nested, dict) and not nested:
                lines.append(f"{prefix}{key}: {{}}")
            elif isinstance(nested, list) and not nested:
                lines.append(f"{prefix}{key}: []")
            elif isinstance(nested, dict | list):
                lines.append(f"{prefix}{key}:")
                lines.append(render_minimal_yaml(nested, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_scalar(nested)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{prefix}[]"
        lines = []
        for nested in value:
            if isinstance(nested, dict):
                lines.append(f"{prefix}-")
                lines.append(render_minimal_yaml(nested, indent + 2))
            else:
                lines.append(f"{prefix}- {_scalar(nested)}")
        return "\n".join(lines)
    return f"{prefix}{_scalar(value)}"


def _scalar(value: Any) -> str:
    if isinstance(value, str):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        return f'"{escaped}"'
    return str(value)
