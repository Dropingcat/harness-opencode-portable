# WRITER REFERENCE / TRACE / LIBRARY IMPLEMENTATION REVIEW

Status: ACCEPT for Writer-side boundary. Researcher internals remain intentionally deferred.

## 1. Purpose

This iteration closes the missing Writer-side seams between:

`writing object -> style/evidence reference preparation -> fragment selection -> draft request -> DOM binding -> evidence locator -> validation routing -> change provenance -> source-update invalidation`.

It does not attempt to finish the full Researcher runner. Writer emits typed research debt and dispatch contracts; Researcher remains the authority that may execute discovery and evidence validation.

## 2. New contracts

### ReferenceBundle profile graph digest

`reference_bundle/1.0.profile.graph_digest` can now consume canonical Writer `graphs` artifacts. It stores graph families, node/edge counts, node-type and relation distributions and top motifs. This makes a reference profile describe both surface style and the extracted reasoning structure.

### ReferenceFragment/1.0

A fragment is a concrete section/paragraph-level reference object with:

- reference/source identity;
- source SHA-256;
- original locator and segment offsets;
- normalized text hash;
- document kind/language/section role;
- style features;
- graph digest;
- role permissions (`style` versus `evidence`).

### ReferenceSelection/1.0

Selection is two-stage:

1. hard filters: permission role, document kind, language, section role;
2. ranking: style-feature similarity + graph similarity for style, lexical overlap + locator quality for evidence.

The result says what may be taken from each fragment. Style fragments allow paragraph shape, citation/hedging/causal densities, graph motifs and argument structure, but not factual claims. Evidence fragments allow claim support, excerpt, locator and source hash.

A failed hard-filter search is typed as `DEGRADED / NO_REFERENCE_AFTER_HARD_FILTERS`; it is not silently converted to an unrelated reference.

### EvidenceSpan/1.1

Two modes are supported:

- `text_span`: PDF/DOCX/MD/DJVU/ODT/text-like sources with source hash, locator, local offsets, excerpt and normalized text hash;
- `artifact_locator`: non-text evidence such as spreadsheet cells, table rows or image frames, still bound to source SHA-256 and extractor version.

Evidence coordinates live in the source extractor's locator space, not in an invented global byte offset over binary formats.

### SourceCatalog/1.1

The local catalog stores stable source IDs, current SHA-256, path, media type, title/bibliographic fields, language/document kind, extractor version and metadata. `source_versions` retains every observed content hash for a source ID.

### SearchMemory/1.0

Search memory stores normalized query/hash, purpose, claim ID, route stage, search hits, locators, rank, disposition and reason. It remembers retrieval work, not an LLM prose summary.

### LibrarySearch/1.0 and LibraryIngest/1.1

`library.ingest` recursively indexes supported local documents into FTS and SourceCatalog. `library.search` executes lexical retrieval, enriches hits from SourceCatalog and writes the search run to SearchMemory.

Graph extraction is deliberately lazy: the entire electronic library is not graph-processed on every ingest. Graph profiles are generated when a document becomes an actual reference candidate.

### DraftRequest/1.0

DraftRequest binds:

- chosen writing object;
- section role;
- selected style fragments;
- selected evidence fragments;
- authorized claims;
- instructions and restrictions.

The contract explicitly states that style references are not evidence and that Writer cannot search the web or introduce unsupported factual claims without research debt.

### ResearchDispatchContract/1.0

ValidationPlan now resolves to a concrete Researcher stage. A claim with an exact locator enters `evidence-validation`; a source without locator enters `document-analysis`; a bibliographic candidate enters `source-resolution`; an unknown source starts at local corpus and escalates to discovery only through Researcher routing.

The dispatch result exposes logical tools and capabilities, not provider/backend names.

### WriterDependencyGraph/1.1 and SourceUpdate/1.0

The dependency graph maps:

`Source -> SUPPORTS -> Claim -> REALIZED_IN -> Paragraph`

