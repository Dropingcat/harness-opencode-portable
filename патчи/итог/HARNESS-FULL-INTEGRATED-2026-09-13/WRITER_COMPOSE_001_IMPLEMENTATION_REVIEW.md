# WRITER-COMPOSE-001 implementation review

## 1. Goal

Close the Writer-side composition loop without rebuilding Researcher. The target pipeline is:

`WritingObjectDecision -> Reference preparation -> WritingPolicy -> Claim/Evidence load -> DraftRequest -> writer-agent boundary -> DraftArtifact -> DOM Patch -> ChangeLedger -> validation -> source invalidation -> claim-state reducer -> selective RepairRequest -> RTT/release`.

The design deliberately keeps heavy analysis lazy. A library may contain many thousands of sources, but only a shortlist of roughly 3-5 reference candidates is graph-enriched for a concrete writing decision.

## 2. Decisions and risk trade-offs

### 2.1 Document analysis is cached, not repeated

A source version is keyed by `source_id + source_sha256`. `DocumentCard/1.0` indexes the cheap extraction result and registered derived artifacts. Full fragment graphs are separate artifacts, not embedded into the card.

Chosen over a monolithic JSON card because individual derived artifacts have independent extractor versions and invalidation lifetimes.

### 2.2 Fragment graph analysis is lazy

`ReferenceFragment` remains cheap. `reference.select.iterative` performs:

1. role/genre/language/section hard filters for STYLE;
2. cheap style shortlist;
3. graph enrichment for only the shortlisted fragments;
4. final style+graph rerank.

EVIDENCE selection intentionally does not inherit STYLE hard filters for genre/language/section. An English article may support a Russian dissertation claim.

Risk controlled: graph extraction cost cannot grow with total library size unless the caller deliberately enriches the entire corpus.

### 2.3 Source provenance is carried into graph nodes

`reference_fragment_graph/1.0` propagates `source_id`, `source_sha256`, locator, local span and normalized-text hash into every derived graph node and edge. Local graph offsets remain fragment-relative, while source provenance remains stable.

This allows the trace:

`Source -> source span -> ReferenceFragment -> graph node/motif -> StyleInstruction -> DraftRequest`.

### 2.4 Style is transformed before it reaches the writer-agent

`StyleInstructionArtifact/1.0` contains paragraph length targets, citation/hedging/causal densities, graph-relation patterns and rhetorical architecture hints. It does not forward the reference paragraph text.

Chosen to reduce lexical imitation and to prevent a STYLE reference from silently becoming claim/evidence authority.

### 2.5 DOM changes use optimistic concurrency

The writer-agent must not return or overwrite a whole document. `writer_dom_patch/1.0` emits paragraph operations with:

- base DOM hash;
- target paragraph ID;
- expected paragraph hash;
- replacement paragraph payload.

A stale base or paragraph produces a typed patch conflict rather than silent overwrite.

### 2.6 Source invalidation is split from epistemic state transition

`source-update` detects source-version changes and returns an invalidation plan. It does not directly mutate claim status.

The state reducer then applies policy:

- single/critical support -> `PENDING_REVALIDATION`;
- a supported claim with multiple evidence references -> `SUPPORTED_WITH_STALE_EVIDENCE` until revalidation.

This separation preserves replayability and prevents a file watcher from becoming an epistemic authority.

### 2.7 Byte changes are not automatically semantic changes

`SourceCatalog` now distinguishes:

- `UNCHANGED`;
- `BYTE_ONLY`: file SHA changed, normalized text hash unchanged;
- `SEMANTIC`: normalized content hash changed.

Only semantic changes trigger dependency invalidation when normalized hashes are available. If normalized hashes are missing, behavior remains conservatively fail-closed.

## 3. Implemented contracts/modules

New Writer-side contracts and modules include:

- `DocumentCard/1.0`;
- `derived_artifact_store/1.0`;
- `language_profile/1.0` (`ru/en/de/mixed/unknown`);
- `reference_fragment_graph/1.0`;
- `iterative_reference_selection/1.0`;
- `WritingPolicy/1.0`;
- `StyleInstructionArtifact/1.0`;
- extended `DraftRequest/1.0`;
- `WriterAgentDispatchContract/1.0`;
- `DraftArtifact/1.0`;
- `writer_dom_patch/1.0` and apply result;
- `writer_change_ledger/1.1` with nested DOM paragraph paths;
- `claim_state_transition/1.0`;
- `RepairRequest/1.0`;
- `writer_invalidation_event_bridge/1.0`.

