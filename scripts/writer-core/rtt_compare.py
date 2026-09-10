"""Deterministic RTT comparator over runtime-owned reason codes (v0.3).

Compares T0 digests of source vs candidate; emits RTTReason codes.
Validated against tests/linguistics/golden_traps.yaml (see golden_test.py).
"""
from __future__ import annotations

import re

from writer_core.rtt import RTTReason, RTTResult

from t0_ru import T0Sentence, analyze_sentence  # noqa: E402


def _has_connective_flag(s: T0Sentence, flag: str) -> bool:
    """True if any connective detected in s carries the given registry flag."""
    return any(c.get(flag) for c in s.connectives)


def compare(source: str, candidate: str) -> RTTResult:
    s = analyze_sentence(source)
    c = analyze_sentence(candidate)
    reasons: list[RTTReason] = []
    notes: list[str] = []

    # 1) Modality upgrade / downgrade
    if c.force_rank > s.force_rank:
        reasons.append(RTTReason.MODALITY_UPGRADE)
        notes.append(f"modality {s.force}({s.force_rank}) -> {c.force}({c.force_rank})")
    elif c.force_rank < s.force_rank:
        reasons.append(RTTReason.MODALITY_DOWNGRADE)

    # 2) Causality upgrade / loss
    if c.causal and not s.causal:
        reasons.append(RTTReason.CAUSALITY_UPGRADE)
        notes.append("causality introduced")
    elif s.causal and not c.causal:
        reasons.append(RTTReason.CAUSALITY_LOSS)

    # 3) Scope expansion / narrowing
    if not s.scope_restricted and c.universals and not c.scope_restricted:
        reasons.append(RTTReason.SCOPE_EXPANSION)
        notes.append(f"universal quantifiers: {c.universals}")
    if s.scope_restricted and not c.scope_restricted:
        reasons.append(RTTReason.SCOPE_EXPANSION)
        notes.append("scope restrictor dropped")
    if not s.scope_restricted and c.scope_restricted:
        reasons.append(RTTReason.SCOPE_NARROWING)

    # 4) Qualifier loss
    if s.qualifiers and not c.qualifiers:
        reasons.append(RTTReason.QUALIFIER_LOSS)
        notes.append(f"qualifiers lost: {s.qualifiers}")

    # 5) Negation flip
    if s.negation != c.negation:
        reasons.append(RTTReason.NEGATION_FLIP)

    # 6) Numeric / unit drift (exact set of numbers must be preserved)
    s_nums = _norm_numbers(s.numbers)
    c_nums = _norm_numbers(c.numbers)
    if s_nums and s_nums != c_nums:
        reasons.append(RTTReason.NUMERIC_DRIFT)
        notes.append(f"numbers {s_nums} -> {c_nums}")
    if s_nums and c_nums and _units(s_nums) != _units(c_nums):
        reasons.append(RTTReason.UNIT_DRIFT)

    # 7) Unauthorized claim: candidate has causal/boosted force where source had none
    if c.force in {"CAUSAL_ASSERTED", "BOOSTED"} and s.force in {"OBSERVED", "CONSISTENT_WITH"}:
        reasons.append(RTTReason.UNAUTHORIZED_CLAIM)

    # 8) Claim omission: source had strong force, candidate lost it entirely
    if s.force_rank >= 5 and c.force == "OBSERVED" and not c.causal:
        reasons.append(RTTReason.CLAIM_OMISSION)

    # 9) Unjustified discourse connective: candidate bridges a NEW causal claim
    #    with an argument-support connective ("следовательно", "поэтому", ...)
    #    that the source premise did not license.
    if not s.causal and c.causal and _has_connective_flag(c, "requires_argument_support"):
        reasons.append(RTTReason.DISCOURSE_CONNECTIVE_UNJUSTIFIED)
        notes.append("causal claim introduced under argument-support connective")

    # 10) Reformulation drift: candidate re-states the claim under a
    #     semantic-equivalence connective ("иными словами", ...) but the
    #     re-statement drifts (universalized, force boosted, scope un-restricted).
    if _has_connective_flag(c, "requires_semantic_equivalence") and (
        (c.universals and not s.universals)
        or c.force_rank > s.force_rank
        or (s.scope_restricted and not c.scope_restricted)
    ):
        reasons.append(RTTReason.REFORMULATION_DRIFT)
        notes.append("reformulation marker used but semantics drifted")

    if not reasons:
        reasons.append(RTTReason.EXACT if source.strip() == candidate.strip()
                       else RTTReason.PARAPHRASE_SAFE)
    verdict = "PASS" if reasons in ([RTTReason.EXACT], [RTTReason.PARAPHRASE_SAFE]) else "FAIL"
    return RTTResult(
        contract_id="rtt-sentence",
        realization_id="candidate",
        level="sentence",
        verdict=verdict,
        reason_codes=reasons,
        notes=notes,
    )


