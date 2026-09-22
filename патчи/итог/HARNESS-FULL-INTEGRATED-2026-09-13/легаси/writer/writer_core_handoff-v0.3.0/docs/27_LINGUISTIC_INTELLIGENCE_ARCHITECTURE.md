# Linguistic Intelligence Layer

## Mission
Turn linguistic competence into a layered environment that weak models can consume. The system MUST NOT ask a small model to rediscover Russian grammar, textual cohesion and academic rhetoric from raw prose every turn.

## Components
1. `LinguisticParser` — deterministic/statistical NLP proposals.
2. `LinguisticIRBuilder` — canonical actionable representation.
3. `LinguisticExpert` — Tier-2 semantic arbiter for difficult ambiguity.
4. `LinguisticAuditor` — post-hoc corpus/session learning from accepted and rejected realizations.
5. `SurfaceRealizer` — semantic plan -> lexical/syntactic plan -> text.
6. `LinguisticRTT` — text -> linguistic IR -> semantic comparison.

## Tier model
### Tier 0 — code/NLP
Tokenization, morphology, dependency syntax, sentence/clause boundaries, numeric/unit binding, citations, formulas, lexical dictionaries, simple agreement/government checks.

### Tier 1 — weak LLM
Receives a compact `LinguisticDigest`, local context and a bounded affordance set. Suitable for clause-role classification, sentence-frame choice, local reference resolution, simple modality classification, lexical reranking and local repairs.

### Tier 2 — strong LLM
Receives a diagnostic capsule, not an unconstrained full document. Used for ambiguous coreference, nested negation, uncertain scope, implicit warrant, multi-sentence discourse relation, complex compression, RTT disagreement and high-impact rhetorical interpretation.

### Human/expert tier
Required where policy says so or Tier-2 disagreement affects a high-criticality claim.

## Semantic-impact escalation
Escalation MUST depend primarily on potential semantic impact, not parser confidence alone.

`impact = claim_criticality × ambiguity_relevance × potential_semantic_delta`.

A morphological ambiguity with no semantic effect does not deserve Tier 2. Ambiguity in negation scope of a defense position does.

## Separation of authority
Linguistic modules MAY propose realizations and interpretations. They MUST NOT:
- create evidence,
- silently strengthen epistemic status,
- alter Researcher claims,
- infer authorship as fact,
- promote learned preferences to hard rules without an explicit architecture decision.
