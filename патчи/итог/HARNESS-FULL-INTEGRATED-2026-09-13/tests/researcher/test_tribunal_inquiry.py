from __future__ import annotations

import random
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EntityMeta, EvidenceSpan, Source
from researcher_core.r0.enums import ClaimStatus, EdgeKind
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_composition import (
    TribunalCompositionRequest,
    TribunalLineageProfile,
    compile_tribunal_composition,
    load_tribunal_composition_policy,
)
from researcher_core.tribunal_evidence import TribunalEvidenceRequest, compile_tribunal_evidence_bundle
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook
from researcher_core.tribunal_inquiry import (
    AdditionalEvidenceRequest,
    ArgumentPosition,
    DiscoveryKind,
    InquiryDiscovery,
    RoleWorkerDraft,
    TribunalInquiryError,
    compile_inquiry_contract,
    materialize_role_worker_draft,
    validate_inquiry_contract_integrity,
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


class TribunalInquiryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root / "config" / "tribunal_composition.yaml")
        self.handbook = load_role_handbook(self.root / "config" / "tribunal_role_handbook.yaml", self.policy)
        self.ids = EntityIdFactory(Clock(), random.Random(531))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.req = self.ids.new("RRQ")
        self.scope = self.ids.new("SCP")
        self.t = datetime(2026, 9, 13, 12, 30, tzinfo=timezone.utc)

        def meta(ns, schema):
            return EntityMeta(self.ids.new(ns), schema, 1, self.run, self.t, self.actor)

        self.claim = Claim(meta("CLM", "claim/1.0"), "Claim", "claim", "causal", self.scope, ClaimStatus.OPEN)
        self.source = Source(meta("SRC", "source/1.0"), "journal", "Source", "doi:10/test", "sha256:test")
        self.evd = EvidenceSpan(meta("EVD", "evidence-span/1.0"), self.source.meta.id, "Visible evidence", "p.1", "sha256:evd")
        self.edge = GraphEdge(meta("EDG", "graph-edge/1.0"), self.evd.meta.id, self.claim.meta.id, EdgeKind.SUPPORTS, {})
        need = AssessmentNeed(
            axis=UncertaintyAxis.METHOD,
            level=UncertaintyLevel.BLOCKING,
            blocking=True,
            target_refs=(self.edge.meta.id,),
            source_refs=(self.evd.meta.id,),
            question="Does the method isolate the claimed effect?",
            assessment_methods=(AssessmentMethod.METHOD_COMPATIBILITY,),
            completion_criteria=("method-specific review",),
            reason_codes=("fixture",),
        )
        self.field = ReviewWorkField(
            meta=meta("RWF", "review-work-field/1.0"),
            request_id=self.req,
            target_refs=(self.edge.meta.id,),
            uncertainty_profile_ids=(),
            assessment_needs=(need,),
            open_gap_ids=(),
            conflict_ids=(),
            relation_assessment_ids=(),
            evidence_refs=(self.evd.meta.id,),
            readiness=ReviewReadiness.BLOCKED,
        )
        lineage = TribunalLineageProfile(disciplinary_views=("crystallography",), method_views=("xrd",))
        self.plan = compile_tribunal_composition(TribunalCompositionRequest(self.field, lineage), self.policy)
        state = {x.meta.id: x for x in (self.claim, self.source, self.evd, self.edge)}
        bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(self.field, self.plan, state))
        self.slice = next(x for x in bundle.slices if x.role_id == "xrd_specialist")

    def contract(self):
        instruction = compile_role_instruction_pack(role_id="xrd_specialist", variant=RoleVariantKind.FIRST_PASS, handbook=self.handbook, policy=self.policy)
        return compile_inquiry_contract(
            plan=self.plan,
            evidence_slice=self.slice,
            work_field=self.field,
            id_factory=self.ids,
            actor=self.actor,
            created_at=self.t,
            role_instruction_id=instruction.instruction_id,
            role_instruction_fingerprint=instruction.instruction_fingerprint,
        )

    def test_contract_binds_role_slice_needs_and_authority(self):
        contract = self.contract()
        validate_inquiry_contract_integrity(contract)
        self.assertEqual(contract.role_id, "xrd_specialist")
        self.assertEqual(contract.evidence_slice_fingerprint, self.slice.slice_fingerprint)
        self.assertEqual(contract.assigned_need_refs, self.slice.assigned_need_refs)
        self.assertEqual(contract.expected_output_contract, "ArgumentArtifact/1.0")
        self.assertIn("science.physics", contract.allowed_capabilities)

    def test_contract_integrity_rejects_tampering(self):
        contract = self.contract()
        tampered = replace(contract, token_budget=contract.token_budget + 1)
        with self.assertRaises(TribunalInquiryError):
            validate_inquiry_contract_integrity(tampered)

    def test_worker_output_cannot_cite_evidence_outside_slice(self):
        contract = self.contract()
        hidden = self.ids.new("EVD")
        draft = RoleWorkerDraft(
            ArgumentPosition.CHALLENGE,
            "Hidden evidence used",
            "Invalid",
            cited_evidence_refs=(hidden,),
        )
        with self.assertRaises(TribunalInquiryError):
            materialize_role_worker_draft(
                contract=contract,
                evidence_slice=self.slice,
                draft=draft,
                id_factory=self.ids,
                actor=self.actor,
                created_at=self.t,
            )

    def test_first_pass_materializes_typed_turn_argument_and_discovery(self):
        contract = self.contract()
        target = next(x.target_id for x in self.slice.target_projections if x.target_id.namespace == "EDG")
        need_ref = contract.assigned_need_refs[0]
        draft = RoleWorkerDraft(
            position=ArgumentPosition.QUALIFY,
            summary="The visible XRD evidence does not independently separate method effects.",
            justification="The bounded slice supports a peak shift but not an independent separation test.",
            cited_evidence_refs=(self.evd.meta.id,),
            cited_target_refs=(target,),
            discoveries=(InquiryDiscovery(
                DiscoveryKind.METHOD_LIMITATION,
                "Independent method separation is missing.",
                (need_ref,),
                target_refs=(target,),
                evidence_refs=(self.evd.meta.id,),
                blocking=True,
            ),),
            additional_evidence_requests=(AdditionalEvidenceRequest(
                "Can stress-sensitive XRD or an independent composition measurement separate the effects?",
                "Required to close the method uncertainty.",
                (need_ref,),
                target_refs=(target,),
                requested_evidence_kinds=("stress-sensitive XRD", "independent composition measurement"),
            ),),
        )
        artifacts = materialize_role_worker_draft(
            contract=contract,
            evidence_slice=self.slice,
            draft=draft,
            id_factory=self.ids,
            actor=self.actor,
            created_at=self.t,
        )
        self.assertEqual(artifacts.turn.meta.id.namespace, "IQT")
        self.assertEqual(artifacts.argument.meta.id.namespace, "ARG")
        self.assertEqual(artifacts.argument.source_turn_id, artifacts.turn.meta.id)
        self.assertEqual(artifacts.argument.discoveries[0].kind, DiscoveryKind.METHOD_LIMITATION)
        self.assertIn("reducers/admission", artifacts.argument.metadata["authority_boundary"])
        self.assertEqual(self.claim.status, ClaimStatus.OPEN)
        self.assertEqual(self.edge.meta.revision, 1)

    def test_semantic_open_is_valid_without_citations(self):
        contract = self.contract()
        draft = RoleWorkerDraft(
            position=ArgumentPosition.OPEN,
            summary="No disposition from the visible slice.",
            justification="The role cannot close the assigned uncertainty from this bounded input.",
            discoveries=(InquiryDiscovery(
                DiscoveryKind.MISSING_EVIDENCE,
                "Additional evidence is required.",
                (contract.assigned_need_refs[0],),
                blocking=True,
            ),),
        )
        artifacts = materialize_role_worker_draft(
            contract=contract,
            evidence_slice=self.slice,
            draft=draft,
            id_factory=self.ids,
            actor=self.actor,
            created_at=self.t,
        )
        self.assertEqual(artifacts.argument.position, ArgumentPosition.OPEN)


if __name__ == "__main__":
    unittest.main()
