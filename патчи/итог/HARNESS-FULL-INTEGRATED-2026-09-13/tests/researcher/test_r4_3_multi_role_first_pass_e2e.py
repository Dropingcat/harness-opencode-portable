from __future__ import annotations

import random
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.jobs import job_ctl
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
from researcher_core.tribunal_evidence import (
    EvidenceViewKind,
    TribunalEvidenceRequest,
    compile_tribunal_evidence_bundle,
)
from researcher_core.tribunal_inquiry import (
    ArgumentPosition,
    RoleWorkerDraft,
    compile_inquiry_contract,
)
from researcher_core.tribunal_role_handbook import (
    RoleVariantKind,
    compile_role_instruction_pack,
    load_role_handbook,
)
from researcher_core.tribunal_role_runtime import JobCtlTribunalRoleAdapter
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


class BoundedFirstPassWorker:
    def __init__(self, role_id: str):
        self.worker_id = f"fixture.{role_id}/1.0"
        self.role_id = role_id

    def execute(self, *, contract, evidence_slice, instruction):
        assert contract.role_id == self.role_id == instruction.role_id == evidence_slice.role_id
        assert instruction.variant is RoleVariantKind.FIRST_PASS
        evidence = evidence_slice.evidence_items[0]
        targets = tuple(x.target_id for x in evidence_slice.target_projections)
        return RoleWorkerDraft(
            position=ArgumentPosition.QUALIFY,
            summary=f"{self.role_id} completed an independent bounded first pass.",
            justification=(
                f"The {self.role_id} fixture used only the evidence visible in its compiled slice "
                "and does not assert authoritative truth."
            ),
            cited_evidence_refs=(evidence.evidence_id,),
            cited_target_refs=targets[:1],
            metadata={"fixture_semantics": "multi-role structural E2E"},
        )


class R43MultiRoleFirstPassE2E(unittest.TestCase):
    def test_xrd_and_crystallography_roles_execute_independently_with_distinct_views(self):
        root = Path(__file__).resolve().parents[2]
        policy = load_tribunal_composition_policy(root / "config" / "tribunal_composition.yaml")
        handbook = load_role_handbook(root / "config" / "tribunal_role_handbook.yaml", policy)
        ids = EntityIdFactory(Clock(), random.Random(911))
        actor = ActorRef("AGENT", "researcher")
        run = ids.new("RUN")
        req = ids.new("RRQ")
        scope = ids.new("SCP")
        t = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)

        def meta(ns: str, schema: str) -> EntityMeta:
            return EntityMeta(ids.new(ns), schema, 1, run, t, actor)

        claim = Claim(
            meta("CLM", "claim/1.0"),
            "The observed BCC lattice change is structurally interpretable from the XRD data.",
            "the observed bcc lattice change is structurally interpretable from the xrd data",
            "method",
            scope,
            ClaimStatus.OPEN,
        )
        source = Source(meta("SRC", "source/1.0"), "journal", "XRD study", "doi:10/example", "sha256:src")
        evidence = EvidenceSpan(
            meta("EVD", "evidence-span/1.0"),
            source.meta.id,
            "The diffraction peak shifts after treatment and the phase assignment remains BCC in the measured interval.",
            "p.4",
            "sha256:evidence",
        )
        edge = GraphEdge(
            meta("EDG", "graph-edge/1.0"),
            evidence.meta.id,
            claim.meta.id,
            EdgeKind.SUPPORTS,
            {"scope_match": "MATCH", "directness": "DIRECT"},
        )
        need = AssessmentNeed(
            axis=UncertaintyAxis.METHOD,
            level=UncertaintyLevel.BLOCKING,
            blocking=True,
            target_refs=(edge.meta.id,),
            source_refs=(evidence.meta.id,),
            question="Can the XRD method support the structural interpretation?",
            assessment_methods=(AssessmentMethod.METHOD_COMPATIBILITY,),
            completion_criteria=("typed method assessment",),
            reason_codes=("MULTI_ROLE_E2E",),
        )
        field = ReviewWorkField(
            meta=meta("RWF", "review-work-field/1.0"),
            request_id=req,
            target_refs=(edge.meta.id,),
            uncertainty_profile_ids=(),
            assessment_needs=(need,),
            open_gap_ids=(),
            conflict_ids=(),
            relation_assessment_ids=(),
            evidence_refs=(evidence.meta.id,),
            readiness=ReviewReadiness.BLOCKED,
        )
        lineage = TribunalLineageProfile(disciplinary_views=("crystallography",), method_views=("xrd",))
        plan = compile_tribunal_composition(TribunalCompositionRequest(field, lineage), policy)
        bundle = compile_tribunal_evidence_bundle(
            TribunalEvidenceRequest(
                field,
                plan,
                {
                    claim.meta.id: claim,
                    source.meta.id: source,
                    evidence.meta.id: evidence,
                    edge.meta.id: edge,
                },
            )
        )

        slices = {x.role_id: x for x in bundle.slices}
        self.assertIn("xrd_specialist", slices)
        self.assertIn("crystallographer", slices)
        self.assertEqual(slices["xrd_specialist"].view_kind, EvidenceViewKind.METHOD_ONLY)
        self.assertEqual(slices["crystallographer"].view_kind, EvidenceViewKind.CLAIM_PLUS_SUPPORT)
        self.assertNotEqual(
            slices["xrd_specialist"].slice_fingerprint,
            slices["crystallographer"].slice_fingerprint,
        )

        instructions = {
            role_id: compile_role_instruction_pack(
                role_id=role_id,
                variant=RoleVariantKind.FIRST_PASS,
                handbook=handbook,
                policy=policy,
            )
            for role_id in ("xrd_specialist", "crystallographer")
        }
        self.assertNotEqual(
            instructions["xrd_specialist"].instruction_fingerprint,
            instructions["crystallographer"].instruction_fingerprint,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            parent_path = tmp_path / "parent.json"
            job_ctl.save(job_ctl.create("multi-role-parent", {"schema": "fixture/1.0"}, ["tribunal"]), parent_path)
            runtime = JobCtlTribunalRoleAdapter(state_dir=tmp_path / "jobs", artifact_dir=tmp_path / "artifacts")
            outputs = {}
            for role_id in ("xrd_specialist", "crystallographer"):
                contract = compile_inquiry_contract(
                    plan=plan,
                    evidence_slice=slices[role_id],
                    work_field=field,
                    id_factory=ids,
                    actor=actor,
                    created_at=t,
                    role_instruction_id=instructions[role_id].instruction_id,
                    role_instruction_fingerprint=instructions[role_id].instruction_fingerprint,
                )
                outputs[role_id] = runtime.execute(
                    parent_state_path=parent_path,
                    contract=contract,
                    evidence_slice=slices[role_id],
                    worker=BoundedFirstPassWorker(role_id),
                    instruction=instructions[role_id],
                    id_factory=ids,
                    actor=actor,
                    created_at=t,
                )

            parent = job_ctl.load(parent_path)
            self.assertEqual(len(parent["children"]), 2)
            self.assertTrue(all(x["status"] == "COMPLETED" for x in parent["children"]))
            self.assertEqual(outputs["xrd_specialist"].argument.role_id, "xrd_specialist")
            self.assertEqual(outputs["crystallographer"].argument.role_id, "crystallographer")
            self.assertNotEqual(
                outputs["xrd_specialist"].argument.meta.id,
                outputs["crystallographer"].argument.meta.id,
            )

        self.assertEqual(claim.status, ClaimStatus.OPEN)
        self.assertEqual(edge.meta.revision, 1)


if __name__ == "__main__":
    unittest.main()
