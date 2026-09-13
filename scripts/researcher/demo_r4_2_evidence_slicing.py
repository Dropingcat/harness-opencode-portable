#!/usr/bin/env python3
"""Build a deterministic R3.3 -> R3.5 -> R4.1 -> R4.2 scientific demo artifact."""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EntityMeta, EvidenceSpan, Source
from researcher_core.r0.enums import ClaimStatus, EdgeKind
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.relation_assessment import EvidenceQuality, MethodMatch, RelationAssessmentProposal, assess_relation
from researcher_core.research_planning import ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchDOM
from researcher_core.tribunal_composition import (
    TribunalCompositionRequest,
    compile_tribunal_composition,
    lineage_profile_from_research_dom,
    load_tribunal_composition_policy,
    tribunal_composition_plan_to_dict,
)
from researcher_core.tribunal_evidence import TribunalEvidenceRequest, compile_tribunal_evidence_bundle, tribunal_evidence_bundle_to_dict
from researcher_core.uncertainty_field import (
    build_review_work_field,
    build_uncertainty_profile,
    components_from_relation_assessment,
    review_work_field_to_dict,
)


class Clock:
    def now_ms(self):
        return 1789272000000


def build_demo(root: Path) -> dict:
    ids = EntityIdFactory(Clock(), random.Random(421))
    actor = ActorRef("AGENT", "researcher")
    run = ids.new("RUN")
    request_id = ids.new("RRQ")
    scope = ids.new("SCP")
    created_at = datetime(2026, 9, 13, 11, 30, tzinfo=timezone.utc)

    def meta(ns: str, schema: str) -> EntityMeta:
        return EntityMeta(ids.new(ns), schema, 1, run, created_at, actor)

    claim = Claim(
        meta("CLM", "claim/1.0"),
        "BCC lattice expansion after nitriding is attributable to nitrogen uptake.",
        "bcc lattice expansion after nitriding is attributable to nitrogen uptake",
        "causal",
        scope,
        ClaimStatus.OPEN,
    )
    support_source = Source(meta("SRC", "source/1.0"), "journal", "Nitriding XRD study", "doi:10/xrd-support", "sha256:support")
    counter_source = Source(meta("SRC", "source/1.0"), "journal", "Residual-stress XRD study", "doi:10/xrd-counter", "sha256:counter")
    support = EvidenceSpan(
        meta("EVD", "evidence-span/1.0"), support_source.meta.id,
        "Lattice expansion increased after nitrogen uptake during nitriding.", "p.5", "sha256:evd-support",
    )
    counter = EvidenceSpan(
        meta("EVD", "evidence-span/1.0"), counter_source.meta.id,
        "Residual stress can shift the same diffraction peak without a composition change.", "p.9", "sha256:evd-counter",
    )
    support_edge = GraphEdge(
        meta("EDG", "graph-edge/1.0"), support.meta.id, claim.meta.id, EdgeKind.SUPPORTS,
        {"scope_match": "MATCH", "directness": "DIRECT"},
    )
    counter_edge = GraphEdge(
        meta("EDG", "graph-edge/1.0"), counter.meta.id, claim.meta.id, EdgeKind.CONTRADICTS,
        {"scope_match": "MATCH", "directness": "DIRECT"},
    )

    objective = ResearchCard(meta("RCD", "research-card/1.0"), request_id, ResearchCardKind.OBJECTIVE, "Interpret lattice change", status=ResearchCardStatus.ACTIVE)
    discipline = ResearchCard(meta("RCD", "research-card/1.0"), request_id, ResearchCardKind.DISCIPLINARY_VIEW, "Crystallography", parent_id=objective.meta.id, dimensions={"discipline": "crystallography"})
    method = ResearchCard(meta("RCD", "research-card/1.0"), request_id, ResearchCardKind.METHOD_VIEW, "XRD", parent_id=discipline.meta.id, dimensions={"method": "xrd"})
    dom = ResearchDOM(meta("RDM", "research-dom/1.0"), request_id, objective.meta.id, {
        objective.meta.id: objective,
        discipline.meta.id: discipline,
        method.meta.id: method,
    })

    proposal = RelationAssessmentProposal(
        meta("RAP", "relation-assessment-proposal/1.0"), method.meta.id, support_edge.meta.id, 1,
        "MATCH", "DIRECT", MethodMatch.UNKNOWN, EvidenceQuality.ADEQUATE,
        "composition/stress discrimination is unresolved", (support.meta.id,),
    )
    assessment, _ = assess_relation(edge=support_edge, proposal=proposal, id_factory=ids, actor=actor, created_at=created_at)
    profile = build_uncertainty_profile(
        target_id=support_edge.meta.id,
        target_revision=1,
        components=components_from_relation_assessment(assessment),
        id_factory=ids,
        actor=actor,
        run_id=run,
        created_at=created_at,
    )
    field = build_review_work_field(
        request_id=request_id,
        profiles=(profile,),
        relation_assessments=(assessment,),
        id_factory=ids,
        actor=actor,
        run_id=run,
        created_at=created_at,
    )
    # Add the explicit counterevidence to the bounded RWF evidence pool.  The
    # uncertainty definition still comes from the assessed support relation.
    field = field.__class__(
        field.meta, field.request_id, field.target_refs, field.uncertainty_profile_ids,
        field.assessment_needs, field.open_gap_ids, field.conflict_ids,
        field.relation_assessment_ids, tuple(dict.fromkeys((*field.evidence_refs, support.meta.id, counter.meta.id))),
        field.readiness, field.metadata,
    )

    policy = load_tribunal_composition_policy(root / "config" / "tribunal_composition.yaml")
    lineage = lineage_profile_from_research_dom(dom, method.meta.id)
    plan = compile_tribunal_composition(TribunalCompositionRequest(field, lineage), policy)
    state = {x.meta.id: x for x in (claim, support_source, counter_source, support, counter, support_edge, counter_edge)}
    bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, state))

    return {
        "schema_version": "r4.2-evidence-slicing-demo/1.0",
        "pipeline": ["RelationAssessment", "UncertaintyProfile", "ReviewWorkField", "TribunalCompositionPlan", "TribunalEvidenceBundle"],
        "review_work_field": review_work_field_to_dict(field),
        "composition": tribunal_composition_plan_to_dict(plan),
        "evidence_bundle": tribunal_evidence_bundle_to_dict(bundle),
        "checks": {
            "claim_status_unchanged": claim.status.value,
            "support_edge_revision_unchanged": support_edge.meta.revision,
            "skeptic_blind_provenance": next(x for x in bundle.slices if x.role_id == "skeptic").include_provenance is False,
            "no_dialogue_executed": True,
        },
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    out = root / "artifacts" / "researcher_r4_2" / "r4_2_evidence_slicing_e2e_demo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_demo(root)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
