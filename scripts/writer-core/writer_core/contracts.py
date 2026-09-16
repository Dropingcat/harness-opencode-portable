# -*- coding: utf-8 -*-
"""writer_core.contracts — контракты фабрики письма (детерминированные).

Модели (pydantic v2, JSON-серизуемые):

  ResearchBundleLA  — упрощённый research-bundle, строится из claims/objects
                      гибридного артефакта (hybrid_extract);
  WriterContract    — контракт на один claim: что разрешено писать, с какой
                      модальностью/каузальностью, какие трансформации
                      запрещены, какие квалификаторы обязательны;
  Defect            — дефект RTT-диффа: defect_type + claim_id + span +
                      suggestion (вход constrained repair);
  VersionedArtifact — версионируемый артефакт с content_hash (sha256).

Функции-маппинги:
  research_bundle_from_artifact(artifact)  — гибридный артефакт -> ResearchBundleLA;
  writer_contract_from_claim(claim, digest) — claim (+digest) -> WriterContract.

Используется ТОЛЬКО stdlib + pydantic — тяжёлые модули гибрида сюда не
импортируются (CLI подгружает их лениво по командам).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator  # noqa: F401  (re-export)

# ---------------------------------------------------------------------------
# ResearchBundleLA
# ---------------------------------------------------------------------------

class SourceRef(BaseModel):
    """Источник ResearchBundle: uri + человекочитаемый title."""
    id: str = ""
    uri: str = ""
    title: str = ""


class BundleClaim(BaseModel):
    """Утверждение ResearchBundle: proposition + происхождение (span/источник)."""
    claim_id: str = ""
    proposition: str = ""
    source_id: str = ""
    span_start: int | None = None
    span_end: int | None = None
    qa_status: str = "PROPOSED"


class ResearchBundleLA(BaseModel):
    """Упрощённый ResearchBundle (по образцу full ResearchBundleLA).

    task_contract         — постановка задачи письма (тема/цель);
    sources[]             — источники;
    claims[]              — разрешённые утверждения (proposition);
    evidence_links[]      — claim_id -> source_id;
    contradictions[]      — пары конфликтующих claims;
    unresolved_questions[]— открытые вопросы (gaps);
    confidence_map        — claim_id -> уверенность (0..1).
    """
    schema_version: str = "writer_core.research_bundle_la.v1"
    task_contract: str = ""
    sources: list[SourceRef] = Field(default_factory=list)
    claims: list[BundleClaim] = Field(default_factory=list)
    evidence_links: list[dict] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence_map: dict[str, float] = Field(default_factory=dict)

    def to_contract_claims(self, default_scope: str = "",
                           default_modality: str = "assertive",
                           default_causal: str = "none") -> list["WriterContract"]:
        """Каждый claim бандла -> WriterContract (для draftcheck/планирования)."""
        out: list[WriterContract] = []
        for c in self.claims:
            out.append(writer_contract_from_claim(
                {"claim_id": c.claim_id, "raw_span": c.proposition},
                None,
                default_scope=default_scope,
                default_modality=default_modality,
                default_causal=default_causal,
            ))
        return out


# ---------------------------------------------------------------------------
# WriterContract
# ---------------------------------------------------------------------------

class WriterContract(BaseModel):
    """Контракт на ОДНО утверждение (маппится из LinguisticDigest/claims).

    claim_id               — id утверждения в контракте;
    proposition            — эталонная формулировка (source для RTT);
    scope                  — ограничение области (строка, '' = не задано);
    modality               — разрешённая модальность (assertive/possibility/...);
    causal_level           — разрешённая каузальность (none/weak/causal);
    forbidden_transformations — список запрещённых RTT-причин (RTTReason names);
    required_qualifiers    — обязательные квалификаторы ('' если не требуются);
    citation_policy        — политика цитирования ('' если не требуется).
    """
    claim_id: str
    proposition: str
    scope: str = ""
    modality: str = "assertive"
    causal_level: str = "none"
    forbidden_transformations: list[str] = Field(default_factory=list)
    required_qualifiers: list[str] = Field(default_factory=list)
    citation_policy: str = ""


# ---------------------------------------------------------------------------
# Defect (RTT-дифф -> constrained repair)
# ---------------------------------------------------------------------------

class Span(BaseModel):
    """Абсолютный span в тексте черновика."""
    start: int
    end: int
    text: str = ""


class Defect(BaseModel):
    """Дефект семантического RTT-диффа.

    defect_type — snake_case причина (например "causality_upgrade"),
    reason_code — канонический RTTReason ("CAUSALITY_UPGRADE"),
    claim_id    — claim контракта, которому сопоставлен span черновика,
    span        — фрагмент черновика (вход constrained repair),
    suggestion  — детерминированная подсказка ремонта.
    """
    defect_type: str
    claim_id: str
    span: Span | None = None
    suggestion: str = ""
    reason_code: str = ""


# ---------------------------------------------------------------------------
# VersionedArtifact
# ---------------------------------------------------------------------------

def content_sha256(content: str | bytes) -> str:
    """sha256 содержимого (детерминированный хэш для версионирования)."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class VersionedArtifact(BaseModel):
    """Версионируемый артефакт: id + version + content_hash + created_at.

    content_hash считается ФУНКЦИЕЙ от содержимого (content_sha256) — не
    принимается извне, чтобы исключить ручную подмену.
    """
    id: str
    version: str
    content_hash: str
    created_at: str = Field(default_factory=_utc_now_iso)

    @field_validator("content_hash")
    @classmethod
    def _validate_content_hash(cls, v: str) -> str:
        """content_hash обязан быть непустым sha256-hex (64 символа).

        Ручная подмена/пустой хэш — контрактное нарушение (fail-closed).
        """
        if not v or not isinstance(v, str):
            raise ValueError("content_hash не может быть пустым")
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("content_hash должен быть 64-символьным sha256-hex")
        return v.lower()

    @classmethod
    def create(cls, artifact_id: str, version: str, content: str | bytes,
               created_at: str | None = None) -> "VersionedArtifact":
        """Фабрика: считает content_hash из content (контрактно)."""
        return cls(
            id=artifact_id,
            version=version,
            content_hash=content_sha256(content),
            created_at=created_at or _utc_now_iso(),
        )


