from __future__ import annotations

import random
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_composition import (
    TribunalCompositionRequest,
    TribunalLineageProfile,
    compile_tribunal_composition,
    load_tribunal_composition_policy,
)
from researcher_core.tribunal_role_handbook import (
    RoleVariantKind,
    TribunalRoleHandbook,
    TribunalRoleHandbookError,
    compile_role_instruction_pack,
    draft_handbook_entry_skeleton,
    handbook_fill_requests_for_plan,
    load_role_handbook,
    validate_role_instruction_pack_integrity,
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


class TribunalRoleHandbookTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root / "config" / "tribunal_composition.yaml")
        self.handbook = load_role_handbook(self.root / "config" / "tribunal_role_handbook.yaml", self.policy)
        self.ids = EntityIdFactory(Clock(), random.Random(733))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.req = self.ids.new("RRQ")
        self.claim = self.ids.new("CLM")
        self.evd = self.ids.new("EVD")
        self.t = datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc)

    def field_plan_lineage(self):
        need = AssessmentNeed(
            axis=UncertaintyAxis.METHOD,
            level=UncertaintyLevel.BLOCKING,
            blocking=True,
            target_refs=(self.claim,),
            source_refs=(self.evd,),
            question="Assess XRD method compatibility",
            assessment_methods=(AssessmentMethod.METHOD_COMPATIBILITY,),
            completion_criteria=("typed method disposition",),
            reason_codes=("fixture",),
        )
        field = ReviewWorkField(
            meta=EntityMeta(self.ids.new("RWF"), "review-work-field/1.0", 1, self.run, self.t, self.actor),
            request_id=self.req,
            target_refs=(self.claim,),
            uncertainty_profile_ids=(),
            assessment_needs=(need,),
            open_gap_ids=(), conflict_ids=(), relation_assessment_ids=(), evidence_refs=(self.evd,),
            readiness=ReviewReadiness.BLOCKED,
        )
        lineage = TribunalLineageProfile(disciplinary_views=("crystallography",), method_views=("xrd",))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, lineage), self.policy)
        return field, plan, lineage

    def test_handbook_semantics_do_not_contain_authority_fields(self):
        xrd = self.handbook.entries["xrd_specialist"]
        self.assertIn(RoleVariantKind.FIRST_PASS, xrd.variants)
        pack = compile_role_instruction_pack(
            role_id="xrd_specialist",
            variant=RoleVariantKind.FIRST_PASS,
            handbook=self.handbook,
            policy=self.policy,
        )
        self.assertTrue(pack.instruction_id.startswith("RHI-"))
        self.assertEqual(pack.expected_output_contract, "ArgumentArtifact/1.0")
        self.assertTrue(pack.stop_conditions)
        self.assertTrue(any("OPEN" in item for item in pack.stop_conditions))
        self.assertNotIn("allowed_tools", pack.metadata)
        self.assertIn("semantic guidance only", pack.metadata["authority_boundary"])
        validate_role_instruction_pack_integrity(pack)
        with self.assertRaises(TribunalRoleHandbookError):
            validate_role_instruction_pack_integrity(replace(pack, objective=pack.objective + " tampered"))

    def test_code_emits_fill_request_when_selected_role_has_no_handbook_entry(self):
        field, plan, lineage = self.field_plan_lineage()
        entries = dict(self.handbook.entries)
        entries.pop("xrd_specialist")
        incomplete = TribunalRoleHandbook(
            handbook_id=self.handbook.handbook_id,
            version=self.handbook.version,
            entries=MappingProxyType(entries),
            handbook_hash=self.handbook.handbook_hash,
            source_path=self.handbook.source_path,
        )
        requests = handbook_fill_requests_for_plan(
            plan=plan,
            work_field=field,
            lineage=lineage,
            handbook=incomplete,
            policy=self.policy,
        )
        xrd_request = next(x for x in requests if x.role_id == "xrd_specialist")
        self.assertEqual(xrd_request.uncertainty_axes, ("METHOD",))
        self.assertIn("METHOD_COMPATIBILITY", xrd_request.assessment_methods)
        self.assertIn("xrd", xrd_request.lineage_tags)
        self.assertEqual(xrd_request.reason_codes, ("HANDBOOK_ENTRY_MISSING",))

        draft = draft_handbook_entry_skeleton(xrd_request)
        self.assertEqual(draft["admission_status"], "PROPOSAL_ONLY")
        self.assertNotIn("allowed_tools", draft)
        self.assertNotIn("allowed_capabilities", draft)
        self.assertEqual(draft["source_request"]["policy_hash"], plan.policy_hash)

    def test_current_selected_roles_have_first_pass_guidance(self):
        field, plan, lineage = self.field_plan_lineage()
        requests = handbook_fill_requests_for_plan(
            plan=plan,
            work_field=field,
            lineage=lineage,
            handbook=self.handbook,
            policy=self.policy,
        )
        self.assertEqual(requests, ())
        self.assertNotIn("advocate", (*plan.permanent_roles, *plan.dynamic_roles))

    def test_role_variants_are_semantic_modes_not_new_authority(self):
        challenger = compile_role_instruction_pack(
            role_id="skeptic",
            variant=RoleVariantKind.CHALLENGER,
            handbook=self.handbook,
            policy=self.policy,
        )
        cross = compile_role_instruction_pack(
            role_id="xrd_specialist",
            variant=RoleVariantKind.CROSS_EXAM,
            handbook=self.handbook,
            policy=self.policy,
        )
        self.assertNotEqual(challenger.instruction_id, cross.instruction_id)
        self.assertEqual(challenger.expected_output_contract, "ArgumentArtifact/1.0")
        self.assertEqual(cross.expected_output_contract, "ArgumentArtifact/1.0")
        self.assertNotIn("allowed_capabilities", challenger.metadata)

    def test_code_emits_fill_request_for_missing_variant(self):
        field, plan, lineage = self.field_plan_lineage()
        requests = handbook_fill_requests_for_plan(
            plan=plan,
            work_field=field,
            lineage=lineage,
            handbook=self.handbook,
            policy=self.policy,
            required_variant=RoleVariantKind.CHALLENGER,
        )
        xrd_request = next(x for x in requests if x.role_id == "xrd_specialist")
        self.assertEqual(xrd_request.reason_codes, ("HANDBOOK_VARIANT_MISSING",))
        draft = draft_handbook_entry_skeleton(xrd_request)
        self.assertIn("challenger", draft["variants"])



if __name__ == "__main__":
    unittest.main()
