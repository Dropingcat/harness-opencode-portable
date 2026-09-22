from __future__ import annotations

import json
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
    prior_review_artifact_from_argument,
)
from researcher_core.tribunal_role_runtime import JobCtlTribunalRoleAdapter, TribunalRoleRuntimeError
from researcher_core.uncertainty_field import (
    ReviewReadiness,
    build_review_work_field,
    build_uncertainty_profile,
    components_from_relation_assessment,
)


class Clock:
    def now_ms(self):
        return 1789272000000


class DeterministicXRDWorker:
    worker_id = "fixture.xrd-specialist/1.0"

    def execute(self, *, contract, evidence_slice, instruction):
        assert instruction.role_id == contract.role_id
        assert "XRD" in instruction.mission or "XRD" in instruction.objective
        evidence = evidence_slice.evidence_items[0]
        edge_target = next(x.target_id for x in evidence_slice.target_projections if x.target_id.namespace == "EDG")
        need_ref = contract.assigned_need_refs[0]
        return RoleWorkerDraft(
            position=ArgumentPosition.QUALIFY,
            summary="Peak-shift evidence is visible, but the slice does not independently separate stress from composition.",
            justification=(
                "The assigned XRD relation contains a post-nitriding peak shift. "
                "The visible evidence explicitly states that stress separation was not independently measured."
            ),
            cited_evidence_refs=(evidence.evidence_id,),
            cited_target_refs=(edge_target,),
            discoveries=(InquiryDiscovery(
                DiscoveryKind.METHOD_LIMITATION,
                "Residual-stress and compositional contributions are not independently separated in the visible evidence.",
                (need_ref,),
                target_refs=(edge_target,),
                evidence_refs=(evidence.evidence_id,),
                blocking=True,
            ),),
            additional_evidence_requests=(AdditionalEvidenceRequest(
                "Obtain a stress-sensitive XRD comparison or independent composition/phase measurement.",
                "The method uncertainty cannot be closed from the bounded first-pass slice.",
                (need_ref,),
                target_refs=(edge_target,),
                requested_evidence_kinds=("stress-sensitive XRD", "independent composition/phase evidence"),
            ),),
            metadata={"fixture_semantics": "deterministic structural E2E worker; not a production scientific verdict"},
        )


class InvalidCitationWorker:
    worker_id = "fixture.invalid-citation/1.0"

    def __init__(self, hidden_ref):
        self.hidden_ref = hidden_ref

    def execute(self, *, contract, evidence_slice, instruction):
        return RoleWorkerDraft(
            position=ArgumentPosition.CHALLENGE,
            summary="Attempt to use evidence outside the slice.",
            justification="This fixture must be rejected by the R4.3 admission boundary.",
            cited_evidence_refs=(self.hidden_ref,),
        )


