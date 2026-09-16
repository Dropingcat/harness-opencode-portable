"""Offline capsules used before real MCP/skill adapters are restored."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Mapping

from researcher_core.capsules import CapsuleDescriptor, CapsuleObservation, CapsuleRequest, SideEffectClass, assert_capsule_observation_is_untrusted
from researcher_core.r0.entities import ClaimProposal, EntityMeta, EvidenceSpan, QuantityProposal, Source
from researcher_core.r0.ids import EntityId
from researcher_core.r0.registry import ProposalBatch


_PERCENT_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
_ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ENTITY_ID_SUFFIX_LENGTH = 26  # debt-scan: ignore-line -- EntityId ULID wire suffix length.
_FIXED_CREATED_AT = datetime.fromtimestamp(0, tz=UTC)


class LocalTextClaimExtractionCapsule:
    """Deterministic offline capsule that extracts one simple numeric claim."""

    descriptor = CapsuleDescriptor(
        capsule_id="local.text_claim_extraction",
        version="0.1.0",
        capabilities=("llm.extract_claims", "text.extract_numeric_claims"),
        side_effect_class=SideEffectClass.READ_ONLY,
        input_schema_version="local-text/0.1",
        output_schema_version="proposal-batch-observation/0.1",
        policy_keys=("capsule.local_text.max_chars",),
    )

    def run(self, request: CapsuleRequest) -> CapsuleObservation:
        text = request.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("payload.text is required")
        match = _PERCENT_RE.search(text)
        claims: tuple[ClaimProposal, ...]
        quantities: tuple[QuantityProposal, ...]
        if match is None:
            claims = ()
            quantities = ()
        else:
            value = Decimal(match.group("value"))
            claims = (
                ClaimProposal(
                    temp_id="tmp-local-claim-1",
                    proposition=text.strip(),
                    proposed_type="quantitative",
                    proposed_scope={"capsule": self.descriptor.capsule_id},
                    source_span_ref=None,
                    extraction_run_id=request.request_id,
                ),
            )
            quantities = (
                QuantityProposal(
                    temp_id="tmp-local-quantity-1",
                    value=value,
                    unit="%",
                    measured_property="percentage_value",
                    source_span_ref=None,
                    extraction_run_id=request.request_id,
                ),
            )
        observation = CapsuleObservation(
            request_id=request.request_id,
            capsule_id=self.descriptor.capsule_id,
            capability=request.capability,
            output_schema_version=self.descriptor.output_schema_version,
            payload={"claims": claims, "quantities": quantities},
            provenance={"capsule_version": self.descriptor.version, "method": "regex_percent_v1"},
        )
        assert_capsule_observation_is_untrusted(observation)
        return observation


class LocalDocumentExtractionCapsule:
    """Deterministic offline capsule that extracts a local document source and exact evidence span."""

    descriptor = CapsuleDescriptor(
        capsule_id="local.document_extraction",
        version="0.1.0",
        capabilities=("document.extract_source_evidence", "local.extract_document"),
        side_effect_class=SideEffectClass.READ_ONLY,
        input_schema_version="local-document/0.1",
        output_schema_version="source-evidence-observation/0.1",
        policy_keys=("capsule.local_document.max_chars",),
    )

    def run(self, request: CapsuleRequest) -> CapsuleObservation:
        document_id = _required_str(request.payload, "document_id")
        title = _required_str(request.payload, "title")
        text = _required_str(request.payload, "text")
        locator = _required_str(request.payload, "locator")
        content_hash = _sha256_tag(text)
        source_id = _entity_id_from_seed("SRC", f"{document_id}\n{locator}\n{content_hash}")
        evidence_id = _entity_id_from_seed("EVD", f"{document_id}\n{locator}\n{text}")
        source = Source(
            meta=_meta(source_id, request),
            source_type="local_document",
            title=title,
            locator=locator,
            content_hash=content_hash,
        )
        evidence = EvidenceSpan(
            meta=_meta(evidence_id, request),
            source_id=source_id,
            exact_text=text,
            locator=locator,
            text_hash=_sha256_tag(text),
        )
        observation = CapsuleObservation(
            request_id=request.request_id,
            capsule_id=self.descriptor.capsule_id,
            capability=request.capability,
            output_schema_version=self.descriptor.output_schema_version,
            payload={"sources": (source,), "evidence_spans": (evidence,)},
            provenance={
                "capsule_version": self.descriptor.version,
                "method": "local_exact_document_v1",
                "document_id": document_id,
            },
        )
        assert_capsule_observation_is_untrusted(observation)
        return observation


def observation_to_proposal_batch(observation: CapsuleObservation) -> ProposalBatch:
    claims = observation.payload.get("claims", ())
    quantities = observation.payload.get("quantities", ())
    if not isinstance(claims, tuple) or not isinstance(quantities, tuple):
        raise TypeError("observation payload must contain tuple claims and quantities")
    if not claims and not quantities:
        raise ValueError("observation payload produced no proposals")
    return ProposalBatch(claims=claims, quantities=quantities)


def observation_to_source_evidence(observation: CapsuleObservation) -> tuple[tuple[Source, ...], tuple[EvidenceSpan, ...]]:
    sources = observation.payload.get("sources", ())
    evidence_spans = observation.payload.get("evidence_spans", ())
    if not isinstance(sources, tuple) or not isinstance(evidence_spans, tuple):
        raise TypeError("observation payload must contain tuple sources and evidence_spans")
    if not all(isinstance(source, Source) for source in sources):
        raise TypeError("sources must contain Source entities")
    if not all(isinstance(evidence, EvidenceSpan) for evidence in evidence_spans):
        raise TypeError("evidence_spans must contain EvidenceSpan entities")
    return sources, evidence_spans


def _required_str(payload: object, key: str) -> str:
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload.{key} is required")
    return value


def _sha256_tag(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def _entity_id_from_seed(prefix: str, seed: str) -> EntityId:
    digest = sha256(f"{prefix}\n{seed}".encode("utf-8")).digest()
    suffix = "".join(_ID_ALPHABET[byte % len(_ID_ALPHABET)] for byte in digest[:_ENTITY_ID_SUFFIX_LENGTH])
    return EntityId(f"{prefix}_{suffix}")


def _meta(entity_id: EntityId, request: CapsuleRequest) -> EntityMeta:
    return EntityMeta(
        id=entity_id,
        schema_version="r0-entity/0.1",
        revision=1,
        run_id=request.run_id,
        created_at=_FIXED_CREATED_AT,
        created_by=request.actor,
    )
