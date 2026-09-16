"""R2.3 selective invalidation and historical challenge reopen.

This is deliberately a bounded deterministic layer, not a universal TMS.
Changes are first converted to DependencyImpactAssessment artifacts.  Only a
separate reducer may project a critical impact onto Gap/Conflict,
ResearchChallenge and ResearchDOM state.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping, Sequence

from researcher_core.challenge_resolution import ChallengeResolutionAssessment
from researcher_core.knowledge_reconciliation import ResearchChallenge, ResearchChallengeStatus
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import ConflictState, GapState
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.r1_entities import Conflict, Gap
from researcher_core.research_planning import (
    ResearchCardKind, ResearchCardStatus, ResearchDOM, ResearchPatch,
    SetCardStatusOperation, apply_research_patch,
)


class DependencyStrength(StrEnum):
    HARD = "HARD"
    SOFT = "SOFT"
    CONTEXTUAL = "CONTEXTUAL"


class DependencyState(StrEnum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"


class ImpactState(StrEnum):
    NO_IMPACT = "NO_IMPACT"
    STALE_ONLY = "STALE_ONLY"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    INCOMPLETE = "INCOMPLETE"


class IterationState(StrEnum):
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"
    ACTIVE = "ACTIVE"


@dataclass(frozen=True, slots=True)
class KnowledgeDependency:
    meta: EntityMeta
    source_id: EntityId
    target_id: EntityId
    relation: str
    strength: DependencyStrength
    group_key: str | None = None
    min_active_in_group: int = 1
    state: DependencyState = DependencyState.ACTIVE
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "KDP":
            raise ValueError("dependency id must use KDP prefix")
        if not self.relation.strip():
            raise ValueError("relation is required")
        if self.min_active_in_group < 1:
            raise ValueError("min_active_in_group must be positive")
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class DependencyImpactAssessment:
    meta: EntityMeta
    changed_entity_ids: tuple[EntityId, ...]
    stale_dependency_ids: tuple[EntityId, ...]
    invalidated_entity_ids: tuple[EntityId, ...]
    stale_entity_ids: tuple[EntityId, ...]
    stale_relation_ids: tuple[EntityId, ...]
    state: ImpactState
    target_resolution_id: EntityId | None
    traversal_nodes: int
    diagnostics: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "DIA":
            raise ValueError("impact assessment id must use DIA prefix")
        for name in ("changed_entity_ids", "stale_dependency_ids", "invalidated_entity_ids", "stale_entity_ids", "stale_relation_ids", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class ChallengeIteration:
    meta: EntityMeta
    challenge_id: EntityId
    iteration_index: int
    state: IterationState
    trigger_entity_ids: tuple[EntityId, ...]
    previous_resolution_id: EntityId | None = None
    impact_assessment_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RIT":
            raise ValueError("iteration id must use RIT prefix")
        if self.challenge_id.namespace != "RCH":
            raise ValueError("challenge_id must use RCH prefix")
        if self.iteration_index < 1:
            raise ValueError("iteration_index must be positive")
        object.__setattr__(self, "trigger_entity_ids", tuple(self.trigger_entity_ids))
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class InvalidationResult:
    source_entity: Gap | Conflict
    challenge: ResearchChallenge
    dom: ResearchDOM
    impact: DependencyImpactAssessment
    iteration: ChallengeIteration | None
    events: tuple


class InvalidationError(ValueError):
    pass


def assess_dependency_impact(
    *, changed_entity_ids: Sequence[EntityId], dependencies: Sequence[KnowledgeDependency],
    target_resolution_id: EntityId | None, meta: EntityMeta, max_nodes: int = 128,
) -> DependencyImpactAssessment:
    """Bounded deterministic propagation across explicit dependency records."""
    if meta.id.namespace != "DIA":
        raise ValueError("meta id must use DIA prefix")
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    deps = tuple(dependencies)
    by_source: dict[EntityId, list[KnowledgeDependency]] = {}
    incoming: dict[tuple[EntityId, str], list[KnowledgeDependency]] = {}
    for dep in deps:
        by_source.setdefault(dep.source_id, []).append(dep)
        key=(dep.target_id, dep.group_key or f"{dep.target_id}:{dep.relation}")
        incoming.setdefault(key, []).append(dep)

    changed=set(changed_entity_ids); invalidated=set(changed); stale_entities=set(); stale_deps=set(); stale_relations=set(); diagnostics=[]
    queue=list(changed); visited=set(); truncated=False
    while queue:
        current=queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        if len(visited)>max_nodes:
            truncated=True; diagnostics.append("IMPACT_SCOPE_TRUNCATED"); break
        for dep in by_source.get(current, ()):
            if dep.state != DependencyState.ACTIVE:
                continue
            if dep.strength == DependencyStrength.CONTEXTUAL and dep.metadata.get("scope_overlap") is False:
                continue
            stale_deps.add(dep.meta.id)
            if dep.target_id.namespace == "EDG":
                stale_relations.add(dep.target_id)
            if dep.strength == DependencyStrength.SOFT:
                stale_entities.add(dep.target_id)
                continue
            key=(dep.target_id, dep.group_key or f"{dep.target_id}:{dep.relation}")
            group=incoming.get(key, [dep])
            active_after=sum(1 for x in group if x.state==DependencyState.ACTIVE and x.source_id not in invalidated)
            required=max(x.min_active_in_group for x in group)
            if active_after < required or bool(dep.metadata.get("critical")):
                if dep.target_id not in invalidated:
                    invalidated.add(dep.target_id); queue.append(dep.target_id)
            else:
                stale_entities.add(dep.target_id)

    if truncated or any(dep.metadata.get("provenance_complete") is False for dep in deps if dep.meta.id in stale_deps):
        state=ImpactState.INCOMPLETE
    elif target_resolution_id and target_resolution_id in invalidated:
        state=ImpactState.REOPEN_REQUIRED
    elif target_resolution_id and target_resolution_id in stale_entities:
        state=ImpactState.REVALIDATION_REQUIRED
    elif stale_deps or stale_relations or stale_entities:
        state=ImpactState.STALE_ONLY
    else:
        state=ImpactState.NO_IMPACT
    return DependencyImpactAssessment(
        meta=meta, changed_entity_ids=tuple(changed_entity_ids), stale_dependency_ids=tuple(sorted(stale_deps,key=str)),
        invalidated_entity_ids=tuple(sorted(invalidated-set(changed),key=str)), stale_entity_ids=tuple(sorted(stale_entities,key=str)),
        stale_relation_ids=tuple(sorted(stale_relations,key=str)), state=state, target_resolution_id=target_resolution_id,
        traversal_nodes=len(visited), diagnostics=tuple(diagnostics), metadata={"max_nodes":max_nodes},
    )


def reopen_from_impact(
    *, dom: ResearchDOM, challenge: ResearchChallenge, source_entity: Gap | Conflict,
    resolution: ChallengeResolutionAssessment, impact: DependencyImpactAssessment,
    challenge_card_id: EntityId, prior_iterations: Sequence[ChallengeIteration], patch_id: EntityId,
    actor: ActorRef, id_factory: EntityIdFactory, timestamp, causation_id: EntityId, correlation_id: EntityId,
) -> InvalidationResult:
    """Project only a critical complete impact into an existing historical branch."""
    if impact.target_resolution_id != resolution.meta.id:
        raise InvalidationError("impact targets a different resolution assessment")
    if resolution.challenge_id != challenge.meta.id or resolution.source_entity_id != source_entity.id:
        raise InvalidationError("resolution/challenge/source mismatch")
    if resolution.expected_challenge_revision + 1 != challenge.meta.revision:
        raise InvalidationError("resolution is not the current resolved challenge revision")
    if challenge_card_id not in dom.cards or dom.cards[challenge_card_id].kind != ResearchCardKind.CHALLENGE:
        raise InvalidationError("challenge card missing or wrong kind")
    if dom.cards[challenge_card_id].dimensions.get("challenge_id") != str(challenge.meta.id):
        raise InvalidationError("challenge card binding mismatch")
    if impact.state == ImpactState.INCOMPLETE:
        raise InvalidationError("incomplete impact cannot mutate challenge state")
    if impact.state != ImpactState.REOPEN_REQUIRED:
        return InvalidationResult(source_entity,challenge,dom,impact,None,())
    if challenge.status != ResearchChallengeStatus.RESOLVED:
        raise InvalidationError("only RESOLVED challenge can be automatically reopened")

    if isinstance(source_entity, Gap):
        if source_entity.status != GapState.NO_OPEN_GAPS:
            raise InvalidationError("gap is not resolved")
        reopened_state=GapState.OPEN_BLOCKING_GAPS if source_entity.severity.lower()=="blocking" else GapState.OPEN_NONBLOCKING_GAPS
        updated_source=replace(source_entity,status=reopened_state)
    else:
        if source_entity.status != ConflictState.NO_DIRECT_CONFLICT:
            raise InvalidationError("conflict is not resolved")
        updated_source=replace(source_entity,status=ConflictState.CONFLICT_UNRESOLVED)

    updated_challenge=replace(challenge,meta=replace(challenge.meta,revision=challenge.meta.revision+1),status=ResearchChallengeStatus.REOPENED)
    card=dom.cards[challenge_card_id]
    patch=ResearchPatch(
        id=patch_id,request_id=dom.request_id,expected_dom_revision=dom.meta.revision,
        operations=(SetCardStatusOperation(challenge_card_id,card.meta.revision,ResearchCardStatus.ACTIVE),),
    )
    reduced=apply_research_patch(dom,patch,actor,id_factory,timestamp,causation_id,correlation_id)
    iteration=ChallengeIteration(
        meta=EntityMeta(id_factory.new("RIT"),"challenge-iteration/1.0",1,dom.meta.run_id,timestamp,actor),
        challenge_id=challenge.meta.id,iteration_index=max((x.iteration_index for x in prior_iterations),default=0)+1,
        state=IterationState.REOPENED,trigger_entity_ids=impact.changed_entity_ids,
        previous_resolution_id=resolution.meta.id,impact_assessment_id=impact.meta.id,
        metadata={"previous_challenge_revision":challenge.meta.revision,"new_challenge_revision":updated_challenge.meta.revision},
    )
    return InvalidationResult(updated_source,updated_challenge,reduced.dom,impact,iteration,reduced.events)


def dependency_to_dict(v: KnowledgeDependency)->dict[str,Any]:
    return {"schema_version":"knowledge-dependency/1.0","id":str(v.meta.id),"run_id":str(v.meta.run_id),"created_at":v.meta.created_at.isoformat(),"created_by":{"actor_type":v.meta.created_by.actor_type,"actor_id":v.meta.created_by.actor_id},"revision":v.meta.revision,"source_id":str(v.source_id),"target_id":str(v.target_id),"relation":v.relation,"strength":v.strength.value,"group_key":v.group_key,"min_active_in_group":v.min_active_in_group,"state":v.state.value,"metadata":_plain(v.metadata)}


def impact_to_dict(v: DependencyImpactAssessment)->dict[str,Any]:
    return {"schema_version":"dependency-impact/1.0","id":str(v.meta.id),"run_id":str(v.meta.run_id),"created_at":v.meta.created_at.isoformat(),"created_by":{"actor_type":v.meta.created_by.actor_type,"actor_id":v.meta.created_by.actor_id},"revision":v.meta.revision,"changed_entity_ids":[str(x) for x in v.changed_entity_ids],"stale_dependency_ids":[str(x) for x in v.stale_dependency_ids],"invalidated_entity_ids":[str(x) for x in v.invalidated_entity_ids],"stale_entity_ids":[str(x) for x in v.stale_entity_ids],"stale_relation_ids":[str(x) for x in v.stale_relation_ids],"state":v.state.value,"target_resolution_id":str(v.target_resolution_id) if v.target_resolution_id else None,"traversal_nodes":v.traversal_nodes,"diagnostics":list(v.diagnostics),"metadata":_plain(v.metadata)}


def iteration_to_dict(v: ChallengeIteration)->dict[str,Any]:
    return {"schema_version":"challenge-iteration/1.0","id":str(v.meta.id),"run_id":str(v.meta.run_id),"created_at":v.meta.created_at.isoformat(),"created_by":{"actor_type":v.meta.created_by.actor_type,"actor_id":v.meta.created_by.actor_id},"revision":v.meta.revision,"challenge_id":str(v.challenge_id),"iteration_index":v.iteration_index,"state":v.state.value,"trigger_entity_ids":[str(x) for x in v.trigger_entity_ids],"previous_resolution_id":str(v.previous_resolution_id) if v.previous_resolution_id else None,"impact_assessment_id":str(v.impact_assessment_id) if v.impact_assessment_id else None,"metadata":_plain(v.metadata)}


class InvalidationRepository:
    def __init__(self,conn)->None:self._conn=conn
    def save(self,*values)->None:
        with SqliteUnitOfWork(self._conn) as uow:
            for v in values:
                if isinstance(v,KnowledgeDependency): raw=dependency_to_dict(v)
                elif isinstance(v,DependencyImpactAssessment): raw=impact_to_dict(v)
                elif isinstance(v,ChallengeIteration): raw=iteration_to_dict(v)
                else: raise TypeError(type(v).__name__)
                uow.put_state(v.meta.id,raw)
            uow.commit()
    def iterations_for_challenge(self,challenge_id:EntityId)->tuple[Mapping[str,Any],...]:
        view=SqliteUnitOfWork(self._conn).state_view(); out=[]
        for raw in view.values():
            if raw.get("schema_version")=="challenge-iteration/1.0" and raw.get("challenge_id")==str(challenge_id): out.append(raw)
        return tuple(sorted(out,key=lambda x:int(x["iteration_index"])))


def _plain(v:Any)->Any:
    if isinstance(v,Mapping):return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,tuple):return [_plain(x) for x in v]
    if isinstance(v,EntityId):return str(v)
    return v
