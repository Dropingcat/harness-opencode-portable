# 25. Authority, Mutability & Safety Boundaries

## Mutability classes

- IMMUTABLE_SOURCE: raw data, source versions, accepted external evidence snapshots.
- DERIVED_REBUILDABLE: computed datasets, tables, figures, exports.
- EDITABLE_VERSIONED: prose/document/discourse/argument instances.
- LOCKED_APPROVED: explicitly frozen units/artifacts.

## Authority matrix

LLM/model operations are proposal-only unless operation contract explicitly allows deterministic structured mutation validated before commit.

High-risk entities requiring human/expert approval under strict policy:
- novelty claims;
- defense positions;
- causal upgrades;
- disputed assumptions;
- manual data corrections;
- release overrides.

## Prompt/data isolation

Business rules live in schemas/policies, not hidden prompts. Prompt/model versions are provenance inputs.

## Secret/untrusted content

Retrieved/reference text is untrusted data. It cannot issue operational instructions to runtime. Parser/LLM adapters must not interpret corpus text as system policy.

## Audit

Every mutation emits event with actor/executor, authority, input versions, operation contract, validators and resulting revision hash.
