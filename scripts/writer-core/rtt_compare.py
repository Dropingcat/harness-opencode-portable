"""Deterministic RTT comparator over skeleton reason codes (v0.3).

Compares T0 digests of source vs candidate; emits RTTReason codes.
Validated against tests/linguistics/golden_traps.yaml (see golden_test.py).
"""
from __future__ import annotations

import sys

sys.path.insert(0, r"E:\Documents\Документы\writer-core\writer_core_handoff\src_skeleton")

from writer_core_ir.rtt import RTTReason, RTTResult  # noqa: E402

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

    verdict = "PASS" if not reasons else "FAIL"
    return RTTResult(
        contract_id="rtt-sentence",
        realization_id="candidate",
        level="sentence",
        verdict=verdict,
        reason_codes=reasons,
        notes=notes,
    )


def _norm_numbers(nums: list[str]) -> list[str]:
    return [n.strip().lower() for n in nums]


def _units(nums: list[str]) -> set[str]:
    return {n.split()[-1] if n.split() else "" for n in nums if n.split()}