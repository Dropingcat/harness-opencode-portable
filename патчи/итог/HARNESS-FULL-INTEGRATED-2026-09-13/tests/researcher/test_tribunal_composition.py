from __future__ import annotations

import random
import unittest
from dataclasses import replace

import yaml
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.research_planning import ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchDOM
from researcher_core.tribunal_composition import (
    EvidenceViewKind,
    TribunalCompositionError,
    TribunalCompositionRequest,
    TribunalLineageProfile,
    compile_tribunal_composition,
    lineage_profile_from_research_dom,
    load_tribunal_composition_policy,
    tribunal_composition_plan_to_dict,
    validate_tribunal_composition_plan_integrity,
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


class TribunalCompositionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root / "config" / "tribunal_composition.yaml")
        self.ids = EntityIdFactory(Clock(), random.Random(211))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.req = self.ids.new("RRQ")
        self.claim = self.ids.new("CLM")
        self.evidence = self.ids.new("EVD")
        self.t = datetime(2026, 9, 13, 8, 0, tzinfo=timezone.utc)

    def _need(self, *, axis, methods, blocking=True):
        return AssessmentNeed(
            axis=axis,
            level=UncertaintyLevel.BLOCKING if blocking else UncertaintyLevel.MATERIAL,
            blocking=blocking,
            target_refs=(self.claim,),
            source_refs=(self.evidence,),
            question=f"Assess {axis.value}",
            assessment_methods=tuple(methods),
            completion_criteria=("typed disposition",),
            reason_codes=("fixture",),
        )

    def _field(self, *needs):
        return ReviewWorkField(
            meta=EntityMeta(self.ids.new("RWF"), "review-work-field/1.0", 1, self.run, self.t, self.actor),
            request_id=self.req,
            target_refs=(self.claim,),
            uncertainty_profile_ids=(),
            assessment_needs=tuple(needs),
            open_gap_ids=(), conflict_ids=(), relation_assessment_ids=(), evidence_refs=(self.evidence,),
            readiness=ReviewReadiness.BLOCKED if any(n.blocking for n in needs) else ReviewReadiness.NEEDS_REVIEW,
        )

    def test_same_input_same_policy_identical_plan(self):
        field = self._field(self._need(axis=UncertaintyAxis.CONFLICT, methods=(AssessmentMethod.CONFLICT_ANALYSIS,)))
        request = TribunalCompositionRequest(field, TribunalLineageProfile())
        a = compile_tribunal_composition(request, self.policy)
        b = compile_tribunal_composition(request, self.policy)
        self.assertEqual(a, b)
        self.assertEqual(a.composition_fingerprint, b.composition_fingerprint)
        self.assertEqual(a.policy_hash, self.policy.policy_hash)

    def test_blocking_numeric_gets_measurement_specialist(self):
        field = self._field(self._need(
            axis=UncertaintyAxis.NUMERIC_MEASUREMENT,
            methods=(AssessmentMethod.INTERVAL_OVERLAP, AssessmentMethod.EXPERIMENTAL_RETEST),
        ))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy)
        self.assertIn("measurement_specialist", plan.dynamic_roles)
        self.assertIn("measurement_specialist", plan.assignments[0].role_ids)

    def test_xrd_method_uncertainty_adds_xrd_and_crystallography_expertise(self):
        field = self._field(self._need(axis=UncertaintyAxis.METHOD, methods=(AssessmentMethod.METHOD_COMPATIBILITY,)))
        lineage = TribunalLineageProfile(disciplinary_views=("crystallography",), method_views=("XRD",))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, lineage), self.policy)
        self.assertIn("xrd_specialist", plan.dynamic_roles)
        self.assertIn("crystallographer", plan.dynamic_roles)

    def test_conflict_has_skeptical_coverage(self):
        field = self._field(self._need(axis=UncertaintyAxis.CONFLICT, methods=(AssessmentMethod.CONFLICT_ANALYSIS,)))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy)
        self.assertIn("skeptic", plan.assignments[0].role_ids)

    def test_fresh_context_contract_cannot_see_previous_conclusions(self):
        skeptic = self.policy.roles["skeptic"]
        self.assertEqual(skeptic.evidence_view.kind, EvidenceViewKind.FRESH_CONTEXT)
        self.assertFalse(skeptic.evidence_view.include_previous_conclusions)
        self.assertFalse(skeptic.evidence_view.include_provenance)

    def test_assessment_need_refs_are_content_addressed_not_position_only(self):
        need = self._need(axis=UncertaintyAxis.CONFLICT, methods=(AssessmentMethod.CONFLICT_ANALYSIS,))
        plan = compile_tribunal_composition(TribunalCompositionRequest(self._field(need), TribunalLineageProfile()), self.policy)
        self.assertTrue(plan.assignments[0].need_ref.key.startswith("ANR-"))
        self.assertEqual(plan.assignments[0].need_ref.ordinal, 0)

    def test_unknown_role_in_policy_fails_closed(self):
        text = (self.root / "config" / "tribunal_composition.yaml").read_text(encoding="utf-8")
        bad = text.replace("permanent_roles:\n  - critic", "permanent_roles:\n  - imaginary_role\n  - critic")
        path = self.root / "config" / "_tribunal_bad_test.yaml"
        try:
            path.write_text(bad, encoding="utf-8")
            with self.assertRaises(TribunalCompositionError):
                load_tribunal_composition_policy(path)
        finally:
            path.unlink(missing_ok=True)

    def test_synonymous_dynamic_roles_are_deduplicated_by_equivalence_group(self):
        policy_path = self.root / "config" / "tribunal_composition.yaml"
        raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        alias = dict(raw["roles"]["xrd_specialist"])
        alias["label"] = "X-ray Diffraction Expert Alias"
        alias["selection_priority"] = 50
        alias["equivalence_group"] = "xrd_specialist"
        raw["roles"]["xray_diffraction_alias"] = alias
        temp = self.root / "config" / "_tribunal_synonym_test.yaml"
        try:
            temp.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
            policy = load_tribunal_composition_policy(temp)
            field = self._field(self._need(axis=UncertaintyAxis.METHOD, methods=(AssessmentMethod.METHOD_COMPATIBILITY,)))
            lineage = TribunalLineageProfile(method_views=("xrd",))
            plan = compile_tribunal_composition(TribunalCompositionRequest(field, lineage), policy)
            self.assertIn("xrd_specialist", plan.dynamic_roles)
            self.assertNotIn("xray_diffraction_alias", plan.dynamic_roles)
        finally:
            temp.unlink(missing_ok=True)



    def test_plan_integrity_fingerprint_covers_role_brief_authority(self):
        field = self._field(self._need(axis=UncertaintyAxis.CONFLICT, methods=(AssessmentMethod.CONFLICT_ANALYSIS,)))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy)
        validate_tribunal_composition_plan_integrity(plan)
        briefs = list(plan.role_briefs)
        idx = next(i for i, brief in enumerate(briefs) if brief.role_id == "skeptic")
        briefs[idx] = replace(briefs[idx], token_budget=briefs[idx].token_budget + 1)
        tampered = replace(plan, role_briefs=tuple(briefs))
        with self.assertRaises(TribunalCompositionError):
            validate_tribunal_composition_plan_integrity(tampered)

    def test_plan_serialization_is_typed_and_stable(self):
        field = self._field(self._need(axis=UncertaintyAxis.CONFLICT, methods=(AssessmentMethod.CONFLICT_ANALYSIS,)))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy)
        raw = tribunal_composition_plan_to_dict(plan)
        self.assertEqual(raw["schema_version"], "tribunal-composition-plan/1.0")
        self.assertEqual(raw["policy_hash"], self.policy.policy_hash)
        self.assertEqual(raw["assignments"][0]["need_ref"]["key"], plan.assignments[0].need_ref.key)

    def test_research_dom_lineage_compiles_without_free_text_global_inference(self):
        root = ResearchCard(EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run, self.t, self.actor), self.req, ResearchCardKind.OBJECTIVE, "study", status=ResearchCardStatus.ACTIVE)
        discipline = ResearchCard(EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run, self.t, self.actor), self.req, ResearchCardKind.DISCIPLINARY_VIEW, "Crystallography", parent_id=root.meta.id, dimensions={"discipline": "crystallography"})
        method = ResearchCard(EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run, self.t, self.actor), self.req, ResearchCardKind.METHOD_VIEW, "XRD", parent_id=discipline.meta.id, dimensions={"method": "x-ray diffraction"})
        dom = ResearchDOM(EntityMeta(self.ids.new("RDM"), "research-dom/1.0", 1, self.run, self.t, self.actor), self.req, root.meta.id, {root.meta.id: root, discipline.meta.id: discipline, method.meta.id: method})
        profile = lineage_profile_from_research_dom(dom, method.meta.id)
        self.assertIn("crystallography", profile.disciplinary_views)
        self.assertIn("xrd", profile.method_views)


    def test_composition_plan_has_no_authoritative_state_objects(self):
        field = self._field(self._need(axis=UncertaintyAxis.CONFLICT, methods=(AssessmentMethod.CONFLICT_ANALYSIS,)))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, TribunalLineageProfile()), self.policy)
        self.assertFalse(hasattr(plan, "claim_status"))
        self.assertFalse(hasattr(plan, "graph_edges"))
        self.assertFalse(hasattr(plan, "gaps"))
        self.assertIn("composition only", plan.metadata["authority_boundary"])


if __name__ == "__main__":
    unittest.main()
