"""Build a runtime LinguisticDigest from T0 signals (deterministic, no LLM).

Uses the minimal runtime-owned pydantic models.
T0 signals (t0_ru.py) are mapped 1:1 to LinguisticIssue types; every
heuristic-driven issue records details["heuristic"] for downstream tier policy.
"""
from __future__ import annotations

import uuid

from writer_core.linguistic_models import (
    AffordanceSet,
    Impact,
    LinguisticDigest,
    LinguisticIssue,
)

from t0_ru import T0Sentence, analyze_sentence, build_scope_field  # noqa: E402


def _issue(itype: str, impact: Impact, details: dict) -> LinguisticIssue:
    return LinguisticIssue(
        id=f"issue-{uuid.uuid4().hex[:8]}",
        type=itype,
        target="sentence",
        impact=impact,
        details=details,
    )


def _main_statement(s: T0Sentence) -> dict:
    return {"predicate": s.force_expr or "assertion", "text": s.text[:300]}


def build_digest(text: str) -> LinguisticDigest:
    s = analyze_sentence(text)
    issues: list[LinguisticIssue] = []

    # ---- m2_t0: per-sentence risk signals (T0 deterministic heuristics) ----
    if s.modality_upgrade:
        issues.append(_issue("MODALITY_UPGRADE", Impact.HIGH, {
            "force": s.force,
            "force_expr": s.force_expr,
            "heuristic": "boosted_without_qualifier",
        }))
    if s.causality_upgrade:
        issues.append(_issue("CAUSALITY_UPGRADE", Impact.HIGH, {
            "causal_force": "CAUSAL",
            "heuristic": "causal_marker_without_hedge",
        }))
    if s.scope_expansion:
        issues.append(_issue("SCOPE_EXPANSION", Impact.MEDIUM, {
            "head": s.scope_expansion_head,
            "heuristic": "scope_np_without_research_attr",
        }))
    if s.universals and not s.scope_restricted:
        issues.append(_issue("SCOPE_EXPANSION", Impact.MEDIUM, {
            "universals": s.universals,
            "heuristic": "universal_without_scope_restriction",
        }))
    if s.presuppositions:
        issues.append(_issue("PRESUPPOSITION_CANDIDATE", Impact.MEDIUM, {
            "phrases": s.presuppositions,
        }))
    if s.reformulation_drift:
        issues.append(_issue("REFORMULATION_DRIFT", Impact.MEDIUM, {
            "connectives": [c["form"] for c in s.connectives
                            if c.get("relation") == "REFORMULATION"],
        }))
    if s.qualifier_loss:
        issues.append(_issue("QUALIFIER_LOSS", Impact.LOW, {
            "force": s.force,
            "heuristic": "strong_claim_without_hedge",
        }))

    # lexical causal assertion ("приводит к", "обусловлено" in lexicon)
    # suppressed for presuppositional claims (covered by PRESUPPOSITION_CANDIDATE)
    if s.causal and s.force_rank >= _RANK("CAUSAL_ASSERTED") and not s.presuppositions:
        issues.append(_issue("CAUSALITY_HIGH_FORCE", Impact.HIGH, {
            "force": s.force,
            "heuristic": "lexical_causal_assertion",
        }))

    # discourse connectives requiring argument support (registry flag)
    for c in s.connectives:
        if c.get("requires_argument_support"):
            issues.append(_issue(
                "DISCOURSE_CONNECTIVE_UNJUSTIFIED",
                Impact.HIGH if c.get("relation") == "INFERENCE" else Impact.MEDIUM,
                {"connective": c},
            ))

    return LinguisticDigest(
        id=f"digest-{uuid.uuid4().hex[:8]}",
        main_statement=_main_statement(s),
        scope=build_scope_field(s),
        modality=_modality_for_force(s.force),
        causal_force="CAUSAL" if s.causal else "NONE",
        ambiguities=issues,
        discourse_role=_guess_discourse_role(s),
        affordances=_affordances_for_issues(issues),
    )


def _RANK(name: str) -> int:
    from t0_ru import _FORCE_RANK
    return _FORCE_RANK.get(name, 0)


def _modality_for_force(force: str) -> str:
    mapping = {
        "OBSERVED": "assertive",
        "CONSISTENT_WITH": "assertive_compat",
        "POSSIBLE_INTERPRETATION": "possibility",
        "WEAK_INFERENCE": "weak_inference",
        "ESTABLISHED_WITHIN_SCOPE": "assertive",
        "CAUSAL_ASSERTED": "causal_assertive",
        "BOOSTED": "boosted",
    }
    return mapping.get(force, "assertive")


def _guess_discourse_role(s: T0Sentence) -> str | None:
    if s.connectives:
        rels = [c["relation"] for c in s.connectives]
        if "REFORMULATION" in rels:
            return "reformulation"
        if "INFERENCE" in rels or "SUMMARY_OR_INFERENCE" in rels:
            return "inference"
        if "CONTRAST" in rels or "CONCESSION_OR_CONTRAST" in rels:
            return "contrast"
        return "connective"
    return None


def _affordances_for_issues(issues: list[LinguisticIssue]) -> list[str]:
    """Map digest issues to allowed actions (registry-aligned action vocabulary)."""
    acts = {"inspect_contract", "rewrite_span"}
    for i in issues:
        if i.type in {"MODALITY_UPGRADE", "CAUSALITY_UPGRADE", "CAUSALITY_HIGH_FORCE"}:
            acts.update({"weaken_modality", "remove_causality", "request_research"})
        if "SCOPE" in i.type or i.type == "REFORMULATION_DRIFT":
            acts.update({"restore_scope", "rewrite_span"})
        if i.type == "PRESUPPOSITION_CANDIDATE":
            acts.update({"request_context", "inspect_contract"})
        if i.type == "QUALIFIER_LOSS":
            acts.add("weaken_modality")
        if i.impact in {Impact.HIGH, Impact.CRITICAL}:
            acts.add("request_expert")
    return sorted(acts)


def affordance_set_for(sentence: str) -> AffordanceSet:
    """Adaptive control hook: build AffordanceSet from digest issues."""
    d = build_digest(sentence)
    return AffordanceSet(
        target="sentence",
        affordances=d.affordances,
        unavailable_actions=["silent_claim_mutation", "silent_evidence_creation"],
        signals=[{"issue": i.type, "impact": i.impact.value} for i in d.ambiguities],
    )
