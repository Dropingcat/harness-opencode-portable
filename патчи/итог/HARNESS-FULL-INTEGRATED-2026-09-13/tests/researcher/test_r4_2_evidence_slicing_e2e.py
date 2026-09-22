from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EntityMeta, EvidenceSpan, Source
from researcher_core.r0.enums import ClaimStatus, EdgeKind
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.relation_assessment import (
    EvidenceQuality,
    MethodMatch,
    RelationAssessmentProposal,
    assess_relation,
)
from researcher_core.research_planning import ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchDOM
from researcher_core.tribunal_composition import (
    TribunalCompositionRequest,
    compile_tribunal_composition,
    lineage_profile_from_research_dom,
    load_tribunal_composition_policy,
)
from researcher_core.tribunal_evidence import (
    EvidenceSliceStatus,
    TribunalEvidenceRequest,
    compile_tribunal_evidence_bundle,
)
from researcher_core.uncertainty_field import (
    ReviewReadiness,
    build_review_work_field,
    build_uncertainty_profile,
    components_from_relation_assessment,
)


class Clock:
    def now_ms(self):
        return 1789272000000


class R42EvidenceSlicingE2E(unittest.TestCase):
    def test_relation_assessment_to_rwf_to_composition_to_evidence_slice(self):
        root = Path(__file__).resolve().parents[2]
        policy = load_tribunal_composition_policy(root / "config" / "tribunal_composition.yaml")
        ids = EntityIdFactory(Clock(), random.Random(419))
        actor = ActorRef("AGENT", "researcher")
        run = ids.new("RUN")
        req = ids.new("RRQ")
        scope = ids.new("SCP")
        t = datetime(2026, 9, 13, 11, 0, tzinfo=timezone.utc)

        def meta(ns, schema):
            return EntityMeta(ids.new(ns), schema, 1, run, t, actor)

        claim = Claim(
            meta("CLM", "claim/1.0"),
            "BCC lattice expansion is attributable to nitrogen uptake.",
            "bcc lattice expansion is attributable to nitrogen uptake",
            "causal",
            scope,
            ClaimStatus.OPEN,
        )
        source = Source(meta("SRC", "source/1.0"), "journal", "XRD experiment", "doi:10/xrd", "sha256:xrd")
        evd = EvidenceSpan(
            meta("EVD", "evidence-span/1.0"), source.meta.id,
            "The BCC peak shifted after nitriding, while stress separation was not independently measured.",
            "p.6", "sha256:xrd-evidence",
        )
        edge = GraphEdge(
            meta("EDG", "graph-edge/1.0"), evd.meta.id, claim.meta.id, EdgeKind.SUPPORTS,
            {"scope_match": "MATCH", "directness": "DIRECT"},
        )

        objective = ResearchCard(meta("RCD", "research-card/1.0"), req, ResearchCardKind.OBJECTIVE, "Interpret lattice change", status=ResearchCardStatus.ACTIVE)
        discipline = ResearchCard(meta("RCD", "research-card/1.0"), req, ResearchCardKind.DISCIPLINARY_VIEW, "Crystallography", parent_id=objective.meta.id, dimensions={"discipline": "crystallography"})
        method = ResearchCard(meta("RCD", "research-card/1.0"), req, ResearchCardKind.METHOD_VIEW, "XRD", parent_id=discipline.meta.id, dimensions={"method": "xrd"})
        dom = ResearchDOM(meta("RDM", "research-dom/1.0"), req, objective.meta.id, {
            objective.meta.id: objective,
            discipline.meta.id: discipline,
            method.meta.id: method,
        })

        proposal = RelationAssessmentProposal(
            meta("RAP", "relation-assessment-proposal/1.0"),
            method.meta.id,
            edge.meta.id,
            edge.meta.revision,
            "MATCH",
            "DIRECT",
            MethodMatch.UNKNOWN,
            EvidenceQuality.ADEQUATE,
            "XRD relation requires method-specific review",
            (evd.meta.id,),
        )
        assessment, _ = assess_relation(edge=edge, proposal=proposal, id_factory=ids, actor=actor, created_at=t)
        components = components_from_relation_assessment(assessment)
        profile = build_uncertainty_profile(
            target_id=edge.meta.id,
            target_revision=edge.meta.revision,
            components=components,
            id_factory=ids,
            actor=actor,
            run_id=run,
            created_at=t,
        )
        field = build_review_work_field(
            request_id=req,
            profiles=(profile,),
            relation_assessments=(assessment,),
            id_factory=ids,
            actor=actor,
            run_id=run,
            created_at=t,
        )
        self.assertEqual(field.readiness, ReviewReadiness.BLOCKED)

        lineage = lineage_profile_from_research_dom(dom, method.meta.id)
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, lineage), policy)
        self.assertIn("xrd_specialist", plan.dynamic_roles)
        self.assertIn("crystallographer", plan.dynamic_roles)

        state = {x.meta.id: x for x in (claim, source, evd, edge)}
        bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, state))
        xrd = next(x for x in bundle.slices if x.role_id == "xrd_specialist")
        self.assertEqual(xrd.status, EvidenceSliceStatus.READY)
        self.assertEqual({x.evidence_id for x in xrd.evidence_items}, {evd.meta.id})
        self.assertEqual(xrd.evidence_items[0].exact_text, evd.exact_text)
        self.assertEqual(claim.status, ClaimStatus.OPEN)
        self.assertEqual(edge.meta.revision, 1)
        self.assertIn("evidence slicing only", bundle.metadata["authority_boundary"])


if __name__ == "__main__":
    unittest.main()
