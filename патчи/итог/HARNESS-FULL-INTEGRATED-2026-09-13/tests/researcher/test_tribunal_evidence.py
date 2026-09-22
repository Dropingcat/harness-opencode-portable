from __future__ import annotations

import random
import unittest
from dataclasses import replace

import yaml
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EntityMeta, EvidenceSpan, Quantity, Source
from researcher_core.r0.enums import ClaimStatus, EdgeKind
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_composition import (
    TribunalCompositionRequest,
    TribunalLineageProfile,
    compile_tribunal_composition,
    load_tribunal_composition_policy,
)
from researcher_core.tribunal_evidence import (
    EvidencePolarity,
    EvidenceSliceStatus,
    PriorReviewArtifact,
    TribunalEvidenceError,
    TribunalEvidenceRequest,
    compile_tribunal_evidence_bundle,
    tribunal_evidence_bundle_to_dict,
)
from researcher_core.uncertainty_field import (
    AssessmentMethod,
    AssessmentNeed,
    ReviewReadiness,
    ReviewWorkField,
    UncertaintyAxis,
    UncertaintyLevel,
)


class Clock:
    def now_ms(self):
        return 1789272000000


class TribunalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root / "config" / "tribunal_composition.yaml")
        self.ids = EntityIdFactory(Clock(), random.Random(307))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.req = self.ids.new("RRQ")
        self.t = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)
        self.scope = self.ids.new("SCP")

        self.claim = Claim(
            self._meta("CLM", "claim/1.0"),
            "The observed peak shift is caused by nitrogen in solid solution.",
            "the observed peak shift is caused by nitrogen in solid solution",
            "causal",
            self.scope,
            ClaimStatus.OPEN,
        )
        self.support_source = Source(
            self._meta("SRC", "source/1.0"), "journal", "Support paper", "doi:10/support", "sha256:support"
        )
        self.counter_source = Source(
            self._meta("SRC", "source/1.0"), "journal", "Counter paper", "doi:10/counter", "sha256:counter"
        )
        self.extra_source = Source(
            self._meta("SRC", "source/1.0"), "review", "Background review", "doi:10/background", "sha256:bg"
        )
        self.support_evd = EvidenceSpan(
            self._meta("EVD", "evidence-span/1.0"),
            self.support_source.meta.id,
            "Nitrogen uptake coincided with the measured lattice expansion.",
            "p.4",
            "sha256:evd-support",
        )
        self.counter_evd = EvidenceSpan(
            self._meta("EVD", "evidence-span/1.0"),
            self.counter_source.meta.id,
            "Residual stress produced a comparable diffraction-peak shift.",
            "p.8",
            "sha256:evd-counter",
        )
        self.extra_evd = EvidenceSpan(
            self._meta("EVD", "evidence-span/1.0"),
            self.extra_source.meta.id,
            "The review discusses both compositional and stress contributions.",
            "p.12",
            "sha256:evd-bg",
        )
        self.support_edge = GraphEdge(
            self._meta("EDG", "graph-edge/1.0"),
            self.support_evd.meta.id,
            self.claim.meta.id,
            EdgeKind.SUPPORTS,
            {"scope_match": "MATCH", "directness": "DIRECT"},
        )
        self.counter_edge = GraphEdge(
            self._meta("EDG", "graph-edge/1.0"),
            self.counter_evd.meta.id,
            self.claim.meta.id,
            EdgeKind.CONTRADICTS,
            {"scope_match": "MATCH", "directness": "DIRECT"},
        )
        self.state = {
            x.meta.id: x
            for x in (
                self.claim,
                self.support_source,
                self.counter_source,
                self.extra_source,
                self.support_evd,
                self.counter_evd,
                self.extra_evd,
                self.support_edge,
                self.counter_edge,
            )
        }

    def _meta(self, namespace, schema):
        return EntityMeta(self.ids.new(namespace), schema, 1, self.run, self.t, self.actor)

    def _field(self):
        method_need = AssessmentNeed(
            axis=UncertaintyAxis.METHOD,
            level=UncertaintyLevel.BLOCKING,
            blocking=True,
            target_refs=(self.support_edge.meta.id,),
            source_refs=(self.support_evd.meta.id,),
            question="Can XRD distinguish composition from stress in this inference?",
            assessment_methods=(AssessmentMethod.METHOD_COMPATIBILITY,),
            completion_criteria=("typed method disposition",),
            reason_codes=("fixture:method",),
        )
        conflict_need = AssessmentNeed(
            axis=UncertaintyAxis.CONFLICT,
            level=UncertaintyLevel.BLOCKING,
            blocking=True,
            target_refs=(self.claim.meta.id,),
            source_refs=(self.support_evd.meta.id, self.counter_evd.meta.id),
            question="What explains the conflict?",
            assessment_methods=(AssessmentMethod.CONFLICT_ANALYSIS,),
            completion_criteria=("typed conflict disposition",),
            reason_codes=("fixture:conflict",),
        )
        return ReviewWorkField(
            meta=self._meta("RWF", "review-work-field/1.0"),
            request_id=self.req,
            target_refs=(self.claim.meta.id, self.support_edge.meta.id),
            uncertainty_profile_ids=(),
            assessment_needs=(method_need, conflict_need),
            open_gap_ids=(),
            conflict_ids=(),
            relation_assessment_ids=(),
            evidence_refs=(
                self.support_evd.meta.id,
                self.counter_evd.meta.id,
                self.extra_evd.meta.id,
                self.support_source.meta.id,
                self.counter_source.meta.id,
                self.extra_source.meta.id,
            ),
            readiness=ReviewReadiness.BLOCKED,
        )

    def _bundle(self):
        field = self._field()
        lineage = TribunalLineageProfile(
            disciplinary_views=("crystallography",),
            method_views=("xrd", "x-ray diffraction"),
        )
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, lineage), self.policy)
        prior = PriorReviewArtifact(
            "PRELIM-1",
            "PreliminaryVerdict",
            (self.claim.meta.id,),
            {"verdict": "SUPPORTED", "confidence": 0.93},
        )
        bundle = compile_tribunal_evidence_bundle(
            TribunalEvidenceRequest(field, plan, self.state, (prior,))
        )
        return field, plan, bundle

    def _slice(self, bundle, role_id):
        return next(x for x in bundle.slices if x.role_id == role_id)

    def test_fresh_context_hides_provenance_previous_conclusions_and_polarity(self):
        _, _, bundle = self._bundle()
        skeptic = self._slice(bundle, "skeptic")
        self.assertFalse(skeptic.include_provenance)
        self.assertFalse(skeptic.include_previous_conclusions)
        self.assertFalse(skeptic.source_projections)
        self.assertFalse(skeptic.prior_review_artifacts)
        self.assertTrue(skeptic.evidence_items)
        self.assertTrue(all(x.source_id is None and x.locator is None for x in skeptic.evidence_items))
        self.assertTrue(all(x.polarity is EvidencePolarity.UNLABELED for x in skeptic.evidence_items))
        self.assertTrue(all(
            {reason.value for reason in x.selection_reasons} == {"ASSIGNED_RELEVANCE"}
            for x in skeptic.evidence_items
        ))

    def test_support_view_excludes_known_counterevidence(self):
        _, _, bundle = self._bundle()
        crystallographer = self._slice(bundle, "crystallographer")
        ids = {x.evidence_id for x in crystallographer.evidence_items}
        self.assertIn(self.support_evd.meta.id, ids)
        self.assertNotIn(self.counter_evd.meta.id, ids)
        self.assertTrue(all(x.polarity is not EvidencePolarity.COUNTER for x in crystallographer.evidence_items))

    def test_counter_view_excludes_known_support(self):
        _, _, bundle = self._bundle()
        critic = self._slice(bundle, "critic")
        ids = {x.evidence_id for x in critic.evidence_items}
        self.assertIn(self.counter_evd.meta.id, ids)
        self.assertNotIn(self.support_evd.meta.id, ids)

    def test_method_only_does_not_widen_to_background_work_field_evidence(self):
        _, _, bundle = self._bundle()
        methodologist = self._slice(bundle, "methodologist")
        ids = {x.evidence_id for x in methodologist.evidence_items}
        self.assertEqual(ids, {self.support_evd.meta.id})
        self.assertNotIn(self.extra_evd.meta.id, ids)

    def test_full_relevant_is_assignment_scoped_and_keeps_provenance(self):
        _, _, bundle = self._bundle()
        auditor = self._slice(bundle, "evidence_auditor")
        ids = {x.evidence_id for x in auditor.evidence_items}
        self.assertEqual(ids, {self.support_evd.meta.id, self.counter_evd.meta.id})
        self.assertNotIn(self.extra_evd.meta.id, ids)
        source_ids = {x.source_id for x in auditor.source_projections}
        self.assertEqual(source_ids, {self.support_source.meta.id, self.counter_source.meta.id})
        self.assertNotIn(self.extra_source.meta.id, source_ids)
        self.assertTrue(all(x.source_id is not None and x.locator for x in auditor.evidence_items))

    def test_tampered_role_brief_is_rejected_by_plan_integrity(self):
        field = self._field()
        plan = compile_tribunal_composition(
            TribunalCompositionRequest(field, TribunalLineageProfile(method_views=("xrd",))), self.policy
        )
        briefs = list(plan.role_briefs)
        index = next(i for i, brief in enumerate(briefs) if brief.role_id == "skeptic")
        skeptic = briefs[index]
        briefs[index] = replace(
            skeptic,
            evidence_view=replace(skeptic.evidence_view, include_provenance=True),
        )
        tampered = replace(plan, role_briefs=tuple(briefs))
        with self.assertRaises(TribunalEvidenceError):
            compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, tampered, self.state))

    def test_fresh_context_hides_graph_edge_semantics(self):
        need = AssessmentNeed(
            axis=UncertaintyAxis.EVIDENCE_SUFFICIENCY,
            level=UncertaintyLevel.BLOCKING,
            blocking=True,
            target_refs=(self.support_edge.meta.id,),
            source_refs=(self.support_evd.meta.id,),
            question="Independently assess evidence sufficiency",
            assessment_methods=(AssessmentMethod.CROSS_SOURCE_COMPARISON,),
            completion_criteria=("typed evidence disposition",),
        )
        field = ReviewWorkField(
            self._meta("RWF", "review-work-field/1.0"), self.req, (self.support_edge.meta.id,), (),
            (need,), (), (), (), (self.support_evd.meta.id,), ReviewReadiness.BLOCKED,
        )
        plan = compile_tribunal_composition(
            TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy
        )
        bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, self.state))
        skeptic = self._slice(bundle, "skeptic")
        edge_projection = next(x for x in skeptic.target_projections if x.target_id == self.support_edge.meta.id)
        self.assertNotIn("edge_kind", edge_projection.payload)
        self.assertNotIn("source_id", edge_projection.payload)
        self.assertNotIn("target_id", edge_projection.payload)
        self.assertTrue(edge_projection.payload["relation_semantics_hidden"])

    def test_same_input_is_deterministic(self):
        field = self._field()
        plan = compile_tribunal_composition(
            TribunalCompositionRequest(field, TribunalLineageProfile(method_views=("xrd",))), self.policy
        )
        request = TribunalEvidenceRequest(field, plan, self.state)
        a = compile_tribunal_evidence_bundle(request)
        b = compile_tribunal_evidence_bundle(request)
        self.assertEqual(a, b)
        self.assertEqual(a.bundle_fingerprint, b.bundle_fingerprint)

    def test_blocking_numeric_need_can_be_ready_with_target_only_payload(self):
        quantity = Quantity(
            self._meta("QTY", "quantity/1.0"),
            Decimal("0.434"),
            "%",
            "relative_lattice_change",
            self.scope,
        )
        need = AssessmentNeed(
            UncertaintyAxis.NUMERIC_MEASUREMENT,
            UncertaintyLevel.BLOCKING,
            True,
            (quantity.meta.id,),
            (quantity.meta.id,),
            "Assess decision-relevant measurement uncertainty",
            (AssessmentMethod.INTERVAL_OVERLAP,),
            ("typed numeric disposition or MissingEvidence",),
        )
        field = ReviewWorkField(
            self._meta("RWF", "review-work-field/1.0"), self.req, (quantity.meta.id,), (), (need,), (), (), (),
            (), ReviewReadiness.BLOCKED,
        )
        plan = compile_tribunal_composition(
            TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy
        )
        state = dict(self.state)
        state[quantity.meta.id] = quantity
        bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, state))
        measurement = self._slice(bundle, "measurement_specialist")
        self.assertEqual(measurement.status, EvidenceSliceStatus.READY)
        self.assertFalse(measurement.evidence_items)
        self.assertEqual({x.target_id for x in measurement.target_projections}, {quantity.meta.id})

    def test_missing_blocking_evidence_is_visible_not_backfilled(self):
        missing_evd = self.ids.new("EVD")
        need = AssessmentNeed(
            UncertaintyAxis.METHOD,
            UncertaintyLevel.BLOCKING,
            True,
            (self.claim.meta.id,),
            (missing_evd,),
            "Assess missing method evidence",
            (AssessmentMethod.METHOD_COMPATIBILITY,),
            ("typed disposition",),
        )
        field = ReviewWorkField(
            self._meta("RWF", "review-work-field/1.0"), self.req, (self.claim.meta.id,), (), (need,), (), (), (),
            (missing_evd,), ReviewReadiness.BLOCKED,
        )
        plan = compile_tribunal_composition(
            TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy
        )
        bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, self.state))
        methodologist = self._slice(bundle, "methodologist")
        self.assertEqual(methodologist.status, EvidenceSliceStatus.BLOCKED)
        self.assertIn(missing_evd, methodologist.missing_refs)
        self.assertFalse(methodologist.evidence_items)

    def test_plan_for_other_work_field_is_rejected(self):
        field_a = self._field()
        plan = compile_tribunal_composition(
            TribunalCompositionRequest(field_a, TribunalLineageProfile()), self.policy
        )
        field_b = self._field()
        with self.assertRaises(TribunalEvidenceError):
            compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field_b, plan, self.state))

    def test_cross_run_canonical_state_is_rejected(self):
        field = self._field()
        plan = compile_tribunal_composition(
            TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy
        )
        other_ids = EntityIdFactory(Clock(), random.Random(999))
        other_run = other_ids.new("RUN")
        bad_source = Source(
            EntityMeta(other_ids.new("SRC"), "source/1.0", 1, other_run, self.t, self.actor),
            "journal", "alien run", "doi:alien",
        )
        state = dict(self.state)
        state[bad_source.meta.id] = bad_source
        with self.assertRaises(TribunalEvidenceError):
            compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, state))

    def test_max_refs_is_deterministic_and_marks_partial(self):
        raw = yaml.safe_load((self.root / "config" / "tribunal_composition.yaml").read_text(encoding="utf-8"))
        raw["roles"]["evidence_auditor"]["evidence_view"]["max_refs"] = 1
        temp = self.root / "config" / "_tribunal_r42_maxrefs_test.yaml"
        try:
            temp.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
            policy = load_tribunal_composition_policy(temp)
            field = self._field()
            plan = compile_tribunal_composition(TribunalCompositionRequest(field, TribunalLineageProfile()), policy)
            bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, self.state))
            auditor = self._slice(bundle, "evidence_auditor")
            self.assertEqual(len(auditor.evidence_items), 1)
            self.assertTrue(auditor.truncated)
            self.assertEqual(auditor.status, EvidenceSliceStatus.PARTIAL)
            again = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, self.state))
            self.assertEqual(auditor.evidence_items, self._slice(again, "evidence_auditor").evidence_items)
        finally:
            temp.unlink(missing_ok=True)

    def test_prior_review_artifact_is_visible_only_when_policy_allows_it(self):
        raw = yaml.safe_load((self.root / "config" / "tribunal_composition.yaml").read_text(encoding="utf-8"))
        raw["roles"]["evidence_auditor"]["evidence_view"]["include_previous_conclusions"] = True
        temp = self.root / "config" / "_tribunal_r42_prior_test.yaml"
        try:
            temp.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
            policy = load_tribunal_composition_policy(temp)
            field = self._field()
            plan = compile_tribunal_composition(TribunalCompositionRequest(field, TribunalLineageProfile()), policy)
            prior = PriorReviewArtifact("PRELIM-X", "PreliminaryVerdict", (self.claim.meta.id,), {"verdict": "SUPPORTED"})
            bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, self.state, (prior,)))
            auditor = self._slice(bundle, "evidence_auditor")
            skeptic = self._slice(bundle, "skeptic")
            self.assertEqual([x.artifact_id for x in auditor.prior_review_artifacts], ["PRELIM-X"])
            self.assertFalse(skeptic.prior_review_artifacts)
        finally:
            temp.unlink(missing_ok=True)

    def test_serialization_contains_typed_slices_not_prompt_text(self):
        _, plan, bundle = self._bundle()
        raw = tribunal_evidence_bundle_to_dict(bundle)
        self.assertEqual(raw["schema_version"], "tribunal-evidence-bundle/1.0")
        self.assertEqual(raw["composition_fingerprint"], plan.composition_fingerprint)
        self.assertTrue(raw["slices"])
        self.assertNotIn("prompt", raw["slices"][0])
        self.assertNotIn("requested_view", raw["slices"][0])

    def test_slicing_does_not_mutate_canonical_state(self):
        before = {k: v for k, v in self.state.items()}
        self._bundle()
        self.assertEqual(before, self.state)
        self.assertEqual(self.claim.status, ClaimStatus.OPEN)


if __name__ == "__main__":
    unittest.main()
