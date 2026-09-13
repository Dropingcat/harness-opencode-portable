from __future__ import annotations

import random
import sqlite3
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import ConflictState, EdgeKind, GapState
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r1_entities import Conflict, Gap
from researcher_core.relation_assessment import (
    EvidenceQuality,
    MethodMatch,
    RelationAssessmentProposal,
    RelationAssessmentVerdict,
    assess_relation,
)
from researcher_core.uncertainty_field import (
    AssessmentMethod,
    ReviewReadiness,
    UncertaintyAxis,
    UncertaintyLevel,
    build_review_work_field,
    build_uncertainty_profile,
    component_from_conflict,
    component_from_gap,
    component_from_numeric_uncertainty,
    components_from_relation_assessment,
    review_work_field_to_dict,
    uncertainty_profile_to_dict,
    UncertaintyFieldRepository,
)


class Clock:
    def now_ms(self):
        return 1789272000000


class UncertaintyFieldTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(109))
        self.actor = ActorRef("AGENT", "researcher")
        self.t = datetime(2026, 9, 13, 4, 0, tzinfo=timezone.utc)
        self.run = self.ids.new("RUN")
        self.req = self.ids.new("RRQ")
        self.card = self.ids.new("RCD")
        self.claim = self.ids.new("CLM")
        self.evidence = self.ids.new("EVD")

    def _assessment(self, *, method=MethodMatch.MATCH, quality=EvidenceQuality.ADEQUATE, scope="MATCH"):
        edge = GraphEdge(
            EntityMeta(self.ids.new("EDG"), "graph-edge/1.0", 1, self.run, self.t, self.actor),
            self.evidence,
            self.claim,
            EdgeKind.SUPPORTS,
            {"scope_match": scope, "directness": "DIRECT"},
        )
        proposal = RelationAssessmentProposal(
            EntityMeta(self.ids.new("RAP"), "relation-assessment-proposal/1.0", 1, self.run, self.t, self.actor),
            self.card,
            edge.meta.id,
            edge.meta.revision,
            scope,
            "DIRECT",
            method,
            quality,
            "fixture",
            (self.evidence,),
        )
        assessment, _ = assess_relation(edge=edge, proposal=proposal, id_factory=self.ids, actor=self.actor, created_at=self.t)
        return edge, assessment

    def test_inconclusive_evidence_becomes_blocking_axis(self):
        edge, assessment = self._assessment(quality=EvidenceQuality.UNKNOWN)
        self.assertEqual(assessment.verdict, RelationAssessmentVerdict.INCONCLUSIVE)
        components = components_from_relation_assessment(assessment)
        self.assertTrue(any(x.axis is UncertaintyAxis.EVIDENCE_SUFFICIENCY for x in components))
        evidence_component = next(x for x in components if x.axis is UncertaintyAxis.EVIDENCE_SUFFICIENCY)
        self.assertEqual(evidence_component.level, UncertaintyLevel.BLOCKING)
        self.assertTrue(evidence_component.blocking)
        self.assertIn(AssessmentMethod.EVIDENCE_QUALITY, evidence_component.assessment_methods)
        profile = build_uncertainty_profile(
            target_id=edge.meta.id,
            target_revision=edge.meta.revision,
            components=components,
            id_factory=self.ids,
            actor=self.actor,
            run_id=self.run,
            created_at=self.t,
        )
        self.assertEqual(profile.readiness, ReviewReadiness.BLOCKED)
        self.assertIn(UncertaintyAxis.EVIDENCE_SUFFICIENCY, profile.dominant_axes)

    def test_qualified_method_stays_usable_but_visible(self):
        edge, assessment = self._assessment(method=MethodMatch.PARTIAL)
        components = components_from_relation_assessment(assessment)
        method_component = next(x for x in components if x.axis is UncertaintyAxis.METHOD)
        self.assertEqual(method_component.level, UncertaintyLevel.QUALIFIED)
        self.assertFalse(method_component.blocking)
        profile = build_uncertainty_profile(
            target_id=edge.meta.id,
            target_revision=1,
            components=components,
            id_factory=self.ids,
            actor=self.actor,
            run_id=self.run,
            created_at=self.t,
        )
        self.assertEqual(profile.readiness, ReviewReadiness.QUALIFIED)

    def test_gap_maps_to_axis_without_scalar_confidence(self):
        gap = Gap(
            self.ids.new("GAP"),
            "METHOD_APPLICABILITY_UNKNOWN",
            (self.claim,),
            "blocking",
            (self.claim,),
            ("validate method applicability",),
            GapState.OPEN_BLOCKING_GAPS,
        )
        component = component_from_gap(gap)
        self.assertEqual(component.axis, UncertaintyAxis.METHOD)
        self.assertEqual(component.level, UncertaintyLevel.BLOCKING)
        self.assertNotIn("confidence", component.metadata)

    def test_conflict_maps_to_conflict_analysis_need(self):
        other_claim = self.ids.new("CLM")
        conflict = Conflict(
            self.ids.new("CNF"),
            (self.claim, other_claim),
            (self.evidence,),
            "NUMERIC_DISAGREEMENT",
            ConflictState.CONFLICT_UNRESOLVED,
        )
        component = component_from_conflict(conflict)
        self.assertEqual(component.axis, UncertaintyAxis.CONFLICT)
        self.assertTrue(component.blocking)
        self.assertIn(AssessmentMethod.CONFLICT_ANALYSIS, component.assessment_methods)

    def test_numeric_uncertainty_uses_interval_semantics_not_fixed_percent_threshold(self):
        component = component_from_numeric_uncertainty(
            target_id=self.ids.new("QTY"),
            value=Decimal("10.0"),
            uncertainty=Decimal("0.5"),
            reference_value=Decimal("10.3"),
            reference_uncertainty=Decimal("0.4"),
            required_for_decision=True,
        )
        self.assertEqual(component.level, UncertaintyLevel.QUALIFIED)
        self.assertEqual(component.metadata["comparison_status"], "MATCH")
        self.assertIn(AssessmentMethod.INTERVAL_OVERLAP, component.assessment_methods)

    def test_numeric_without_reference_is_uncharacterized_or_blocking_by_decision_role(self):
        qid = self.ids.new("QTY")
        optional = component_from_numeric_uncertainty(target_id=qid, value=Decimal("1"), uncertainty=Decimal("0.1"))
        required = component_from_numeric_uncertainty(target_id=qid, value=Decimal("1"), uncertainty=Decimal("0.1"), required_for_decision=True)
        self.assertEqual(optional.level, UncertaintyLevel.UNCHARACTERIZED)
        self.assertFalse(optional.blocking)
        self.assertEqual(required.level, UncertaintyLevel.BLOCKING)
        self.assertTrue(required.blocking)

    def test_review_work_field_contains_what_to_assess_not_who(self):
        edge, assessment = self._assessment(quality=EvidenceQuality.UNKNOWN)
        profile = build_uncertainty_profile(
            target_id=edge.meta.id,
            target_revision=edge.meta.revision,
            components=components_from_relation_assessment(assessment),
            id_factory=self.ids,
            actor=self.actor,
            run_id=self.run,
            created_at=self.t,
        )
        field = build_review_work_field(
            request_id=self.req,
            profiles=(profile,),
            relation_assessments=(assessment,),
            id_factory=self.ids,
            actor=self.actor,
            run_id=self.run,
            created_at=self.t,
        )
        self.assertEqual(field.readiness, ReviewReadiness.BLOCKED)
        self.assertTrue(field.assessment_needs)
        self.assertEqual(field.metadata["composition_boundary"], "R3 defines what must be assessed; R4 selects who assesses it")
        raw = review_work_field_to_dict(field)
        self.assertNotIn("roles", raw)
        self.assertNotIn("specialists", raw)
        self.assertTrue(raw["assessment_needs"][0]["assessment_methods"])

    def test_work_field_collects_gap_conflict_and_relation_refs(self):
        edge, assessment = self._assessment(quality=EvidenceQuality.UNKNOWN)
        gap = Gap(self.ids.new("GAP"), "EVIDENCE_GAP", (self.claim,), "blocking", (self.claim,), ("find independent evidence",), GapState.OPEN_BLOCKING_GAPS)
        other = self.ids.new("CLM")
        conflict = Conflict(self.ids.new("CNF"), (self.claim, other), (self.evidence,), "SCOPE_CONFLICT", ConflictState.CONFLICT_UNRESOLVED)
        components = (*components_from_relation_assessment(assessment), component_from_gap(gap), component_from_conflict(conflict))
        profile = build_uncertainty_profile(
            target_id=self.claim,
            target_revision=1,
            components=components,
            id_factory=self.ids,
            actor=self.actor,
            run_id=self.run,
            created_at=self.t,
        )
        field = build_review_work_field(
            request_id=self.req,
            profiles=(profile,),
            gaps=(gap,),
            conflicts=(conflict,),
            relation_assessments=(assessment,),
            id_factory=self.ids,
            actor=self.actor,
            run_id=self.run,
            created_at=self.t,
        )
        self.assertEqual(field.open_gap_ids, (gap.id,))
        self.assertEqual(field.conflict_ids, (conflict.id,))
        self.assertEqual(field.relation_assessment_ids, (assessment.meta.id,))
        self.assertGreaterEqual(len(field.assessment_needs), 3)

    def test_serialization_preserves_axes_methods_and_reason_codes(self):
        gap = Gap(self.ids.new("GAP"), "DERIVATION_REPRODUCIBILITY", (self.claim,), "blocking", (self.claim,), ("recompute derivation",), GapState.OPEN_BLOCKING_GAPS)
        profile = build_uncertainty_profile(
            target_id=self.claim,
            target_revision=1,
            components=(component_from_gap(gap),),
            id_factory=self.ids,
            actor=self.actor,
            run_id=self.run,
            created_at=self.t,
        )
        raw = uncertainty_profile_to_dict(profile)
        self.assertEqual(raw["components"][0]["axis"], "DERIVATION")
        self.assertIn("DERIVATION_REPRODUCIBILITY", raw["components"][0]["assessment_methods"])
        self.assertEqual(raw["readiness"], "BLOCKED")

    def test_repository_roundtrip_profile_and_work_field(self):
        edge, assessment = self._assessment(quality=EvidenceQuality.UNKNOWN)
        profile = build_uncertainty_profile(
            target_id=edge.meta.id,
            target_revision=1,
            components=components_from_relation_assessment(assessment),
            id_factory=self.ids, actor=self.actor, run_id=self.run, created_at=self.t,
        )
        field = build_review_work_field(
            request_id=self.req, profiles=(profile,), relation_assessments=(assessment,),
            id_factory=self.ids, actor=self.actor, run_id=self.run, created_at=self.t,
        )
        conn = sqlite3.connect(":memory:")
        repo = UncertaintyFieldRepository(conn)
        repo.save_profile(profile); repo.save_work_field(field)
        self.assertEqual(repo.load_profile(profile.meta.id), profile)
        self.assertEqual(repo.load_work_field(field.meta.id), field)
        conn.close()

    def test_service_artifact_exposes_uncertainty_field_for_r4_input(self):
        from researcher_core.artifact_builder import build_minimal_service_artifact
        from researcher_core.r0.projections import Snapshot
        edge, assessment = self._assessment(quality=EvidenceQuality.UNKNOWN)
        profile = build_uncertainty_profile(
            target_id=edge.meta.id, target_revision=1,
            components=components_from_relation_assessment(assessment),
            id_factory=self.ids, actor=self.actor, run_id=self.run, created_at=self.t,
        )
        field = build_review_work_field(
            request_id=self.req, profiles=(profile,), relation_assessments=(assessment,),
            id_factory=self.ids, actor=self.actor, run_id=self.run, created_at=self.t,
        )
        artifact = build_minimal_service_artifact(
            Snapshot(self.ids.new("SNP"), 0, {}, "fixture"),
            {str(edge.meta.id): edge}, "fixture",
            relation_assessments=(assessment,), uncertainty_profiles=(profile,), review_work_fields=(field,),
        )
        self.assertEqual(artifact["uncertainty_profiles"][str(profile.meta.id)]["readiness"], "BLOCKED")
        wf = artifact["review_work_fields"][str(field.meta.id)]
        self.assertEqual(wf["readiness"], "BLOCKED")
        self.assertTrue(wf["assessment_needs"])
        self.assertNotIn("roles", wf)


if __name__ == "__main__":
    unittest.main()
