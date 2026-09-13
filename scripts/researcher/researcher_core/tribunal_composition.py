"""R4.1 deterministic Tribunal composition.

R3.5 defines *what* must be assessed in ``ReviewWorkField``.  This module
compiles a deterministic, versioned and minimal-sufficient composition plan
that says *who* is allowed to assess each need and under which bounded view.
It does not run Tribunal dialogue and it never mutates knowledge state.
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
from researcher_core.r0.ids import EntityId
from researcher_core.research_planning import ResearchCardKind, ResearchDOM
from researcher_core.uncertainty_field import AssessmentMethod, AssessmentNeed, ReviewWorkField, UncertaintyAxis


class TribunalCompositionError(RuntimeError):
    pass


class EvidenceViewKind(StrEnum):
    FULL_RELEVANT = "FULL_RELEVANT"
    CLAIM_PLUS_SUPPORT = "CLAIM_PLUS_SUPPORT"
    CLAIM_PLUS_COUNTEREVIDENCE = "CLAIM_PLUS_COUNTEREVIDENCE"
    FRESH_CONTEXT = "FRESH_CONTEXT"
    METHOD_ONLY = "METHOD_ONLY"


class TribunalRoleKind(StrEnum):
    META = "META"
    DOMAIN = "DOMAIN"
    METHOD = "METHOD"


class CompositionReason(StrEnum):
    PERMANENT_POLICY_ROLE = "PERMANENT_POLICY_ROLE"
    AXIS_REQUIREMENT = "AXIS_REQUIREMENT"
    METHOD_REQUIREMENT = "METHOD_REQUIREMENT"
    LINEAGE_MATCH = "LINEAGE_MATCH"
    BLOCKING_NEED_COVERAGE = "BLOCKING_NEED_COVERAGE"
    MINIMAL_COVER_SELECTION = "MINIMAL_COVER_SELECTION"


@dataclass(frozen=True, slots=True)
class EvidenceViewPolicy:
    kind: EvidenceViewKind
    include_provenance: bool
    include_previous_conclusions: bool
    max_refs: int | None = None

    def __post_init__(self) -> None:
        if self.max_refs is not None and self.max_refs < 1:
            raise ValueError("max_refs must be positive when set")
        if self.kind is EvidenceViewKind.FRESH_CONTEXT and self.include_previous_conclusions:
            raise ValueError("FRESH_CONTEXT cannot include previous conclusions")


@dataclass(frozen=True, slots=True)
class TribunalRoleSpec:
    role_id: str
    label: str
    kind: TribunalRoleKind
    permanent: bool
    supported_axes: tuple[UncertaintyAxis, ...]
    supported_methods: tuple[AssessmentMethod, ...]
    lineage_tags: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    evidence_view: EvidenceViewPolicy
    expected_output_contract: str
    equivalence_group: str = ""
    selection_priority: int = 100

    def __post_init__(self) -> None:
        if not self.role_id or not self.label:
            raise ValueError("role_id and label are required")
        if not self.expected_output_contract:
            raise ValueError("expected_output_contract is required")
        if self.selection_priority < 0:
            raise ValueError("selection_priority must be non-negative")
        object.__setattr__(self, "equivalence_group", self.equivalence_group or self.role_id)
        object.__setattr__(self, "supported_axes", tuple(self.supported_axes))
        object.__setattr__(self, "supported_methods", tuple(self.supported_methods))
        object.__setattr__(self, "lineage_tags", tuple(_normalize_tag(x) for x in self.lineage_tags))
        object.__setattr__(self, "allowed_capabilities", tuple(self.allowed_capabilities))
        object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools))


@dataclass(frozen=True, slots=True)
class TribunalLineageProfile:
    research_directions: tuple[str, ...] = ()
    disciplinary_views: tuple[str, ...] = ()
    question_types: tuple[str, ...] = ()
    method_views: tuple[str, ...] = ()
    object_profile: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "research_directions",
            "disciplinary_views",
            "question_types",
            "method_views",
            "object_profile",
        ):
            object.__setattr__(self, name, tuple(_normalize_tag(x) for x in getattr(self, name)))

    @property
    def tags(self) -> frozenset[str]:
        return frozenset(
            (*self.research_directions, *self.disciplinary_views, *self.question_types, *self.method_views, *self.object_profile)
        )


@dataclass(frozen=True, slots=True)
class AssessmentNeedRef:
    """R4-local stable reference because R3.5 AssessmentNeed has no entity id.

    The key is content-addressed inside a concrete ReviewWorkField.  This avoids
    silently depending on list position.  A future canonical AssessmentNeed ID
    may replace this without changing assignment semantics.
    """

    key: str
    ordinal: int

    def __post_init__(self) -> None:
        if not self.key.startswith("ANR-"):
            raise ValueError("AssessmentNeedRef.key must use ANR- prefix")
        if self.ordinal < 0:
            raise ValueError("AssessmentNeedRef.ordinal must be non-negative")


@dataclass(frozen=True, slots=True)
class AssessmentAssignment:
    need_ref: AssessmentNeedRef
    role_ids: tuple[str, ...]
    reason_codes: tuple[CompositionReason, ...]

    def __post_init__(self) -> None:
        if not self.role_ids:
            raise ValueError("assignment requires at least one role")
        object.__setattr__(self, "role_ids", tuple(self.role_ids))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


@dataclass(frozen=True, slots=True)
class RoleBriefContract:
    role_id: str
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    evidence_view: EvidenceViewPolicy
    allowed_capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    expected_output_contract: str
    inquiry_depth: int
    token_budget: int

    def __post_init__(self) -> None:
        if self.inquiry_depth < 1 or self.token_budget < 1:
            raise ValueError("inquiry depth and token budget must be positive")
        object.__setattr__(self, "assigned_need_refs", tuple(self.assigned_need_refs))
        object.__setattr__(self, "allowed_capabilities", tuple(self.allowed_capabilities))
        object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools))


@dataclass(frozen=True, slots=True)
class TribunalCompositionRequest:
    work_field: ReviewWorkField
    lineage: TribunalLineageProfile


@dataclass(frozen=True, slots=True)
class TribunalCompositionPlan:
    work_field_id: EntityId
    permanent_roles: tuple[str, ...]
    dynamic_roles: tuple[str, ...]
    assignments: tuple[AssessmentAssignment, ...]
    role_briefs: tuple[RoleBriefContract, ...]
    policy_version: str
    policy_hash: str
    composition_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.work_field_id.namespace != "RWF":
            raise ValueError("work_field_id must use RWF prefix")
        object.__setattr__(self, "permanent_roles", tuple(self.permanent_roles))
        object.__setattr__(self, "dynamic_roles", tuple(self.dynamic_roles))
        object.__setattr__(self, "assignments", tuple(self.assignments))
        object.__setattr__(self, "role_briefs", tuple(self.role_briefs))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TribunalCompositionPolicy:
    policy_id: str
    version: str
    roles: Mapping[str, TribunalRoleSpec]
    permanent_role_ids: tuple[str, ...]
    axis_required_role_ids: Mapping[UncertaintyAxis, tuple[str, ...]]
    method_required_role_ids: Mapping[AssessmentMethod, tuple[str, ...]]
    inquiry_depth: int
    token_budget_per_role: int
    policy_hash: str
    source_path: Path


_REQUIRED_TOP = {
    "schema_version",
    "policy_id",
    "version",
    "defaults",
    "permanent_roles",
    "axis_requirements",
    "method_requirements",
    "roles",
}


def load_tribunal_composition_policy(path: Path) -> TribunalCompositionPolicy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TribunalCompositionError("Tribunal composition policy must be a mapping")
    missing = sorted(_REQUIRED_TOP.difference(raw))
    if missing:
        raise TribunalCompositionError(f"missing Tribunal policy keys: {missing}")
    roles_raw = raw["roles"]
    if not isinstance(roles_raw, dict) or not roles_raw:
        raise TribunalCompositionError("roles must be a non-empty mapping")

    roles: dict[str, TribunalRoleSpec] = {}
    for role_id, spec in roles_raw.items():
        if not isinstance(spec, dict):
            raise TribunalCompositionError(f"role {role_id!r} must be a mapping")
        view_raw = spec.get("evidence_view", {})
        view = EvidenceViewPolicy(
            kind=EvidenceViewKind(str(view_raw["kind"])),
            include_provenance=bool(view_raw.get("include_provenance", True)),
            include_previous_conclusions=bool(view_raw.get("include_previous_conclusions", False)),
            max_refs=None if view_raw.get("max_refs") is None else int(view_raw["max_refs"]),
        )
        roles[str(role_id)] = TribunalRoleSpec(
            role_id=str(role_id),
            label=str(spec["label"]),
            kind=TribunalRoleKind(str(spec["kind"])),
            permanent=bool(spec.get("permanent", False)),
            supported_axes=tuple(UncertaintyAxis(str(x)) for x in spec.get("supported_axes", ())),
            supported_methods=tuple(AssessmentMethod(str(x)) for x in spec.get("supported_methods", ())),
            lineage_tags=tuple(str(x) for x in spec.get("lineage_tags", ())),
            allowed_capabilities=tuple(str(x) for x in spec.get("allowed_capabilities", ())),
            allowed_tools=tuple(str(x) for x in spec.get("allowed_tools", ())),
            evidence_view=view,
            expected_output_contract=str(spec.get("expected_output_contract", "TribunalFinding/1.0")),
            equivalence_group=str(spec.get("equivalence_group", role_id)),
            selection_priority=int(spec.get("selection_priority", 100)),
        )

    permanent = tuple(str(x) for x in raw["permanent_roles"])
    _assert_known_roles(permanent, roles, "permanent_roles")
    for role_id in permanent:
        if not roles[role_id].permanent:
            raise TribunalCompositionError(f"permanent role {role_id!r} not marked permanent")

    axis_requirements = {
        UncertaintyAxis(str(axis)): tuple(str(x) for x in role_ids)
        for axis, role_ids in dict(raw["axis_requirements"]).items()
    }
    method_requirements = {
        AssessmentMethod(str(method)): tuple(str(x) for x in role_ids)
        for method, role_ids in dict(raw["method_requirements"]).items()
    }
    for axis, role_ids in axis_requirements.items():
        _assert_known_roles(role_ids, roles, f"axis {axis.value}")
    for method, role_ids in method_requirements.items():
        _assert_known_roles(role_ids, roles, f"method {method.value}")

    defaults = dict(raw["defaults"])
    _validate_declared_authority(roles, path.parent)
    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return TribunalCompositionPolicy(
        policy_id=str(raw["policy_id"]),
        version=str(raw["version"]),
        roles=MappingProxyType(roles),
        permanent_role_ids=permanent,
        axis_required_role_ids=MappingProxyType(axis_requirements),
        method_required_role_ids=MappingProxyType(method_requirements),
        inquiry_depth=int(defaults["inquiry_depth"]),
        token_budget_per_role=int(defaults["token_budget_per_role"]),
        policy_hash=digest,
        source_path=path,
    )


def lineage_profile_from_research_dom(
    dom: ResearchDOM,
    card_id: EntityId,
    *,
    object_profile: Sequence[str] = (),
) -> TribunalLineageProfile:
    """Compile the structural R1 lineage into the typed R4 routing profile.

    Card kind is authoritative for the dimension bucket.  Titles/dimension values
    become normalized routing tags; the compiler does not infer disciplines or
    methods from arbitrary prose outside the declared lineage.
    """
    directions: list[str] = []
    disciplines: list[str] = []
    question_types: list[str] = []
    methods: list[str] = []
    for card in dom.lineage(card_id):
        values = [card.title, *_flatten_dimension_values(card.dimensions)]
        if card.kind is ResearchCardKind.DIRECTION:
            directions.extend(values)
        elif card.kind is ResearchCardKind.DISCIPLINARY_VIEW:
            disciplines.extend(values)
        elif card.kind is ResearchCardKind.QUESTION:
            question_types.extend(values)
        elif card.kind is ResearchCardKind.METHOD_VIEW:
            methods.extend(values)
    return TribunalLineageProfile(
        research_directions=tuple(_dedupe_preserve(directions)),
        disciplinary_views=tuple(_dedupe_preserve(disciplines)),
        question_types=tuple(_dedupe_preserve(question_types)),
        method_views=tuple(_dedupe_preserve(methods)),
        object_profile=tuple(object_profile),
    )


def assessment_need_refs_for_work_field(field: ReviewWorkField) -> tuple[AssessmentNeedRef, ...]:
    """Public R4 bridge for deterministic references to R3.5 AssessmentNeeds.

    AssessmentNeed is not yet a canonical entity (TD-035).  R4.x consumers must
    derive references through this single helper rather than reimplementing the
    content hash independently.
    """
    return tuple(_need_ref(field.meta.id, i, need) for i, need in enumerate(field.assessment_needs))


def tribunal_composition_plan_to_dict(plan: TribunalCompositionPlan) -> dict[str, Any]:
    return {
        "schema_version": "tribunal-composition-plan/1.0",
        "work_field_id": str(plan.work_field_id),
        "permanent_roles": list(plan.permanent_roles),
        "dynamic_roles": list(plan.dynamic_roles),
        "assignments": [
            {
                "need_ref": {"key": item.need_ref.key, "ordinal": item.need_ref.ordinal},
                "role_ids": list(item.role_ids),
                "reason_codes": [x.value for x in item.reason_codes],
            }
            for item in plan.assignments
        ],
        "role_briefs": [
            {
                "role_id": brief.role_id,
                "assigned_need_refs": [
                    {"key": ref.key, "ordinal": ref.ordinal} for ref in brief.assigned_need_refs
                ],
                "evidence_view": {
                    "kind": brief.evidence_view.kind.value,
                    "include_provenance": brief.evidence_view.include_provenance,
                    "include_previous_conclusions": brief.evidence_view.include_previous_conclusions,
                    "max_refs": brief.evidence_view.max_refs,
                },
                "allowed_capabilities": list(brief.allowed_capabilities),
                "allowed_tools": list(brief.allowed_tools),
                "expected_output_contract": brief.expected_output_contract,
                "inquiry_depth": brief.inquiry_depth,
                "token_budget": brief.token_budget,
            }
            for brief in plan.role_briefs
        ],
        "policy_version": plan.policy_version,
        "policy_hash": plan.policy_hash,
        "composition_fingerprint": plan.composition_fingerprint,
        "metadata": dict(plan.metadata),
    }


def _validate_declared_authority(roles: Mapping[str, TribunalRoleSpec], config_dir: Path) -> None:
    capabilities_path = config_dir / "capabilities_authority.json"
    tools_path = config_dir / "logical_tools.json"
    if not capabilities_path.exists() or not tools_path.exists():
        raise TribunalCompositionError("central capability/tool authority files are required for Tribunal policy validation")
    capability_raw = json.loads(capabilities_path.read_text(encoding="utf-8"))
    tool_raw = json.loads(tools_path.read_text(encoding="utf-8"))
    known_capabilities = frozenset(dict(capability_raw.get("capabilities", {})))
    known_tools = frozenset(dict(tool_raw.get("tools", {})))
    for role in roles.values():
        unknown_capabilities = sorted(set(role.allowed_capabilities).difference(known_capabilities))
        unknown_tools = sorted(set(role.allowed_tools).difference(known_tools))
        if unknown_capabilities:
            raise TribunalCompositionError(f"role {role.role_id!r} declares unknown capabilities: {unknown_capabilities}")
        if unknown_tools:
            raise TribunalCompositionError(f"role {role.role_id!r} declares unknown logical tools: {unknown_tools}")


def _flatten_dimension_values(value: Mapping[str, Any]) -> list[str]:
    flattened: list[str] = []
    for key in sorted(value):
        item = value[key]
        if isinstance(item, str):
            flattened.append(item)
        elif isinstance(item, (tuple, list, frozenset, set)):
            flattened.extend(str(x) for x in item)
        elif item is not None and isinstance(item, (int, float, bool)):
            flattened.append(str(item))
    return flattened


def compile_tribunal_composition(
    request: TribunalCompositionRequest,
    policy: TribunalCompositionPolicy,
) -> TribunalCompositionPlan:
    field = request.work_field
    need_refs = assessment_need_refs_for_work_field(field)
    permanent = tuple(policy.permanent_role_ids)
    selected_dynamic: list[str] = []
    assignments: list[AssessmentAssignment] = []

    for need_ref, need in zip(need_refs, field.assessment_needs, strict=True):
        required = _required_roles_for_need(need, request.lineage, policy)
        candidates = _capable_roles_for_need(need, request.lineage, policy)

        chosen: list[str] = [role_id for role_id in permanent if role_id in candidates]
        reason_codes: list[CompositionReason] = []
        if chosen:
            reason_codes.append(CompositionReason.PERMANENT_POLICY_ROLE)

        for role_id in required:
            if role_id in candidates and role_id not in chosen:
                chosen.append(role_id)
                if role_id not in permanent and role_id not in selected_dynamic:
                    selected_dynamic.append(role_id)

        if need.axis in policy.axis_required_role_ids:
            reason_codes.append(CompositionReason.AXIS_REQUIREMENT)
        if any(method in policy.method_required_role_ids for method in need.assessment_methods):
            reason_codes.append(CompositionReason.METHOD_REQUIREMENT)
        if any(policy.roles[x].lineage_tags and request.lineage.tags.intersection(policy.roles[x].lineage_tags) for x in chosen):
            reason_codes.append(CompositionReason.LINEAGE_MATCH)

        if not chosen:
            if need.blocking:
                raise TribunalCompositionError(f"UNASSIGNED_NEED:{need_ref.key}")
            fallback = _best_candidate(candidates, need, request.lineage, policy)
            if fallback is not None:
                chosen.append(fallback)
                if fallback not in permanent and fallback not in selected_dynamic:
                    selected_dynamic.append(fallback)

        if need.blocking:
            specialized = [x for x in chosen if not policy.roles[x].permanent]
            if required and not specialized and all(x in permanent for x in required):
                specialized = []
            if required and not any(x in chosen for x in required):
                raise TribunalCompositionError(f"UNASSIGNED_NEED:{need_ref.key}")
            reason_codes.append(CompositionReason.BLOCKING_NEED_COVERAGE)

        chosen = _dedupe_preserve(chosen)
        if not chosen and need.blocking:
            raise TribunalCompositionError(f"UNASSIGNED_NEED:{need_ref.key}")
        if chosen:
            reason_codes.append(CompositionReason.MINIMAL_COVER_SELECTION)
            assignments.append(AssessmentAssignment(need_ref, tuple(chosen), tuple(_dedupe_preserve(reason_codes))))

    selected_roles = _dedupe_preserve([*permanent, *selected_dynamic])
    assigned_by_role: dict[str, list[AssessmentNeedRef]] = {role_id: [] for role_id in selected_roles}
    for assignment in assignments:
        for role_id in assignment.role_ids:
            assigned_by_role.setdefault(role_id, []).append(assignment.need_ref)

    briefs = tuple(
        RoleBriefContract(
            role_id=role_id,
            assigned_need_refs=tuple(assigned_by_role.get(role_id, ())),
            evidence_view=policy.roles[role_id].evidence_view,
            allowed_capabilities=policy.roles[role_id].allowed_capabilities,
            allowed_tools=policy.roles[role_id].allowed_tools,
            expected_output_contract=policy.roles[role_id].expected_output_contract,
            inquiry_depth=policy.inquiry_depth,
            token_budget=policy.token_budget_per_role,
        )
        for role_id in selected_roles
        if assigned_by_role.get(role_id)
    )

    fingerprint = _composition_fingerprint(
        work_field_id=field.meta.id,
        permanent_roles=permanent,
        dynamic_roles=tuple(selected_dynamic),
        assignments=tuple(assignments),
        role_briefs=briefs,
        policy_version=policy.version,
        policy_hash=policy.policy_hash,
    )
    return TribunalCompositionPlan(
        work_field_id=field.meta.id,
        permanent_roles=permanent,
        dynamic_roles=tuple(selected_dynamic),
        assignments=tuple(assignments),
        role_briefs=briefs,
        policy_version=policy.version,
        policy_hash=policy.policy_hash,
        composition_fingerprint=fingerprint,
        metadata={
            "authority_boundary": "composition only; no Claim/GraphEdge/Gap/truth mutation",
            "assessment_need_identity": "R4 content-addressed need ref; canonical R3 AssessmentNeed entity id deferred",
        },
    )


def validate_tribunal_composition_plan_integrity(plan: TribunalCompositionPlan) -> None:
    """Fail closed if a persisted/transferred plan was altered after compilation.

    R4.2 treats TribunalCompositionPlan as a control-plane authority object.  The
    fingerprint therefore covers assignments *and* role briefs/evidence views,
    not merely the selected role names.
    """
    selected_roles = set((*plan.permanent_roles, *plan.dynamic_roles))
    assignment_by_need: dict[tuple[str, int], set[str]] = {}
    for assignment in plan.assignments:
        key = (assignment.need_ref.key, assignment.need_ref.ordinal)
        if key in assignment_by_need:
            raise TribunalCompositionError(f"duplicate assignment for AssessmentNeedRef:{key}")
        unknown = set(assignment.role_ids).difference(selected_roles)
        if unknown:
            raise TribunalCompositionError(f"assignment references unselected roles:{sorted(unknown)}")
        assignment_by_need[key] = set(assignment.role_ids)

    briefs_by_role: dict[str, RoleBriefContract] = {}
    for brief in plan.role_briefs:
        if brief.role_id in briefs_by_role:
            raise TribunalCompositionError(f"duplicate role brief:{brief.role_id}")
        if brief.role_id not in selected_roles:
            raise TribunalCompositionError(f"role brief references unselected role:{brief.role_id}")
        briefs_by_role[brief.role_id] = brief
        for ref in brief.assigned_need_refs:
            roles = assignment_by_need.get((ref.key, ref.ordinal))
            if roles is None or brief.role_id not in roles:
                raise TribunalCompositionError(
                    f"role brief widens assignment:{brief.role_id}:{ref.key}:{ref.ordinal}"
                )

    for assignment in plan.assignments:
        for role_id in assignment.role_ids:
            brief = briefs_by_role.get(role_id)
            if brief is None or assignment.need_ref not in brief.assigned_need_refs:
                raise TribunalCompositionError(
                    f"assignment missing matching role brief:{role_id}:{assignment.need_ref.key}:{assignment.need_ref.ordinal}"
                )

    expected = _composition_fingerprint(
        work_field_id=plan.work_field_id,
        permanent_roles=plan.permanent_roles,
        dynamic_roles=plan.dynamic_roles,
        assignments=plan.assignments,
        role_briefs=plan.role_briefs,
        policy_version=plan.policy_version,
        policy_hash=plan.policy_hash,
    )
    if expected != plan.composition_fingerprint:
        raise TribunalCompositionError("TribunalCompositionPlan fingerprint mismatch")


def _composition_fingerprint(
    *,
    work_field_id: EntityId,
    permanent_roles: Sequence[str],
    dynamic_roles: Sequence[str],
    assignments: Sequence[AssessmentAssignment],
    role_briefs: Sequence[RoleBriefContract],
    policy_version: str,
    policy_hash: str,
) -> str:
    payload = {
        "rwf": str(work_field_id),
        "policy_version": policy_version,
        "policy_hash": policy_hash,
        "permanent": list(permanent_roles),
        "dynamic": list(dynamic_roles),
        "assignments": [
            {
                "need": item.need_ref.key,
                "ordinal": item.need_ref.ordinal,
                "roles": list(item.role_ids),
                "reasons": [reason.value for reason in item.reason_codes],
            }
            for item in assignments
        ],
        "role_briefs": [
            {
                "role_id": brief.role_id,
                "needs": [
                    {"key": ref.key, "ordinal": ref.ordinal}
                    for ref in brief.assigned_need_refs
                ],
                "evidence_view": {
                    "kind": brief.evidence_view.kind.value,
                    "include_provenance": brief.evidence_view.include_provenance,
                    "include_previous_conclusions": brief.evidence_view.include_previous_conclusions,
                    "max_refs": brief.evidence_view.max_refs,
                },
                "capabilities": list(brief.allowed_capabilities),
                "tools": list(brief.allowed_tools),
                "output": brief.expected_output_contract,
                "inquiry_depth": brief.inquiry_depth,
                "token_budget": brief.token_budget,
            }
            for brief in role_briefs
        ],
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _required_roles_for_need(
    need: AssessmentNeed,
    lineage: TribunalLineageProfile,
    policy: TribunalCompositionPolicy,
) -> tuple[str, ...]:
    required: list[str] = list(policy.axis_required_role_ids.get(need.axis, ()))
    for method in need.assessment_methods:
        required.extend(policy.method_required_role_ids.get(method, ()))
    # Domain/method roles are activated only when their declared lineage tags are present.
    for role_id, role in policy.roles.items():
        if role.permanent or not role.lineage_tags:
            continue
        if lineage.tags.intersection(role.lineage_tags) and _role_supports_need(role, need):
            required.append(role_id)
    return _dedupe_role_equivalence(required, policy)


def _capable_roles_for_need(
    need: AssessmentNeed,
    lineage: TribunalLineageProfile,
    policy: TribunalCompositionPolicy,
) -> tuple[str, ...]:
    capable = [
        role_id for role_id, role in policy.roles.items()
        if _role_supports_need(role, need)
        and (not role.lineage_tags or role.permanent or bool(lineage.tags.intersection(role.lineage_tags)))
    ]
    return _dedupe_role_equivalence(capable, policy)


def _role_supports_need(role: TribunalRoleSpec, need: AssessmentNeed) -> bool:
    return need.axis in role.supported_axes or bool(set(need.assessment_methods).intersection(role.supported_methods))


def _dedupe_role_equivalence(
    role_ids: Sequence[str], policy: TribunalCompositionPolicy
) -> tuple[str, ...]:
    by_group: dict[str, list[str]] = {}
    for role_id in _dedupe_preserve(role_ids):
        role = policy.roles[role_id]
        by_group.setdefault(role.equivalence_group, []).append(role_id)
    selected: list[str] = []
    for group in by_group:
        candidates = by_group[group]
        candidates.sort(key=lambda x: (policy.roles[x].selection_priority, x))
        selected.append(candidates[0])
    return tuple(selected)


def _best_candidate(
    candidates: Sequence[str],
    need: AssessmentNeed,
    lineage: TribunalLineageProfile,
    policy: TribunalCompositionPolicy,
) -> str | None:
    if not candidates:
        return None
    def score(role_id: str) -> tuple[int, int, str]:
        role = policy.roles[role_id]
        coverage = int(need.axis in role.supported_axes) * 4 + len(set(need.assessment_methods).intersection(role.supported_methods)) * 2
        lineage_score = len(lineage.tags.intersection(role.lineage_tags))
        return (-coverage, -lineage_score, role_id)
    return sorted(candidates, key=score)[0]


def _need_ref(work_field_id: EntityId, ordinal: int, need: AssessmentNeed) -> AssessmentNeedRef:
    raw = {
        "rwf": str(work_field_id),
        "axis": need.axis.value,
        "level": need.level.value,
        "blocking": need.blocking,
        "targets": [str(x) for x in need.target_refs],
        "sources": [str(x) for x in need.source_refs],
        "question": need.question,
        "methods": [x.value for x in need.assessment_methods],
        "criteria": list(need.completion_criteria),
        "reasons": list(need.reason_codes),
    }
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:20]
    return AssessmentNeedRef(key=f"ANR-{digest}", ordinal=ordinal)


def _normalize_tag(value: str) -> str:
    return "_".join(str(value).strip().lower().replace("-", " ").split())


def _assert_known_roles(role_ids: Sequence[str], roles: Mapping[str, TribunalRoleSpec], where: str) -> None:
    unknown = sorted(set(role_ids).difference(roles))
    if unknown:
        raise TribunalCompositionError(f"unknown role(s) in {where}: {unknown}")


def _dedupe_preserve(values: Sequence[Any]) -> list[Any]:
    return list(dict.fromkeys(values))