# ---------------------------------------------------------------------------
# маппинги из гибридных артефактов
# ---------------------------------------------------------------------------

def _norm_text(t: Any) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip()


def research_bundle_from_artifact(artifact: dict) -> ResearchBundleLA:
    """Гибридный артефакт (документ {paragraphs:[...]} или параграф) -> ResearchBundleLA.

    - claims: все v2 claims всех параграфов (raw_span/text), qa_status;
    - sources: paragraph_id -> SourceRef (uri = document_path);
    - evidence_links: [{claim_id, source_id}] по принадлежности claim параграфу;
    - contradictions: пусто (детектируется верхним тиром, не здесь);
    - unresolved_questions: claims с qa_status != GROUNDED;
    - confidence_map: 1.0 для GROUNDED, 0.5 для PROPOSED, 0.0 для UNGROUNDED.
    Детерминированно: только данные из артефакта, без LLM.
    """
    paras = artifact.get("paragraphs")
    if isinstance(paras, list):
        paragraph_list = paras
        document_path = artifact.get("document_path") or artifact.get("path") or ""
    else:
        # параграф-артефакт трактуется как документ из одного параграфа
        paragraph_list = [artifact]
        document_path = artifact.get("document_path") or ""

    bundle_claims: list[BundleClaim] = []
    evidence_links: list[dict] = []
    confidence_map: dict[str, float] = {}
    unresolved: list[str] = []
    sources: dict[str, SourceRef] = {}

    for i, p in enumerate(paragraph_list):
        pid = str(p.get("paragraph_id") or f"P{i:04d}")
        sources[pid] = SourceRef(id=pid, uri=document_path, title=pid)
        for ci, c in enumerate(p.get("claims") or []):
            cid = str(c.get("claim_id") or f"{pid}_C{ci}")
            qa = str(c.get("qa_status") or "PROPOSED")
            bundle_claims.append(BundleClaim(
                claim_id=cid,
                proposition=_norm_text(c.get("raw_span") or c.get("text") or ""),
                source_id=pid,
                span_start=c.get("start"),
                span_end=c.get("end"),
                qa_status=qa,
            ))
            evidence_links.append({"claim_id": cid, "source_id": pid})
            confidence_map[cid] = 1.0 if qa == "GROUNDED" else (
                0.5 if qa == "PROPOSED" else 0.0)
            if qa != "GROUNDED":
                unresolved.append(cid)

    return ResearchBundleLA(
        task_contract=artifact.get("task_contract") or "",
        sources=list(sources.values()),
        claims=bundle_claims,
        evidence_links=evidence_links,
        unresolved_questions=unresolved,
        confidence_map=confidence_map,
    )


# Маппинг digest -> параметры WriterContract (контрактно, детерминированно).
_MODALITY_OK = {"assertive", "possibility", "weak_inference", "causal_assertive",
                "boosted", "assertive_compat"}
_CAUSAL_OK = {"none", "weak", "causal"}


def writer_contract_from_claim(claim: dict, digest: dict | None = None,
                               default_scope: str = "",
                               default_modality: str = "assertive",
                               default_causal: str = "none") -> WriterContract:
    """claim (+digest из hybrid_extract) -> WriterContract.

    Дигест даёт разрешённые параметры: modality, causal_force, scope;
    forbidden_transformations — те RTT-причины, которые при диффе черновика
    против этого claim считаются дефектами (все причины, кроме безопасных).
    """
    digest = digest or {}
    scope_field = digest.get("scope") or {}
    mod = str(digest.get("modality") or default_modality)
    if mod not in _MODALITY_OK:
        mod = default_modality
    cf = str(digest.get("causal_force") or default_causal).lower()
    if cf in _CAUSAL_OK:
        causal = cf
    elif cf == "causal":
        causal = "causal"
    else:
        causal = default_causal

    prop = _norm_text(claim.get("raw_span") or claim.get("text")
                      or claim.get("proposition") or "")
    cid = str(claim.get("claim_id") or "C0")
    scope = str(scope_field.get("type") or default_scope)

    forbidden = [
        "CLAIM_OMISSION", "UNAUTHORIZED_CLAIM", "SCOPE_EXPANSION",
        "MODALITY_UPGRADE", "CAUSALITY_UPGRADE", "QUALIFIER_LOSS",
        "NEGATION_FLIP", "NUMERIC_DRIFT", "UNIT_DRIFT",
        "PRECISION_INFLATION", "UNCERTAINTY_LOSS",
        "DISCOURSE_CONNECTIVE_UNJUSTIFIED", "REFORMULATION_DRIFT",
    ]
    return WriterContract(
        claim_id=cid,
        proposition=prop,
        scope=scope,
        modality=mod,
        causal_level=causal,
        forbidden_transformations=forbidden,
        required_qualifiers=list(digest.get("affordances") or [])
        if isinstance(digest.get("affordances"), list) else [],
        citation_policy="",
    )