class R43IndependentRoleExecutionE2E(unittest.TestCase):
    def test_r3_5_through_role_attempt_to_typed_argument_and_next_round_projection(self):
        root = Path(__file__).resolve().parents[2]
        policy = load_tribunal_composition_policy(root / "config" / "tribunal_composition.yaml")
        handbook = load_role_handbook(root / "config" / "tribunal_role_handbook.yaml", policy)
        ids = EntityIdFactory(Clock(), random.Random(619))
        actor = ActorRef("AGENT", "researcher")
        run = ids.new("RUN")
        req = ids.new("RRQ")
        scope = ids.new("SCP")
        t = datetime(2026, 9, 13, 13, 0, tzinfo=timezone.utc)

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
            meta("EVD", "evidence-span/1.0"),
            source.meta.id,
            "The BCC peak shifted after nitriding, while stress separation was not independently measured.",
            "p.6",
            "sha256:xrd-evidence",
        )
        edge = GraphEdge(
            meta("EDG", "graph-edge/1.0"),
            evd.meta.id,
            claim.meta.id,
            EdgeKind.SUPPORTS,
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
        profile = build_uncertainty_profile(
            target_id=edge.meta.id,
            target_revision=edge.meta.revision,
            components=components_from_relation_assessment(assessment),
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
        bundle = compile_tribunal_evidence_bundle(TribunalEvidenceRequest(field, plan, {
            claim.meta.id: claim,
            source.meta.id: source,
            evd.meta.id: evd,
            edge.meta.id: edge,
        }))
        xrd_slice = next(x for x in bundle.slices if x.role_id == "xrd_specialist")
        instruction = compile_role_instruction_pack(role_id="xrd_specialist", variant=RoleVariantKind.FIRST_PASS, handbook=handbook, policy=policy)
        contract = compile_inquiry_contract(
            plan=plan,
            evidence_slice=xrd_slice,
            work_field=field,
            id_factory=ids,
            actor=actor,
            created_at=t,
            role_instruction_id=instruction.instruction_id,
            role_instruction_fingerprint=instruction.instruction_fingerprint,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            parent_state = tmp_path / "parent.json"
            parent = job_ctl.create(
                "research-parent",
                {"schema": "research-parent-fixture/1.0", "request_id": str(req)},
                ["tribunal"],
            )
            job_ctl.save(parent, parent_state)

            runtime = JobCtlTribunalRoleAdapter(
                state_dir=tmp_path / "jobs",
                artifact_dir=tmp_path / "artifacts",
            )
            result = runtime.execute(
                parent_state_path=parent_state,
                contract=contract,
                evidence_slice=xrd_slice,
                worker=DeterministicXRDWorker(),
                instruction=instruction,
                id_factory=ids,
                actor=actor,
                created_at=t,
            )

            parent_after = job_ctl.load(parent_state)
            child = job_ctl.load(runtime.child_state_path(result.child_job_id))
            self.assertEqual(parent_after["children"][0]["status"], "COMPLETED")
            self.assertEqual(child["status"], "COMPLETED")
            self.assertEqual(child["attempts"][0]["status"], "COMPLETED")
            self.assertEqual(child["attempts"][0]["external_task_id"], str(contract.meta.id))
            self.assertEqual(child["stages"]["first_pass"]["status"], "COMPLETED")

            artifact_payload = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
            self.assertEqual(artifact_payload["schema"], "tribunal-role-execution-output/1.0")
            self.assertEqual(artifact_payload["argument"]["role_id"], "xrd_specialist")
            self.assertEqual(artifact_payload["argument"]["position"], "QUALIFY")
            self.assertEqual(result.argument.discoveries[0].kind, DiscoveryKind.METHOD_LIMITATION)
            self.assertTrue(result.argument.additional_evidence_requests)

            # Downstream/next-round seam: canonical R4.3 output can be projected
            # into R4.2's controlled prior-review envelope, where a later view
            # policy still decides whether another role may see it.
            prior = prior_review_artifact_from_argument(result.argument)
            self.assertEqual(prior.artifact_id, str(result.argument.meta.id))
            self.assertEqual(prior.artifact_type, "ArgumentArtifact/1.0")
            self.assertIn("QUALIFY", prior.payload["position"])

            # Semantic role variants do not silently change the inquiry phase.
            cross_instruction = compile_role_instruction_pack(
                role_id="xrd_specialist",
                variant=RoleVariantKind.CROSS_EXAM,
                handbook=handbook,
                policy=policy,
            )
            cross_contract = compile_inquiry_contract(
                plan=plan,
                evidence_slice=xrd_slice,
                work_field=field,
                id_factory=ids,
                actor=actor,
                created_at=t,
                role_instruction_id=cross_instruction.instruction_id,
                role_instruction_fingerprint=cross_instruction.instruction_fingerprint,
            )
            with self.assertRaises(TribunalRoleRuntimeError):
                runtime.execute(
                    parent_state_path=parent_state,
                    contract=cross_contract,
                    evidence_slice=xrd_slice,
                    worker=DeterministicXRDWorker(),
                    instruction=cross_instruction,
                    id_factory=ids,
                    actor=actor,
                    created_at=t,
                )

            # Fail-closed runtime path on the same upstream state: a second role
            # attempt that cites unseen evidence becomes FAILED_NO_OUTPUT rather
            # than a semantic OPEN or an admitted argument.
            bad_contract = compile_inquiry_contract(
                plan=plan,
                evidence_slice=xrd_slice,
                work_field=field,
                id_factory=ids,
                actor=actor,
                created_at=t,
                role_instruction_id=instruction.instruction_id,
                role_instruction_fingerprint=instruction.instruction_fingerprint,
            )
            bad_parent_state = tmp_path / "bad-parent.json"
            job_ctl.save(job_ctl.create("research-parent-bad", {"schema": "fixture/1.0"}, ["tribunal"]), bad_parent_state)
            hidden = ids.new("EVD")
            with self.assertRaises(TribunalInquiryError):
                runtime.execute(
                    parent_state_path=bad_parent_state,
                    contract=bad_contract,
                    evidence_slice=xrd_slice,
                    worker=InvalidCitationWorker(hidden),
                    instruction=instruction,
                    id_factory=ids,
                    actor=actor,
                    created_at=t,
                )
            bad_parent = job_ctl.load(bad_parent_state)
            bad_child_id = bad_parent["children"][0]["child_id"]
            bad_child = job_ctl.load(runtime.child_state_path(bad_child_id))
            self.assertEqual(bad_parent["children"][0]["status"], "FAILED")
            self.assertEqual(bad_child["status"], "FAILED_NO_OUTPUT")
            self.assertEqual(bad_child["attempts"][0]["status"], "FAILED")

        # Role output is not a state reducer.
        self.assertEqual(claim.status, ClaimStatus.OPEN)
        self.assertEqual(edge.meta.revision, 1)


if __name__ == "__main__":
    unittest.main()
