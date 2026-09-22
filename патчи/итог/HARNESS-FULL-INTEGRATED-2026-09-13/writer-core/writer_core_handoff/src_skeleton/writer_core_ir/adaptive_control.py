from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from .linguistics import AffordanceSet, Impact, LinguisticIssue


@dataclass(frozen=True)
class EscalationPolicy:
    """Reference skeleton only; production scoring remains policy/config driven."""
    tier2_impacts: frozenset[Impact] = frozenset({Impact.HIGH, Impact.CRITICAL})

    def requires_tier2(self, issue: LinguisticIssue) -> bool:
        return issue.impact in self.tier2_impacts


def build_semantic_mismatch_environment(
    target: str,
    issues: Iterable[LinguisticIssue],
) -> AffordanceSet:
    issues = list(issues)
    actions = {
        "inspect_contract",
        "rewrite_span",
        "request_context",
    }
    if any(i.type in {"MODALITY_UPGRADE", "CAUSALITY_UPGRADE"} for i in issues):
        actions.update({"weaken_modality", "inspect_evidence", "request_research"})
    if any(i.type in {"SCOPE_EXPANSION", "SCOPE_LOSS"} for i in issues):
        actions.add("restore_scope")
    if any(i.impact in {Impact.HIGH, Impact.CRITICAL} for i in issues):
        actions.add("request_expert")
    return AffordanceSet(
        target=target,
        affordances=sorted(actions),
        unavailable_actions=["silent_claim_mutation", "silent_evidence_creation"],
        signals=[{"issue": i.type, "impact": i.impact.value} for i in issues],
    )