The canonical Writer CLI exposes the corresponding logical entrypoints. Capability authority/provider registry and `writing-prose` route were updated. The route now has an explicit `writing-policy` stage.

## 4. Five-source benchmark

Heavy graph enrichment was intentionally limited to five supplied sources:

- Meka dissertation;
- Schacherl dissertation;
- Rakhadilov dissertation;
- Esipov dissertation;
- Demchenko article.

The cheap extraction produced fragment sets first. Graphs were then built only for shortlist/target fragments.

### Style role-swapping after strict hard filters

- Meka discussion -> Schacherl discussion: READY.
- Schacherl discussion -> Meka discussion: READY.
- Rakhadilov discussion -> Esipov discussion: READY.
- Esipov discussion -> Rakhadilov discussion: READY.
- Demchenko article results -> no same-kind style candidate in this five-source set: DEGRADED with `NO_REFERENCE_AFTER_HARD_FILTERS`.

The final case is deliberate fail-closed behavior rather than genre leakage.

### Fragment language behavior

Document-level Meka/Schacherl are predominantly English, but individual German fragments are identified as `de`. Russian dissertation fragments remain `ru`. Selection therefore works on fragment language rather than blindly inheriting the document language.

## 5. Full composition scenario

A real cross-role scenario was executed:

- target object: Russian dissertation discussion;
- STYLE references: Russian dissertation fragments selected from Esipov;
- EVIDENCE source: Demchenko article;
- exact EvidenceSpan: Demchenko PDF page 1 with source SHA and local offsets;
- one authorized claim;
- WritingPolicy and StyleInstruction generated;
- WriterAgentDispatchContract created without backend/provider names;
- controlled DraftArtifact realizes only the authorized claim;
- paragraph patch applied through optimistic concurrency;
- ChangeLedger records `PAR-1` plus touched `C-001`/source dependencies;
- a simulated semantic source-version change invalidates `C-001` and `PAR-1`;
- state reducer transitions `SUPPORTED -> PENDING_REVALIDATION`;
- RepairRequest targets only `PAR-1`.

This verifies that style selection and evidence selection can intentionally cross different source sets.

## 6. Routing

`writing-prose` now follows:

`object-select -> reference-prepare -> writing-policy -> claim-load -> draft -> semantic-validation -> repair/provenance-update`.

Writer stages keep `web.discovery` forbidden. The writer-agent dispatch contract names the logical role only; it exposes no backend/provider name.

## 7. Validation results

- Writer test suite: 104/104 PASS at final implementation run before packaging.
- Dedicated WRITER-COMPOSE tests include language split, graph provenance, document cards, policy/style firewall, unauthorized claim rejection, DOM patch conflict, source invalidation/reducer and byte-only/semantic source-version handling.
- Capability runtime compiler: PASS.
- Base runtime compiler: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.

Capability policy hash: `d9ba450d1f17ad981981cafd352bbf4580db3f8674532cabcd20891ca8b74eda`.

## 8. Remaining weaknesses

1. The external OpenCode `article-writer` agent was not invoked in this container. The dispatch and DraftArtifact contracts are executable, but the external model invocation remains a live integration gate.
2. Reference fragment graph extraction still depends on the current hybrid extractor quality. A bad fragment extraction is now traceable, but not magically corrected.
3. `SourceCatalog` source identity is still caller-provided. Renames/duplicates need later bibliographic reconciliation (`DOI/title/authors/content hash`).
4. SearchMemory remains deterministic exact-query memory. Semantic recall should be a secondary layer, not the authority store.
5. DJVU remains degraded when `djvutxt` is unavailable.
6. `SUPPORTED_WITH_STALE_EVIDENCE` uses a simple evidence-count policy in this implementation. Criticality/source independence should later come from claim policy/graph metadata rather than count alone.
7. Evidence selection uses lexical ranking before exact EvidenceSpan recovery. Researcher hardening should replace this with stronger evidence retrieval/entailment without changing the Writer contract.

## 9. Recommendation

Writer is now close to the intended stable boundary. Before major Researcher reconstruction, perform one live OpenCode writer-agent integration run using the same five-source library and a real target dissertation DOM. If DraftArtifact/DOM Patch/release behavior remains stable, freeze these Writer contracts and move the next major refactor effort into Researcher.
