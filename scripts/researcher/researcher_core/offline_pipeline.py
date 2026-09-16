"""Dependency-free offline research pipeline smoke path.

This is not the production orchestrator. It wires the already-tested local
capsules and in-memory registry into one deterministic flow so the target
artifact can be exercised end-to-end before SQLite/MCP/LLM integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pathlib import Path

from researcher_core.artifact_builder import build_minimal_service_artifact, render_artifact_yaml, render_minimal_yaml
from researcher_core.capsules import CapsuleRequest
from researcher_core.guard import scan_text, scan_text_with_p2
from researcher_core.policy import load_policy
from researcher_core.local_capsules import (
    LocalDocumentExtractionCapsule,
    LocalTextClaimExtractionCapsule,
    observation_to_proposal_batch,
    observation_to_source_evidence,
)
from researcher_core.r0.commands import ActorRef, CommandEnvelope, CommandResult
from researcher_core.r0.entities import EvidenceSpan, Source
from researcher_core.r0.ids import EntityId
from researcher_core.r0.projections import Snapshot
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, ProposalBatch, SequenceClock


@dataclass(frozen=True, slots=True)
class OfflinePipelineResult:
    command_result: CommandResult
    sources: tuple[Source, ...]
    evidence_spans: tuple[EvidenceSpan, ...]
    artifact: dict[str, Any]
    artifact_yaml: str


class OfflineResearchPipeline:
    """Small orchestrator for local document smoke tests."""

    def __init__(self, clock: SequenceClock | None = None, random_source: CycleRandom | None = None) -> None:
        self.clock = clock or SequenceClock()
        self.random_source = random_source or CycleRandom()
        self.registry = InMemoryClaimRegistry(self.clock, self.random_source)
        self.document_capsule = LocalDocumentExtractionCapsule()
        self.claim_capsule = LocalTextClaimExtractionCapsule()

    def run_document(self, *, run_id: EntityId, operation_id: EntityId, correlation_id: EntityId, actor: ActorRef, title: str, text: str, locator: str) -> OfflinePipelineResult:
        document_observation = self.document_capsule.run(
            CapsuleRequest(
                request_id=operation_id,
                run_id=run_id,
                capability="document.extract_source_evidence",
                actor=actor,
                payload={"document_id": str(operation_id), "title": title, "text": text, "locator": locator},
            )
        )
        sources, evidence_spans = observation_to_source_evidence(document_observation)
        # Guard block (целиком P0+P2 polza) перед admit — как в doc_guard для researcher/оркестратора
        # P0 всегда, P2 — tie-breaker для untrusted low/no-match, простенькая lunaris оставлена
        try:
            policy = load_policy(Path.cwd())
            p2_heuristic = policy.heuristics.get("research.guard.p2_enabled")
            guard_heuristic = policy.heuristics.get("research.guard.enabled")
            p2_enabled = bool(p2_heuristic.value[0]) if p2_heuristic else False
            guard_enabled = bool(guard_heuristic.value[0]) if guard_heuristic else True
        except Exception:
            p2_enabled = False
            guard_enabled = True
        filtered_evidence: list[EvidenceSpan] = []
        for span in evidence_spans:
            if not guard_enabled:
                filtered_evidence.append(span)
                continue
            # internal → P0 only (WEAK_RU low), untrusted → P0+P2
            if p2_enabled:
                report = scan_text_with_p2(span.exact_text, field="evidence_span.exact_text", provenance="internal", tool="read", use_p2=True)
            else:
                report = scan_text(span.exact_text, field="evidence_span.exact_text", provenance="internal", tool="read")
            if report.verdict == "PASS":
                filtered_evidence.append(span)
        evidence_spans = tuple(filtered_evidence)
        claim_observation = self.claim_capsule.run(
            CapsuleRequest(
                request_id=operation_id,
                run_id=run_id,
                capability="text.extract_numeric_claims",
                actor=actor,
                payload={"text": text},
            )
        )
        claim_batch = observation_to_proposal_batch(claim_observation)
        batch = ProposalBatch(
            claims=claim_batch.claims,
            quantities=claim_batch.quantities,
            sources=sources,
            evidence_spans=evidence_spans,
            edges=claim_batch.edges,
        )
        command = CommandEnvelope(
            command_id=operation_id,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=run_id,
            actor=actor,
            idempotency_key=f"offline:{operation_id}",
            expected_revisions={},
            causation_id=None,
            correlation_id=correlation_id,
            payload={"proposal_batch": batch},
        )
        command_result = self.registry.execute(command)
        snapshot = self.registry.snapshots[-1] if self.registry.snapshots else Snapshot(
            snapshot_id=EntityId.new("SNP", self.clock, self.random_source),
            event_offset=len(self.registry.events),
            entity_revisions={},
            stop_reason="offline_pipeline_complete",
        )
        artifact = build_minimal_service_artifact(snapshot, self.registry.state_snapshot(), title)
        return OfflinePipelineResult(
            command_result=command_result,
            sources=sources,
            evidence_spans=evidence_spans,
            artifact=artifact,
            artifact_yaml=render_minimal_yaml(artifact),
        )