and understands the real nested Writer DOM (`structure.chapters[].sections[].paragraphs[]`) plus both `id` and `*_id` forms.

When SourceCatalog sees a hash change, `source-update` emits a deterministic invalidation plan. It does not silently mutate claims or prose.

### Writer provenance event bridge

A `writer_change_ledger/1.0` can now be registered in the shared Job state. Two events are appended: `ARTIFACT_REGISTERED` and `WRITER_CHANGE_LEDGER`, preserving before/after DOM hashes and touched claims/sources.

## 3. Document-format coverage

Current inspection/index path:

- PDF: text layer by PyMuPDF, page locators;
- DOCX: paragraph/table locators;
- MD/TXT/JSON/YAML/etc.: line-range segments;
- ODT: paragraph locators;
- DJVU: `djvutxt` when present; current environment reports degraded capability because `djvutxt` is not installed;
- XLSX: sheet/cell locator support for artifact evidence;
- CSV/table and TIFF frame locators remain usable as artifact-locator evidence.

OCR remains a separate capability and should be invoked by routing for pages with no text layer rather than hidden inside the normal extractor.

## 4. Real six-document benchmark

Inputs:

- Dissertation_Carsten_Spira.pdf
- demchenko2011.pdf
- s.meka_Ph.D_thesis.pdf
- Dissertation by Rakhadilov
- Diss_148.pdf (Schacherl)
- 12хн -азотирование.pdf

For graph profiling a bounded real-text sample from each source was passed through canonical `writer extract -> writer graphs`.

Observed graph digests were non-trivial. All samples produced G3/G4/G6/G13/G14/G15 families. The two Russian dissertation samples also produced G5 epistemic projection in the chosen samples. High-volume G13 `HEAD_OF` edges dominate raw counts, so ranking uses graph-family/node/relation signatures rather than raw edge count alone.

Role swapping with hard filters produced:

- Spira target -> Schacherl + Meka style fragments;
- Meka target -> Spira + Schacherl;
- Schacherl target -> Meka + Spira;
- Rakhadilov target -> Esipov;
- Esipov target -> Rakhadilov;
- Demchenko article target -> no peer article in the remaining five sources, therefore `DEGRADED / NO_REFERENCE_AFTER_HARD_FILTERS` rather than using a dissertation as an accidental style substitute.

This is the desired fail-closed behavior.

## 5. Electronic-library benchmark

The six PDFs were indexed through `library.ingest`:

- 6 sources cataloged;
- 655 page segments written to local FTS;
- per-source SHA-256 and version state recorded;
- no external backend required.

Query `nitriding deformation nitrogen diffusion phase formation` retrieved Demchenko page-level hits and recorded them in SearchMemory. A repeated normalized query can therefore reuse the prior search trace and previous source/locator choices without relying on model memory.

## 6. End-to-end scenario

### Object and references

Target: a dissertation results section.

Style reference selection used English-language dissertation fragments and selected Spira/Schacherl under the hard filters. Evidence selection over Demchenko selected page-level fragments relevant to deformation/nitride formation.

An exact EvidenceSpan was recovered on Demchenko PDF page 1 for the statement describing deformation intervals 3-8 % and 20-30 % and accelerated epsilon/gamma-prime nitride formation.

### DraftRequest

DraftRequest contained one authorized factual claim, separate style/evidence references and explicit restrictions.

### First writer output

The first synthetic writer-agent output intentionally added a stronger introductory claim before the sourced sentence. Draft loop returned:

- total claims: 2;
- traced to DOM: 1;
- needs source: 1;
- complete: false.

This demonstrates that reference style does not authorize new factual content.

### Revised writer output

After removing the unsupported extra claim:

- total claims: 1;
- traced to DOM: 1;
- needs source: 0;
- complete: true.

The claim was bound by explicit claim/source markers.

### Validation routing

The claim with a known source locator produced:

