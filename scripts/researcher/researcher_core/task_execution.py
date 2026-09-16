"""R3 task execution and peer-delegation contracts.

ResearchDOM decides *what* should be executed.  This module compiles one
executable leaf into an explicit execution plan and either calls an already
registered local capsule or creates a typed peer delegation on top of the
existing jobs/job_ctl runtime.

Execution is deliberately not epistemic admission.  Observations and peer
artifacts are provenance-bearing outputs; Claim/Evidence state is changed only
by later validators/reducers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from scripts.jobs import job_ctl
from researcher_core.capsules import (
    CapsuleObservation,
    CapsuleRequest,
    InMemoryCapabilityRegistry,
    assert_capsule_observation_is_untrusted,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.research_planning import (
    ResearchCardKind,
    ResearchCardStatus,
    ResearchDOM,
    ResearchPatch,
    SetCardStatusOperation,
    apply_research_patch,
)


class TaskExecutionError(ValueError):
    pass


class ExecutionOwner(StrEnum):
    RESEARCHER = "RESEARCHER"
    CODER = "CODER"
    WRITER = "WRITER"


class ExecutionMode(StrEnum):
    LOCAL = "LOCAL"
    PEER_DELEGATION = "PEER_DELEGATION"


class DelegationMode(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    DETACHED = "detached"


class TaskExecutionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class TaskExecutionPlan:
    meta: EntityMeta
    request_id: EntityId
    source_card_id: EntityId
    source_card_revision: int
    capability: str
    owner: ExecutionOwner
    mode: ExecutionMode
    route_id: str | None = None
    delegation_mode: DelegationMode = DelegationMode.REQUIRED
    input_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "TEP":
            raise ValueError("task execution plan id must use TEP prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if self.source_card_id.namespace != "RCD":
            raise ValueError("source_card_id must use RCD prefix")
        if self.source_card_revision < 1:
            raise ValueError("source_card_revision must be positive")
        if not self.capability.strip():
            raise ValueError("capability is required")
        if self.mode == ExecutionMode.LOCAL and self.owner != ExecutionOwner.RESEARCHER:
            raise ValueError("LOCAL execution owner must be RESEARCHER")
        if self.mode == ExecutionMode.PEER_DELEGATION and self.owner == ExecutionOwner.RESEARCHER:
            raise ValueError("PEER_DELEGATION owner must be CODER or WRITER")
        object.__setattr__(self, "input_payload", _deep_freeze(self.input_payload))


@dataclass(frozen=True, slots=True)
class DelegationRequest:
    meta: EntityMeta
    execution_plan_id: EntityId
    source_card_id: EntityId
    parent_job_id: str
    child_job_id: str
    target_peer: ExecutionOwner
    capability: str
    route_id: str | None
    mode: DelegationMode
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "DLG":
            raise ValueError("delegation request id must use DLG prefix")
        if self.execution_plan_id.namespace != "TEP":
            raise ValueError("execution_plan_id must use TEP prefix")
        if self.source_card_id.namespace != "RCD":
            raise ValueError("source_card_id must use RCD prefix")
        if self.target_peer not in {ExecutionOwner.CODER, ExecutionOwner.WRITER}:
            raise ValueError("target_peer must be CODER or WRITER")
        if not self.parent_job_id or not self.child_job_id:
            raise ValueError("parent_job_id and child_job_id are required")
        if not self.capability.strip() and not (self.route_id or "").strip():
            raise ValueError("peer delegation requires capability or explicit route_id")
        object.__setattr__(self, "payload", _deep_freeze(self.payload))


@dataclass(frozen=True, slots=True)
class TaskExecutionResult:
    meta: EntityMeta
    execution_plan_id: EntityId
    source_card_id: EntityId
    active_card_revision: int
    status: TaskExecutionStatus
    owner: ExecutionOwner
    capability: str
    observation: CapsuleObservation | None = None
    artifact_refs: tuple[str, ...] = ()
    child_job_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "TER":
            raise ValueError("task execution result id must use TER prefix")
        if self.execution_plan_id.namespace != "TEP":
            raise ValueError("execution_plan_id must use TEP prefix")
        if self.source_card_id.namespace != "RCD":
            raise ValueError("source_card_id must use RCD prefix")
        if self.active_card_revision < 1:
            raise ValueError("active_card_revision must be positive")
        if self.status == TaskExecutionStatus.SUCCEEDED and self.reason:
            raise ValueError("successful result must not carry failure reason")
        object.__setattr__(self, "artifact_refs", tuple(dict.fromkeys(self.artifact_refs)))


def compile_task_execution_plan(
    *,
    dom: ResearchDOM,
    card_id: EntityId,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
    local_capabilities: Sequence[str] = (),
) -> TaskExecutionPlan:
    """Compile one authoritative leaf card into a deterministic execution plan."""
    if card_id not in dom.cards:
        raise TaskExecutionError("task card does not exist")
    card = dom.cards[card_id]
    if card.kind not in {ResearchCardKind.TASK, ResearchCardKind.DELEGATION}:
        raise TaskExecutionError("only TASK/DELEGATION cards are executable")
    if dom.children_of(card_id):
        raise TaskExecutionError("only leaf TASK/DELEGATION cards are executable")
    if card.status not in {ResearchCardStatus.PLANNED, ResearchCardStatus.READY}:
        raise TaskExecutionError(f"card cannot start execution from {card.status.value}")

    dims = dict(card.dimensions)
    capability = str(dims.get("capability") or "").strip()
    delegation_target = str(dims.get("delegation_target") or "").strip()
    raw_owner = str(dims.get("execution_owner") or delegation_target or "").strip().upper()
    route_id = str(dims.get("route_id") or "").strip() or None
    raw_mode = str(dims.get("delegation_mode") or DelegationMode.REQUIRED.value).strip().lower()
    try:
        delegation_mode = DelegationMode(raw_mode)
    except ValueError as exc:
        raise TaskExecutionError(f"unsupported delegation_mode: {raw_mode}") from exc

    if raw_owner:
        aliases = {"CODE": "CODER", "CODER": "CODER", "WRITER": "WRITER", "RESEARCHER": "RESEARCHER", "RESEARCH": "RESEARCHER"}
        normalized = aliases.get(raw_owner)
        if normalized is None:
            raise TaskExecutionError(f"unsupported execution_owner/delegation_target: {raw_owner}")
        owner = ExecutionOwner(normalized)
    elif capability and capability in set(local_capabilities):
        owner = ExecutionOwner.RESEARCHER
    elif capability:
        # Do not silently delegate merely because a local provider is absent.
        raise TaskExecutionError("no local provider and no explicit peer delegation target")
    else:
        raise TaskExecutionError("executable card lacks capability/delegation_target")

    if owner == ExecutionOwner.RESEARCHER:
        if not capability:
            raise TaskExecutionError("local execution requires capability")
        if capability not in set(local_capabilities):
            raise TaskExecutionError(f"no local provider for capability: {capability}")
        mode = ExecutionMode.LOCAL
    else:
        if not capability and not route_id:
            raise TaskExecutionError("peer delegation requires capability or explicit route_id")
        mode = ExecutionMode.PEER_DELEGATION

    input_payload = dims.get("input_payload")
    if input_payload is None:
        input_payload = {
            "title": card.title,
            "description": card.description,
            "dimensions": dims,
        }
    if not isinstance(input_payload, Mapping):
        raise TaskExecutionError("input_payload must be a mapping")

    return TaskExecutionPlan(
        meta=EntityMeta(id_factory.new("TEP"), "task-execution-plan/1.0", 1, card.meta.run_id, created_at, actor),
        request_id=card.request_id,
        source_card_id=card.meta.id,
        source_card_revision=card.meta.revision,
        capability=capability or f"route:{route_id}",
        owner=owner,
        mode=mode,
        route_id=route_id,
        delegation_mode=delegation_mode,
        input_payload=input_payload,
    )


def start_task_execution(
    *,
    dom: ResearchDOM,
    plan: TaskExecutionPlan,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    timestamp: datetime,
    causation_id: EntityId,
    correlation_id: EntityId,
):
    """Revision-checked source-card transition into ACTIVE."""
    if plan.request_id != dom.request_id:
        raise TaskExecutionError("execution plan belongs to a different request")
    card = dom.cards.get(plan.source_card_id)
    if card is None or card.meta.revision != plan.source_card_revision:
        raise TaskExecutionError("stale execution plan card revision")
    if card.status not in {ResearchCardStatus.PLANNED, ResearchCardStatus.READY}:
        raise TaskExecutionError(f"card cannot start from {card.status.value}")
    patch = ResearchPatch(
        id=id_factory.new("RPT"), request_id=dom.request_id, expected_dom_revision=dom.meta.revision,
        operations=(SetCardStatusOperation(card.meta.id, card.meta.revision, ResearchCardStatus.ACTIVE),),
    )
    return apply_research_patch(dom, patch, actor, id_factory, timestamp, causation_id, correlation_id)


def execute_local_task(
    *,
    plan: TaskExecutionPlan,
    active_card_revision: int,
    registry: InMemoryCapabilityRegistry,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> TaskExecutionResult:
    if plan.mode != ExecutionMode.LOCAL:
        raise TaskExecutionError("plan is not LOCAL")
    provider = registry.provider_for(plan.capability)
    request = CapsuleRequest(
        request_id=id_factory.new("OPR"), run_id=plan.meta.run_id,
        capability=plan.capability, actor=actor, payload=plan.input_payload,
    )
    observation = provider.run(request)
    assert_capsule_observation_is_untrusted(observation)
    return TaskExecutionResult(
        meta=EntityMeta(id_factory.new("TER"), "task-execution-result/1.0", 1, plan.meta.run_id, created_at, actor),
        execution_plan_id=plan.meta.id,
        source_card_id=plan.source_card_id,
        active_card_revision=active_card_revision,
        status=TaskExecutionStatus.SUCCEEDED,
        owner=plan.owner,
        capability=plan.capability,
        observation=observation,
    )


def build_delegation_request(
    *,
    plan: TaskExecutionPlan,
    parent_job_id: str,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> DelegationRequest:
    if plan.mode != ExecutionMode.PEER_DELEGATION:
        raise TaskExecutionError("plan is not PEER_DELEGATION")
    delegation_id = id_factory.new("DLG")
    child_job_id = f"{plan.owner.value.lower()}-{str(delegation_id)}"
    return DelegationRequest(
        meta=EntityMeta(delegation_id, "delegation-request/1.0", 1, plan.meta.run_id, created_at, actor),
        execution_plan_id=plan.meta.id,
        source_card_id=plan.source_card_id,
        parent_job_id=parent_job_id,
        child_job_id=child_job_id,
        target_peer=plan.owner,
        capability=plan.capability,
        route_id=plan.route_id,
        mode=plan.delegation_mode,
        payload=plan.input_payload,
    )


def _jsonable(value: Any):
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


class JobCtlDelegationAdapter:
    """Thin infrastructure adapter over the existing JSON Job/Child runtime."""

    def __init__(self, state_dir: str | Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def child_state_path(self, child_job_id: str) -> Path:
        safe = child_job_id.replace("/", "_")
        return self.state_dir / f"{safe}.json"

    def start(self, *, parent_state_path: str | Path, request: DelegationRequest) -> Path:
        parent_path = Path(parent_state_path)
        parent = job_ctl.load(parent_path)
        if parent.get("job_id") != request.parent_job_id:
            raise TaskExecutionError("parent Job id does not match DelegationRequest")
        if any(c.get("child_id") == request.child_job_id for c in parent.get("children", ())):
            raise TaskExecutionError("delegated child already exists")

        child_path = self.child_state_path(request.child_job_id)
        if child_path.exists():
            raise TaskExecutionError("child Job state already exists")
        contract = {
            "schema": "peer-delegation/1.0",
            "delegation_request_id": str(request.meta.id),
            "execution_plan_id": str(request.execution_plan_id),
            "source_card_id": str(request.source_card_id),
            "target_peer": request.target_peer.value,
            "capability": request.capability,
            "route_id": request.route_id,
            "payload": _jsonable(request.payload),
        }
        child = job_ctl.create(request.child_job_id, contract, ["execute"])
        job_ctl.save(child, child_path)

        record = {
            "child_id": request.child_job_id,
            "mode": request.mode.value,
            "external_task_id": str(request.meta.id),
            "status": "RUNNING",
            "created_at": job_ctl.now(),
        }
        parent["children"].append(record)
        job_ctl.event(parent, "CHILD_ADDED", record)
        job_ctl.save(parent, parent_path)
        return child_path

    def finish(
        self,
        *,
        parent_state_path: str | Path,
        request: DelegationRequest,
        child_status: str,
        active_card_revision: int,
        id_factory: EntityIdFactory,
        actor: ActorRef,
        created_at: datetime,
        artifact_refs: Sequence[str] = (),
    ) -> TaskExecutionResult:
        if child_status not in job_ctl.TERMINAL_ATTEMPT:
            raise TaskExecutionError(f"unsupported child terminal status: {child_status}")
        parent_path = Path(parent_state_path)
        parent = job_ctl.load(parent_path)
        child_record = job_ctl.child_by(parent, request.child_job_id)
        if child_record.get("status") != "RUNNING":
            raise TaskExecutionError("delegated child is already terminal")
        child_record["status"] = child_status
        child_record["finished_at"] = job_ctl.now()
        job_ctl.event(parent, "CHILD_FINISHED", {"child_id": request.child_job_id, "status": child_status})
        job_ctl.save(parent, parent_path)

        child_path = self.child_state_path(request.child_job_id)
        child = job_ctl.load(child_path)
        child["stages"]["execute"]["status"] = "COMPLETED" if child_status == "COMPLETED" else "FAILED"
        child["stages"]["execute"]["updated_at"] = job_ctl.now()
        child["status"] = "COMPLETED" if child_status == "COMPLETED" else "FAILED_NO_OUTPUT"
        for artifact_ref in artifact_refs:
            child["artifacts"].setdefault(artifact_ref, {"path": artifact_ref, "sha256": None, "registered_at": job_ctl.now()})
        job_ctl.event(child, "JOB_COMPLETED" if child_status == "COMPLETED" else "JOB_FAILED", {"status": child_status, "artifacts": list(artifact_refs)})
        job_ctl.save(child, child_path)

        status = TaskExecutionStatus.SUCCEEDED if child_status == "COMPLETED" else TaskExecutionStatus.FAILED
        return TaskExecutionResult(
            meta=EntityMeta(id_factory.new("TER"), "task-execution-result/1.0", 1, request.meta.run_id, created_at, actor),
            execution_plan_id=request.execution_plan_id,
            source_card_id=request.source_card_id,
            active_card_revision=active_card_revision,
            status=status,
            owner=request.target_peer,
            capability=request.capability,
            artifact_refs=tuple(artifact_refs),
            child_job_id=request.child_job_id,
            reason=None if status == TaskExecutionStatus.SUCCEEDED else f"peer child ended as {child_status}",
        )


def finish_task_execution(
    *,
    dom: ResearchDOM,
    plan: TaskExecutionPlan,
    result: TaskExecutionResult,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    timestamp: datetime,
    causation_id: EntityId,
    correlation_id: EntityId,
):
    """Project terminal execution into ResearchDOM card state only.

    This does not admit any claims/evidence from the result.
    """
    if result.execution_plan_id != plan.meta.id or result.source_card_id != plan.source_card_id:
        raise TaskExecutionError("execution result does not belong to plan")
    card = dom.cards.get(plan.source_card_id)
    if card is None:
        raise TaskExecutionError("source card no longer exists")
    expected_active_revision = plan.source_card_revision + 1
    if result.active_card_revision != expected_active_revision:
        raise TaskExecutionError("execution result carries stale ACTIVE card revision")
    if card.meta.revision != expected_active_revision or card.status != ResearchCardStatus.ACTIVE:
        raise TaskExecutionError("source card is not the expected ACTIVE execution revision")
    target_status = ResearchCardStatus.COMPLETED if result.status == TaskExecutionStatus.SUCCEEDED else ResearchCardStatus.BLOCKED
    patch = ResearchPatch(
        id=id_factory.new("RPT"), request_id=dom.request_id, expected_dom_revision=dom.meta.revision,
        operations=(SetCardStatusOperation(card.meta.id, card.meta.revision, target_status),),
    )
    return apply_research_patch(dom, patch, actor, id_factory, timestamp, causation_id, correlation_id)



def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id), "schema_version": meta.schema_version, "revision": meta.revision,
        "run_id": str(meta.run_id), "created_at": meta.created_at.isoformat(),
        "created_by": {"actor_type": meta.created_by.actor_type, "actor_id": meta.created_by.actor_id},
    }


def _meta_from_dict(raw: Mapping[str, Any]) -> EntityMeta:
    actor_raw = raw["created_by"]
    return EntityMeta(
        EntityId(str(raw["id"])), str(raw["schema_version"]), int(raw["revision"]), EntityId(str(raw["run_id"])),
        datetime.fromisoformat(str(raw["created_at"])), ActorRef(str(actor_raw["actor_type"]), str(actor_raw["actor_id"])),
    )


def task_execution_plan_to_dict(plan: TaskExecutionPlan) -> dict[str, Any]:
    return {
        "schema_version": "task-execution-plan/1.0", "meta": _meta_to_dict(plan.meta),
        "request_id": str(plan.request_id), "source_card_id": str(plan.source_card_id),
        "source_card_revision": plan.source_card_revision, "capability": plan.capability,
        "owner": plan.owner.value, "mode": plan.mode.value, "route_id": plan.route_id,
        "delegation_mode": plan.delegation_mode.value, "input_payload": _jsonable(plan.input_payload),
    }


def task_execution_plan_from_dict(raw: Mapping[str, Any]) -> TaskExecutionPlan:
    return TaskExecutionPlan(
        meta=_meta_from_dict(raw["meta"]), request_id=EntityId(str(raw["request_id"])),
        source_card_id=EntityId(str(raw["source_card_id"])), source_card_revision=int(raw["source_card_revision"]),
        capability=str(raw["capability"]), owner=ExecutionOwner(str(raw["owner"])), mode=ExecutionMode(str(raw["mode"])),
        route_id=raw.get("route_id") or None, delegation_mode=DelegationMode(str(raw["delegation_mode"])),
        input_payload=dict(raw.get("input_payload", {})),
    )


def delegation_request_to_dict(request: DelegationRequest) -> dict[str, Any]:
    return {
        "schema_version": "delegation-request/1.0", "meta": _meta_to_dict(request.meta),
        "execution_plan_id": str(request.execution_plan_id), "source_card_id": str(request.source_card_id),
        "parent_job_id": request.parent_job_id, "child_job_id": request.child_job_id,
        "target_peer": request.target_peer.value, "capability": request.capability, "route_id": request.route_id,
        "mode": request.mode.value, "payload": _jsonable(request.payload),
    }


def delegation_request_from_dict(raw: Mapping[str, Any]) -> DelegationRequest:
    return DelegationRequest(
        meta=_meta_from_dict(raw["meta"]), execution_plan_id=EntityId(str(raw["execution_plan_id"])),
        source_card_id=EntityId(str(raw["source_card_id"])), parent_job_id=str(raw["parent_job_id"]),
        child_job_id=str(raw["child_job_id"]), target_peer=ExecutionOwner(str(raw["target_peer"])),
        capability=str(raw["capability"]), route_id=raw.get("route_id") or None,
        mode=DelegationMode(str(raw["mode"])), payload=dict(raw.get("payload", {})),
    )


def _observation_to_dict(observation: CapsuleObservation | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "request_id": str(observation.request_id), "capsule_id": observation.capsule_id,
        "capability": observation.capability, "output_schema_version": observation.output_schema_version,
        "payload": _jsonable(observation.payload), "provenance": _jsonable(observation.provenance),
    }


def _observation_from_dict(raw: Mapping[str, Any] | None) -> CapsuleObservation | None:
    if raw is None:
        return None
    return CapsuleObservation(
        request_id=EntityId(str(raw["request_id"])), capsule_id=str(raw["capsule_id"]),
        capability=str(raw["capability"]), output_schema_version=str(raw["output_schema_version"]),
        payload=dict(raw.get("payload", {})), provenance=dict(raw.get("provenance", {})),
    )


def task_execution_result_to_dict(result: TaskExecutionResult) -> dict[str, Any]:
    return {
        "schema_version": "task-execution-result/1.0", "meta": _meta_to_dict(result.meta),
        "execution_plan_id": str(result.execution_plan_id), "source_card_id": str(result.source_card_id),
        "active_card_revision": result.active_card_revision, "status": result.status.value,
        "owner": result.owner.value, "capability": result.capability, "observation": _observation_to_dict(result.observation),
        "artifact_refs": list(result.artifact_refs), "child_job_id": result.child_job_id, "reason": result.reason,
    }


def task_execution_result_from_dict(raw: Mapping[str, Any]) -> TaskExecutionResult:
    return TaskExecutionResult(
        meta=_meta_from_dict(raw["meta"]), execution_plan_id=EntityId(str(raw["execution_plan_id"])),
        source_card_id=EntityId(str(raw["source_card_id"])), active_card_revision=int(raw["active_card_revision"]),
        status=TaskExecutionStatus(str(raw["status"])), owner=ExecutionOwner(str(raw["owner"])),
        capability=str(raw["capability"]), observation=_observation_from_dict(raw.get("observation")),
        artifact_refs=tuple(str(x) for x in raw.get("artifact_refs", ())), child_job_id=raw.get("child_job_id") or None,
        reason=raw.get("reason") or None,
    )


class TaskExecutionRepository:
    """Durable audit store for R3 plans, delegations and terminal results."""
    def __init__(self, conn) -> None:
        self._conn = conn

    def save_plan(self, plan: TaskExecutionPlan) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(plan.meta.id, task_execution_plan_to_dict(plan)); uow.commit()

    def save_delegation(self, request: DelegationRequest) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(request.meta.id, delegation_request_to_dict(request)); uow.commit()

    def save_result(self, result: TaskExecutionResult) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(result.meta.id, task_execution_result_to_dict(result)); uow.commit()

    def load_plan(self, entity_id: EntityId) -> TaskExecutionPlan | None:
        raw = SqliteUnitOfWork(self._conn).state_view().get(str(entity_id))
        return task_execution_plan_from_dict(raw) if raw and raw.get("schema_version") == "task-execution-plan/1.0" else None

    def load_delegation(self, entity_id: EntityId) -> DelegationRequest | None:
        raw = SqliteUnitOfWork(self._conn).state_view().get(str(entity_id))
        return delegation_request_from_dict(raw) if raw and raw.get("schema_version") == "delegation-request/1.0" else None

    def load_result(self, entity_id: EntityId) -> TaskExecutionResult | None:
        raw = SqliteUnitOfWork(self._conn).state_view().get(str(entity_id))
        return task_execution_result_from_dict(raw) if raw and raw.get("schema_version") == "task-execution-result/1.0" else None