def compare_contract(contract_claim: dict, candidate: str) -> RTTResult:
    """Compare one handoff-style claim contract with its realization.

    Explicit contract fields take authority over incidental textual signals. This
    keeps the four v0.3 compatibility fixtures executable without making the
    broader handoff semantic compiler a runtime dependency.
    """
    proposition = str(contract_claim.get("proposition") or "")
    claim_id = str(contract_claim.get("id") or contract_claim.get("claim_id") or "claim")
    baseline = compare(proposition, candidate)
    reasons: list[RTTReason] = []
    notes: list[str] = []

    scope = contract_claim.get("scope")
    if isinstance(scope, dict):
        missing_scope = [str(value) for value in scope.values()
                         if value is not None and str(value).casefold() not in candidate.casefold()]
        if missing_scope:
            reasons.append(RTTReason.SCOPE_SHIFT_MAJOR)
            notes.append(f"contract scope values omitted: {missing_scope}")

    numeric_refs = contract_claim.get("numeric_refs") or []
    expected_numbers = [str(ref.get("value")) for ref in numeric_refs
                        if isinstance(ref, dict) and ref.get("value") is not None]
    normalized_candidate = candidate.replace(",", ".")
    if expected_numbers and any(
            re.search(rf"(?<!\d){re.escape(value.replace(',', '.'))}(?!\d)", normalized_candidate) is None
            for value in expected_numbers):
        reasons.append(RTTReason.NUMERIC_DRIFT)
        notes.append(f"contract numeric values omitted or changed: {expected_numbers}")

    required_qualifiers = [str(q) for q in contract_claim.get("required_qualifiers") or []]
    candidate_words = set(re.findall(r"[a-zа-яё0-9]+", candidate.casefold()))
    dropped = []
    for qualifier in required_qualifiers:
        qualifier_words = set(re.findall(r"[a-zа-яё0-9]+", qualifier.casefold())) - {
            "в", "во", "для", "на", "при",
        }
        if not qualifier_words or not qualifier_words <= candidate_words:
            dropped.append(qualifier)
    if dropped:
        reasons.append(RTTReason.QUALIFIER_DROPPED)
        notes.append(f"required qualifiers dropped: {dropped}")

    if RTTReason.CAUSALITY_UPGRADE in baseline.reason_codes:
        reasons.insert(0, RTTReason.CAUSALITY_UPGRADE)
    if not reasons:
        reasons.append(RTTReason.EXACT if proposition.strip() == candidate.strip()
                       else RTTReason.PARAPHRASE_SAFE)

    safe = reasons in ([RTTReason.EXACT], [RTTReason.PARAPHRASE_SAFE])
    return RTTResult(
        contract_id=claim_id,
        realization_id="candidate",
        level="sentence",
        verdict="PASS" if safe else "FAIL",
        reason_codes=reasons,
        notes=notes,
    )


def _norm_numbers(nums: list[str]) -> list[str]:
    return [n.strip().lower() for n in nums]


def _units(nums: list[str]) -> set[str]:
    return {n.split()[-1] if n.split() else "" for n in nums if n.split()}