`ValidationPlan.entry_stage = evidence-validation`

and then a real `ResearchDispatchContract` for:

`route_id = academic-research`
`stage = evidence-validation`
`bundle_state = READY`.

Writer sees logical tools/capabilities; `backend_names_exposed_to_writer = false` and `writer_may_execute_web_discovery = false`.

### Source update and invalidation

A synthetic source-version hash change was applied in an isolated catalog DB. The source PDF itself was not modified.

The resulting invalidation path was:

`DEMCHENKO -> C-001 -> PAR-1`

with:

- `claims_to_revalidate = [C-001]`;
- `paragraphs_to_repair = [PAR-1]`;
- `requires_revalidation = true`.

This closes the Writer-side provenance feedback loop.

## 7. Routing map after this iteration

### Writer

`object-select`
-> `reference-prepare`
-> `claim-load`
-> `draft`
-> `semantic-validation`
-> optional `repair`
-> `provenance-update`

Writer may use local library search, reference fragments/selectors, evidence locators, DraftRequest and deterministic provenance tools. `web.discovery` remains forbidden in Writer stages.

### Researcher handoff

`ValidationPlan`
-> local corpus if source missing
-> `ResearchDispatchContract`
-> one of `discovery / source-resolution / document-analysis / evidence-validation`

External providers remain hidden behind logical capabilities.

## 8. Known weak points

These are not hidden by the green tests.

1. Graph digest is currently document/sample-level when attached to ReferenceFragments. True per-fragment graph fingerprints require stable graph-node -> source-locator mapping from extraction.
2. English and German are still grouped as `en_or_de`; real language ID should be a separate lightweight capability.
3. PDF structural extraction is text-layer based. Pages without text are reported and should route to OCR. Complex layouts need the planned Docling/GROBID-style structured backends when available.
4. `library.ingest` source IDs are stable to the library-relative path, not bibliographic identity. Rename/move reconciliation should later use DOI/title/authors/source fingerprinting in Researcher/source-resolution.
5. SearchMemory currently recalls exact normalized query hashes. Semantic search-memory retrieval is intentionally deferred until lexical behavior is stable.
6. Local FTS query syntax is still direct FTS5. Query decomposition, synonym expansion and bilingual retrieval belong in the later Researcher/search planner, not Writer.
7. Textual entailment and literature/public-source validation remain the major unfinished Researcher capability. This iteration only creates the typed dispatch boundary.
8. SourceUpdate emits invalidation but does not automatically rewrite claim verification state. A later state-reducer policy should decide the transition (for example SUPPORTED -> STALE/PENDING_REVALIDATION).

## 9. Gates

- full unittest discovery: 94/94 PASS;
- Writer/capsule compileall: PASS;
- base runtime compiler check: PASS;
- capability runtime compiler check: PASS;
- git diff --check: PASS.

Capability policy hash after this work:
`b3770133572c9246efded19f08d5b4f6f92101116bbe8125eb9c6e82141cd2ef`

Base runtime policy hash remains:
`6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`

## 10. Recommended next boundary

Do not rebuild the full Researcher yet.

The next Writer-focused boundary should be `WRITER-COMPOSE-001`:

1. make graph fingerprints per ReferenceFragment, not only per source sample;
2. add a `WritingPolicy`/genre profile between WritingObjectDecision and DraftRequest;
3. convert selected style fragments into a bounded `StyleInstructionArtifact` that cannot carry factual claims;
4. connect DraftRequest to the specialized writer-agent invocation and capture DraftArtifact/attempt provenance;
5. add DOM patch/merge rather than whole-file draft application;
6. add a state transition for invalidated claims and selective paragraph repair;
7. rerun the six-source role-swapping benchmark and one Russian dissertation-section composition scenario.

After that boundary Writer will be at a reasonable stopping point and the deterministic Researcher runner can be rebuilt against stable contracts instead of a moving target.
