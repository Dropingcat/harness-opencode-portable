"""Semantic Tribunal role handbook and code-generated fill requests.

The handbook is intentionally non-authoritative with respect to tool access,
evidence visibility and role admission.  Those remain owned by the versioned
Tribunal composition policy.  This module only compiles semantic guidance for
already-admitted roles and emits typed requests when guidance is missing.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import yaml

from researcher_core.r0.events import _deep_freeze
from researcher_core.tribunal_composition import (
    AssessmentNeedRef,
    TribunalCompositionPlan,
    TribunalCompositionPolicy,
    TribunalLineageProfile,
    assessment_need_refs_for_work_field,
)
from researcher_core.uncertainty_field import ReviewWorkField


class TribunalRoleHandbookError(RuntimeError):
    pass


class RoleVariantKind(StrEnum):
    FIRST_PASS = "first_pass"
    CHALLENGER = "challenger"
    CROSS_EXAM = "cross_exam"
    DEFENSE = "defense"


@dataclass(frozen=True, slots=True)
class RoleVariantSpec:
    variant: RoleVariantKind
    objective: str
    question_lenses: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("role variant objective is required")
        object.__setattr__(self, "question_lenses", tuple(x.strip() for x in self.question_lenses if x.strip()))


@dataclass(frozen=True, slots=True)
class RoleHandbookEntry:
    role_id: str
    mission: str
    mandatory_checks: tuple[str, ...]
    forbidden_moves: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    discovery_focus: tuple[str, ...]
    variants: Mapping[RoleVariantKind, RoleVariantSpec]

    def __post_init__(self) -> None:
        if not self.role_id or not self.mission.strip():
            raise ValueError("role_id/mission are required")
        if not self.variants:
            raise ValueError("role handbook entry requires at least one semantic variant")
        object.__setattr__(self, "mandatory_checks", tuple(self.mandatory_checks))
        object.__setattr__(self, "forbidden_moves", tuple(self.forbidden_moves))
        object.__setattr__(self, "stop_conditions", tuple(self.stop_conditions))
        object.__setattr__(self, "discovery_focus", tuple(self.discovery_focus))
        object.__setattr__(self, "variants", MappingProxyType(dict(self.variants)))


@dataclass(frozen=True, slots=True)
class TribunalRoleHandbook:
    handbook_id: str
    version: str
    entries: Mapping[str, RoleHandbookEntry]
    handbook_hash: str
    source_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))


@dataclass(frozen=True, slots=True)
class RoleInstructionPack:
    instruction_id: str
    role_id: str
    variant: RoleVariantKind
    handbook_version: str
    handbook_hash: str
    instruction_fingerprint: str
    mission: str
    objective: str
    mandatory_checks: tuple[str, ...]
    forbidden_moves: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    discovery_focus: tuple[str, ...]
    question_lenses: tuple[str, ...]
    expected_output_contract: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.instruction_id.startswith("RHI-"):
            raise ValueError("instruction_id must use RHI- prefix")
        if not self.instruction_fingerprint.startswith("sha256:"):
            raise ValueError("instruction_fingerprint must use sha256: prefix")
        if not self.role_id or not self.mission.strip() or not self.objective.strip():
            raise ValueError("role instruction requires role/mission/objective")
        object.__setattr__(self, "mandatory_checks", tuple(self.mandatory_checks))
        object.__setattr__(self, "forbidden_moves", tuple(self.forbidden_moves))
        object.__setattr__(self, "stop_conditions", tuple(self.stop_conditions))
        object.__setattr__(self, "discovery_focus", tuple(self.discovery_focus))
        object.__setattr__(self, "question_lenses", tuple(self.question_lenses))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoleHandbookFillRequest:
    request_key: str
    role_id: str
    missing_variant: RoleVariantKind
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    uncertainty_axes: tuple[str, ...]
    assessment_methods: tuple[str, ...]
    lineage_tags: tuple[str, ...]
    expected_output_contract: str
    policy_version: str
    policy_hash: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.request_key.startswith("RHR-"):
            raise ValueError("request_key must use RHR- prefix")
        object.__setattr__(self, "assigned_need_refs", tuple(self.assigned_need_refs))
        object.__setattr__(self, "uncertainty_axes", tuple(self.uncertainty_axes))
        object.__setattr__(self, "assessment_methods", tuple(self.assessment_methods))
        object.__setattr__(self, "lineage_tags", tuple(self.lineage_tags))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


def load_role_handbook(path: Path, policy: TribunalCompositionPolicy) -> TribunalRoleHandbook:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TribunalRoleHandbookError("role handbook root must be a mapping")
    if raw.get("schema_version") != "tribunal-role-handbook/1.0":
        raise TribunalRoleHandbookError("unsupported role handbook schema")
    if not str(raw.get("handbook_id") or "").strip() or not str(raw.get("version") or "").strip():
        raise TribunalRoleHandbookError("handbook_id/version are required")
    common = raw.get("common") or {}
    common_forbidden = tuple(str(x) for x in common.get("forbidden_moves", ()))
    common_stop_conditions = tuple(str(x) for x in common.get("first_pass_stop_conditions", ()))
    roles = raw.get("roles")
    if not isinstance(roles, Mapping):
        raise TribunalRoleHandbookError("roles mapping is required")

    entries: dict[str, RoleHandbookEntry] = {}
    forbidden_authority_fields = {"allowed_capabilities", "allowed_tools", "evidence_view", "permanent", "supported_axes", "supported_methods"}
    for role_id, spec in roles.items():
        role_id = str(role_id)
        if role_id not in policy.roles:
            raise TribunalRoleHandbookError(f"handbook references non-admitted role:{role_id}")
        if not isinstance(spec, Mapping):
            raise TribunalRoleHandbookError(f"handbook role must be mapping:{role_id}")
        leaked = forbidden_authority_fields.intersection(str(x) for x in spec)
        if leaked:
            raise TribunalRoleHandbookError(f"handbook may not grant authority fields:{role_id}:{sorted(leaked)}")
        variants_raw = spec.get("variants") or {}
        variants: dict[RoleVariantKind, RoleVariantSpec] = {}
        for variant_id, variant_spec in variants_raw.items():
            try:
                variant = RoleVariantKind(str(variant_id))
            except ValueError as exc:
                raise TribunalRoleHandbookError(f"unknown role variant:{role_id}:{variant_id}") from exc
            variants[variant] = RoleVariantSpec(
                variant=variant,
                objective=str((variant_spec or {}).get("objective") or ""),
                question_lenses=tuple(str(x) for x in (variant_spec or {}).get("question_lenses", ())),
            )
        discovery_focus = tuple(str(x) for x in spec.get("discovery_focus", ()))
        known_discoveries = {
            "MISSING_EVIDENCE", "METHOD_LIMITATION", "POSSIBLE_COUNTEREXAMPLE", "SCOPE_ISSUE",
            "CAUSALITY_PROBLEM", "NUMERIC_DISCREPANCY", "ASSUMPTION_ISSUE",
            "SOURCE_PROVENANCE_ISSUE", "FRESHNESS_ISSUE",
        }
        unknown_discoveries = set(discovery_focus).difference(known_discoveries)
        if unknown_discoveries:
            raise TribunalRoleHandbookError(f"unknown discovery focus:{role_id}:{sorted(unknown_discoveries)}")
        entry = RoleHandbookEntry(
            role_id=role_id,
            mission=str(spec.get("mission") or ""),
            mandatory_checks=tuple(str(x) for x in spec.get("mandatory_checks", ())),
            forbidden_moves=tuple(dict.fromkeys((*common_forbidden, *(str(x) for x in spec.get("forbidden_moves", ()))))),
            stop_conditions=tuple(dict.fromkeys((*common_stop_conditions, *(str(x) for x in spec.get("stop_conditions", ()))))),
            discovery_focus=discovery_focus,
            variants=variants,
        )
        entries[role_id] = entry

    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return TribunalRoleHandbook(
        handbook_id=str(raw.get("handbook_id") or ""),
        version=str(raw.get("version") or ""),
        entries=entries,
        handbook_hash="sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        source_path=path,
    )


def compile_role_instruction_pack(
    *,
    role_id: str,
    variant: RoleVariantKind,
    handbook: TribunalRoleHandbook,
    policy: TribunalCompositionPolicy,
) -> RoleInstructionPack:
    if role_id not in policy.roles:
        raise TribunalRoleHandbookError(f"role is not admitted by composition policy:{role_id}")
    entry = handbook.entries.get(role_id)
    if entry is None:
        raise TribunalRoleHandbookError(f"missing handbook entry:{role_id}")
    variant_spec = entry.variants.get(variant)
    if variant_spec is None:
        raise TribunalRoleHandbookError(f"missing handbook variant:{role_id}:{variant.value}")
    payload = {
        "role_id": role_id,
        "variant": variant.value,
        "handbook_version": handbook.version,
        "handbook_hash": handbook.handbook_hash,
        "mission": entry.mission,
        "objective": variant_spec.objective,
        "mandatory_checks": list(entry.mandatory_checks),
        "forbidden_moves": list(entry.forbidden_moves),
        "stop_conditions": list(entry.stop_conditions),
        "discovery_focus": list(entry.discovery_focus),
        "question_lenses": list(variant_spec.question_lenses),
        "expected_output_contract": policy.roles[role_id].expected_output_contract,
    }
    fp = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    return RoleInstructionPack(
        instruction_id=f"RHI-{fp[:20]}",
        role_id=role_id,
        variant=variant,
        handbook_version=handbook.version,
        handbook_hash=handbook.handbook_hash,
        instruction_fingerprint="sha256:" + fp,
        mission=entry.mission,
        objective=variant_spec.objective,
        mandatory_checks=entry.mandatory_checks,
        forbidden_moves=entry.forbidden_moves,
        stop_conditions=entry.stop_conditions,
        discovery_focus=entry.discovery_focus,
        question_lenses=variant_spec.question_lenses,
        expected_output_contract=policy.roles[role_id].expected_output_contract,
        metadata={
            "authority_boundary": "semantic guidance only; no role admission, tool/capability or evidence-view authority",
        },
    )




def validate_role_instruction_pack_integrity(pack: RoleInstructionPack) -> None:
    payload = {
        "role_id": pack.role_id,
        "variant": pack.variant.value,
        "handbook_version": pack.handbook_version,
        "handbook_hash": pack.handbook_hash,
        "mission": pack.mission,
        "objective": pack.objective,
        "mandatory_checks": list(pack.mandatory_checks),
        "forbidden_moves": list(pack.forbidden_moves),
        "stop_conditions": list(pack.stop_conditions),
        "discovery_focus": list(pack.discovery_focus),
        "question_lenses": list(pack.question_lenses),
        "expected_output_contract": pack.expected_output_contract,
    }
    fp = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    if pack.instruction_fingerprint != "sha256:" + fp or pack.instruction_id != f"RHI-{fp[:20]}":
        raise TribunalRoleHandbookError("RoleInstructionPack integrity mismatch")


def role_instruction_pack_to_dict(pack: RoleInstructionPack) -> dict[str, Any]:
    return {
        "schema_version": "role-instruction-pack/1.0",
        "instruction_id": pack.instruction_id,
        "role_id": pack.role_id,
        "variant": pack.variant.value,
        "handbook_version": pack.handbook_version,
        "handbook_hash": pack.handbook_hash,
        "instruction_fingerprint": pack.instruction_fingerprint,
        "mission": pack.mission,
        "objective": pack.objective,
        "mandatory_checks": list(pack.mandatory_checks),
        "forbidden_moves": list(pack.forbidden_moves),
        "stop_conditions": list(pack.stop_conditions),
        "discovery_focus": list(pack.discovery_focus),
        "question_lenses": list(pack.question_lenses),
        "expected_output_contract": pack.expected_output_contract,
        "metadata": dict(pack.metadata),
    }

def handbook_fill_requests_for_plan(
    *,
    plan: TribunalCompositionPlan,
    work_field: ReviewWorkField,
    lineage: TribunalLineageProfile,
    handbook: TribunalRoleHandbook,
    policy: TribunalCompositionPolicy,
    required_variant: RoleVariantKind = RoleVariantKind.FIRST_PASS,
) -> tuple[RoleHandbookFillRequest, ...]:
    refs = assessment_need_refs_for_work_field(work_field)
    need_by_ref = {(r.key, r.ordinal): n for r, n in zip(refs, work_field.assessment_needs, strict=True)}
    out: list[RoleHandbookFillRequest] = []
    for brief in plan.role_briefs:
        entry = handbook.entries.get(brief.role_id)
        if entry is not None and required_variant in entry.variants:
            continue
        needs = [need_by_ref[(ref.key, ref.ordinal)] for ref in brief.assigned_need_refs]
        axes = tuple(dict.fromkeys(n.axis.value for n in needs))
        methods = tuple(dict.fromkeys(m.value for n in needs for m in n.assessment_methods))
        payload = {
            "role_id": brief.role_id,
            "variant": required_variant.value,
            "need_refs": [(x.key, x.ordinal) for x in brief.assigned_need_refs],
            "axes": axes,
            "methods": methods,
            "lineage": sorted(lineage.tags),
            "output": brief.expected_output_contract,
            "policy_version": plan.policy_version,
            "policy_hash": plan.policy_hash,
        }
        key = "RHR-" + hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:20]
        out.append(RoleHandbookFillRequest(
            request_key=key,
            role_id=brief.role_id,
            missing_variant=required_variant,
            assigned_need_refs=brief.assigned_need_refs,
            uncertainty_axes=axes,
            assessment_methods=methods,
            lineage_tags=tuple(sorted(lineage.tags)),
            expected_output_contract=brief.expected_output_contract,
            policy_version=plan.policy_version,
            policy_hash=plan.policy_hash,
            reason_codes=("HANDBOOK_ENTRY_MISSING" if entry is None else "HANDBOOK_VARIANT_MISSING",),
        ))
    return tuple(out)


def draft_handbook_entry_skeleton(request: RoleHandbookFillRequest) -> dict[str, Any]:
    """Generate a non-admitted YAML-ready skeleton from code-owned facts.

    This is deliberately a proposal.  It contains no tools/capabilities/evidence
    visibility and cannot be loaded until a maintainer supplies semantic guidance
    and the resulting handbook passes validation.
    """
    lenses = [f"Assess {axis} using {method}" for axis in request.uncertainty_axes for method in request.assessment_methods]
    return {
        "role_id": request.role_id,
        "request_key": request.request_key,
        "mission": "TODO: define the scientific review mission for this admitted role.",
        "mandatory_checks": [f"TODO: check {axis}" for axis in request.uncertainty_axes],
        "discovery_focus": [],
        "variants": {
            request.missing_variant.value: {
                "objective": f"Assess assigned needs: {', '.join(request.uncertainty_axes) or 'unspecified uncertainty'}.",
                "question_lenses": lenses or ["TODO: define a discriminating question lens."],
            }
        },
        "source_request": {
            "assigned_need_refs": [{"key": x.key, "ordinal": x.ordinal} for x in request.assigned_need_refs],
            "assessment_methods": list(request.assessment_methods),
            "lineage_tags": list(request.lineage_tags),
            "expected_output_contract": request.expected_output_contract,
            "policy_version": request.policy_version,
            "policy_hash": request.policy_hash,
        },
        "admission_status": "PROPOSAL_ONLY",
    }
