# Weak-LLM Linguistic Toolkit

## Design target
The small model sees compact tasks with bounded outputs.

## Core tools
`SELECT_FRAME`, `CLASSIFY_CLAUSE_ROLE`, `CHOOSE_CONNECTIVE`, `RESOLVE_REFERENCE`, `REQUEST_CONTEXT`, `SPLIT_CLAUSE`, `MERGE_CLAUSES`, `MOVE_QUALIFIER`, `RESTORE_SCOPE`, `WEAKEN_MODALITY`, `REMOVE_CAUSALITY`, `BIND_TERM`, `BIND_QUANTITY`, `RERANK_LEXICAL_CHOICES`, `PROPOSE_THEME_RHEME`, `REQUEST_EXPERT`.

## Tool contract
Each action declares:
- accepted IR node types;
- fields it may alter;
- fields it MUST preserve;
- post-validators;
- escalation conditions.

## Digest rule
Small model never receives raw graph dumps by default. EnvironmentBuilder compiles a `LinguisticDigest` containing the main predicate, arguments, scope, modality, references, discourse role, ambiguity summary and legal actions.

## Locality
Prefer sentence/clause windows. Cross-section context is retrieved only when required by reference, terminology or argument dependencies.
