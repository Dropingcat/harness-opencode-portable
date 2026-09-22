# 08. Agent Roles & Capability Boundaries v0.2

Agents are executors over typed operations; capabilities matter more than personas.

- **A0 ArchitectureGuardian**: invariants, schemas, ADRs, gate reviews.
- **A1 DomainModelImplementer**: typed entities, registry, events, migrations.
- **A2 ResearchBridgeEngineer**: lossless Researcher projection and WritingContract.
- **A3 WritingPlanner**: decomposition DAG and slot planning; no prose.
- **A4 ArgumentDiscoursePlanner**: argument/discourse pattern instantiation; no truth mutation.
- **A5 ArtifactEngineer**: quantities/formulas/data/figures/tables/crossrefs.
- **A6 QuantEngineer**: units, uncertainty, formula/implementation integrity.
- **A7 Realizer**: structured inline realization proposal only.
- **A8 SemanticBackExtractor**: independent semantic recovery from realized text.
- **A9 RTTValidator**: alignment/diff; no rewrite.
- **A10 RepairPlanner**: minimum repair operations, bounded iterations.
- **A11 ConsistencyEngineer**: global terminology/symbol/claim consistency.
- **A12 BuildEngineer**: dependencies, freshness, blockers, incremental build.
- **A13 Reviewer**: review issues/conflicts/decision proposals.
- **A14 PolicyEngineer**: policy precedence/compliance snapshots.
- **A15 ExportEngineer**: render/parse-back/visual QA; no semantic mutation.
- **A16 CorpusEngineer**: admission/dedup/pattern candidate extraction; no truth leakage.
- **A17 ForensicsEngineer**: fingerprint/lineage/open-world analysis; analytical read-only.
- **A18 RuntimeEngineer**: queues, critical path, recovery, observability.
- **A19 TestEngineer**: golden mutations, catastrophic scenarios, certification.

## Mandatory handoff

```yaml
handoff:
  task_id:
  producer:
  operation_contract_ref:
  input_versions: []
  outputs: []
  dependency_edges_created: []
  blockers_created: []
  decisions: []
  validations: []
  unresolved: []
  next_operations: []
```

No agent may self-promote its own output past a gate requiring an independent validator/human/expert.

## v0.3 linguistic roles

### LinguisticEngineer
Owns linguistic IR contracts, parser adapters, feature extraction and Tier-0 checks. No epistemic write authority.

### SmallModelEngineer
Designs LinguisticDigest, bounded language actions and evaluation for weak models. Must compare tooling against raw-prompt baseline.

### LinguisticExpertEngineer
Owns Tier-2 diagnostic capsules and structured arbitration. Does not directly commit graph changes.

### LinguisticAuditorEngineer
Owns session/corpus language memory, promotion lifecycle, anti-poisoning and style trajectory. Learned observations remain advisory.

### OrchestrationEngineer
Owns EnvironmentBuilder, AffordanceSet and strategy-memory plumbing. Must not encode semantic answers as deterministic routes unless protecting a hard invariant.
