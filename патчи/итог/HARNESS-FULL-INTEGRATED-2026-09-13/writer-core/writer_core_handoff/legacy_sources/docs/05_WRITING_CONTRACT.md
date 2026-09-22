# 05. Writing Contract — Researcher → Writer Boundary v0.2

`allowed/qualified/forbidden` is only one axis. Writer needs the complete transformation envelope for every claim and every writing slot.

## ClaimWritingContract

```yaml
claim_id:
proposition:
claim_type:
scope_ref:
verifiability:
evidence_state:
evidence_refs: []
writer_eligibility:
modality:
causal_level:
uncertainty_refs: []
required_qualifiers: []
forbidden_transformations: []
contradiction_refs: []
gap_refs: []
numeric_refs: []
citation_policy:
review_requirement:
criticality:
visibility:
```

## WritingSlotContract

```yaml
slot_id:
section_contract_ref:
discourse_role:
argument_role:
required_claims: []
optional_claims: []
forbidden_claims: []
required_artifacts: []
required_relations: []
semantic_type_requirements: []
word_budget:
style_profile_ref:
policy_snapshot_ref:
completion_criteria: []
```

## Allowed semantic delta

Default realization may paraphrase, locally reorder, add non-factual discourse glue, expand authoritative abbreviations and render bound object refs.

It may not create factual claims, strengthen causality/modality/certainty, alter scope, drop mandatory qualifiers/uncertainty, invent precision/identity, or collapse conflicting evidence into consensus.

Any necessary new interpretation becomes `WriterClaimCandidate(PROPOSED)` and is quarantined until Researcher/human admission.

## Lossless boundary invariant

The bridge must preserve all dimensions required for later RTT: proposition, scope, evidence state, eligibility, modality, causal level, qualifiers, uncertainty, object refs, conflicts/gaps and review requirements. If a Researcher dimension cannot be represented, the contract build fails closed rather than silently dropping it.
