# 17. Global Consistency, Terminology & Symbols

## Registries

### TermRegistry
Stores canonical term, definitions, translations, allowed/forbidden synonyms, domain and validity intervals.

### SymbolRegistry
Stores LaTeX/plain symbol, meaning, dimension/unit, first definition and allowed context.

### AbbreviationRegistry
Requires definition-before-use and collision detection.

## Global checks

- TERM_DRIFT
- DEFINITION_DRIFT
- TRANSLATION_DRIFT
- SYMBOL_REDEFINITION
- SYMBOL_USED_BEFORE_DEFINITION
- ABBREVIATION_COLLISION
- QUANTITY_VALUE_CONFLICT
- FORMULA_VERSION_CONFLICT
- CLAIM_CONTRADICTION_GLOBAL
- CONCLUSION_BODY_MISMATCH

## Semantic identity

String equality is insufficient. Resolver classifies terminology relations:
`SAME_CONCEPT`, `SYNONYM_ALLOWED`, `NARROWER`, `BROADER`, `DIFFERENT`, `AMBIGUOUS`.

Ambiguous concept mapping is a blocker when it affects core results/novelty.
