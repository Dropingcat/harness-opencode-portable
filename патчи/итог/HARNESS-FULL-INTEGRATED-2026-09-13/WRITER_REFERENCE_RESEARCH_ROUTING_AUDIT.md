# Writer reference/research routing audit on real nitriding literature

Status: implemented hardening + real-data benchmark, 2026-09-10.

## 1. Purpose

This audit tests the canonical Writer as a process rather than as isolated gates. Six real PDF sources supplied by the user were alternated between target-document, style-reference and evidence-source roles. The test focuses on four questions:

1. What are we writing? (`WritingObjectDecision`).
2. How are we writing it, and what is each reference allowed to contribute? (`ReferenceBundle`).
3. From what evidence are factual claims written and how is validation routed? (`ValidationPlan`).
4. What changed in the document/source tree after a revision? (`ChangeLedger`).

The architectural rule is strict: style reference is not evidence. Evidence requires source identity and a locator. Writer does not get web search; missing evidence becomes research debt routed to Researcher.

## 2. Real corpus

The six supplied PDFs are intentionally heterogeneous: five dissertations/theses and one compact paper. This is useful for testing both document-kind selection and reference-role separation.

Observed deterministic profiles from `document.inspect -> reference.prepare`:

| source | inferred kind | language bucket | median paragraph words | citation density / 1000 words |
|---|---|---:|---:|---:|
| 12хн -азотирование | dissertation | ru | 72 | 5.190 |
| Diss_148 | dissertation | en_or_de | 57 | 6.057 |
| Dissertation_Carsten_Spira | dissertation | en_or_de | 29 | 8.708 |
| demchenko2011 | article | en_or_de | 95 | 7.339 |
| s.meka_Ph.D_thesis | dissertation | en_or_de | 62 | 9.624 |
| Рахадилов Б.К. | dissertation | ru | 70 | 4.982 |

The current language detector deliberately has only `ru / en_or_de / mixed`; distinguishing English from German is a remaining refinement, not silently guessed.

A simple style-distance diagnostic (not a production selector) produced sensible nearest pairs: Esipov <-> Rakhadilov for Russian dissertation style, and Meka <-> Schacherl for the Stuttgart/Max-Planck dissertation family. Demchenko is structurally an article and should not be allowed to drive dissertation-level document structure, although it can be a useful local paragraph/rhetorical reference.

## 3. What existed before this audit

### Writer

Already present:
- canonical `scripts/writer/` subsystem and public CLI;
- deterministic/hybrid extraction and graph construction;
- draft-loop, citation trace, RTT and aggregate release gate;
- Researcher verification adapter;
- uncertainty schema/bridge;
- artifact/provenance policies at harness level;
- stage-capability router and capability preflight.

Important limitation: the old structural planner is still heavily derived from an autoreferat-oriented `SECTION_REGISTRY`. It is useful after document type is known, but it should not be the authority that decides the document type.

### Research/tool layer

Already implemented in provider/capability registry:
- `search.discovery`: SearXNG/local search gateway;
- `source.resolve`: Crossref/OpenAlex/Unpaywall resolver;
- `document.inspect`: local PDF/DOCX/XLSX inspector;
- `document.ocr`: Tesseract;
- `corpus.search`: SQLite FTS5;
- `evidence.verify`: code-factory gate + fact-checker agent;
- deterministic numeric/symbolic/formula science capsule;
- job checkpointing and capability escalation.

At benchmark time local document/OCR/corpus/science/evidence capabilities were available. Web discovery, academic metadata and OA resolving were implemented but DEGRADED because their live providers were unavailable in this environment. This is a runtime availability issue, not absence of contracts.

## 4. Defects found on real PDFs

### D1. PDF corpus was silently empty

`corpus_fts.py` indexed only text extensions. Indexing the six PDFs returned `segments_written=0`, and search returned an empty result without a hard error.

Fix: PDF is now indexed page-by-page with PyMuPDF, SHA-256 and `pdf_page:N` locators.

After fix:
- documents added: 6;
- segments written: 655;
- query `nitrid*`: 12 useful hits in the benchmark limit, with stable file hash + page locator.

Remaining: page locator is adequate for retrieval but too coarse for final evidence. Researcher should refine selected pages into exact span/paragraph locators before evidence can become `SUPPORTED` at high confidence.

### D2. No explicit separation of style reference and evidence source

Previously the same reference artifact could be passed around without a machine-enforced statement of what may be copied from it.

Fix: `reference_bundle/1.0` contains an explicit role:
- `style`: structure/rhetoric/style allowed; evidence/claims forbidden;
- `evidence`: evidence/claims allowed; style/structure not used as writing authority;
- `both`: both allowed, still requiring evidence locators.

This prevents a style exemplar from becoming evidence by accidental reuse.

### D3. “What are we writing?” was entangled with an autoreferat planner

The canonical structure module recognizes an autoreferat-oriented section registry. It is not a general genre authority.

Fix: `writing_object_decision/1.0` was added as a deterministic guard before structural planning. Explicit user/task-contract kind wins with confidence 1.0. Automatic classification is intentionally conservative and requests confirmation at low confidence.

On the real corpus after refinement:
- Meka, Schacherl, Spira, Rakhadilov classified as dissertations with high enough confidence;
- Demchenko classified as article;
- the Russian Esipov thesis is correctly classified as dissertation but remains a lower-confidence case, demonstrating why explicit task contract should outrank inference.

### D4. Claim validation did not expose a claim-specific research entry stage

The repository already had an appropriate academic research route:
`discovery -> source-resolution -> document-analysis -> evidence-validation -> synthesis`.

The missing piece was a deterministic decision about where a concrete claim should enter that route.

Fix: `validation_plan/1.0` now routes:
- numeric claim -> deterministic numeric verification;
- formula/symbolic claim -> formula/science verification;
- no source -> `corpus.search -> source.resolve -> search.discovery` research debt;
- source but no locator -> locator recovery through document/corpus inspection;
- qualitative claim with source+locator -> textual entailment through `evidence.verify` / fact-checker;
- uncertainty/qualifier -> uncertainty check.

Writer itself is explicitly forbidden from web discovery.

### D5. Provenance existed globally, but Writer lacked a simple document-tree revision diff

The harness has artifact provenance and Writer has corpus evolution utilities, but there was no narrow artifact answering: “which claim/source/paragraph changed between DOM A and DOM B?”

Fix: `writer_change_ledger/1.0` records old/new SHA-256 and added/removed/modified claims, sources and paragraphs, including changed field names and touched claim/source IDs.

This is not a replacement for the event-sourced Job/Attempt provenance system. It is the Writer-domain delta that should be registered into that system.

## 5. Routing implemented

The `writing-prose` route now resolves as:

```text
object-select
  -> reference-prepare
  -> claim-load
  -> draft
  -> semantic-validation
       -> repair -> provenance-update
       -> provenance-update
```

All six stages resolve `READY` in capability preflight in the test environment.

Key boundaries:
- `object-select`: deterministic guard, no web;
- `reference-prepare`: document/corpus access, no web;
- `claim-load`: load authorized claims/evidence/reference bundles;
- `draft`: writer agent, no web;
- `semantic-validation`: local Writer gates + `ValidationPlan`; missing evidence is returned to Researcher rather than searched by Writer;
- `provenance-update`: deterministic DOM/source delta, no web or code edit.

New logical capabilities/tools:
- `writer.object.select` / `writing.object.select`;
- `writer.reference.prepare` / `reference.prepare`;
- `evidence.validation.plan` / `validation.plan`;
- `writer.provenance.diff` / `provenance.diff`.

All are provider-bound and included in the compiled capability snapshot.

## 6. Researcher apparatus: what is actually usable

### Strong/current

1. **Local document inspection**: works on the supplied PDFs and preserves page boundaries + file hash.
2. **Local exact corpus retrieval**: now works for PDFs; FTS5 is suitable as the first lexical/number/term retrieval layer.
3. **Numeric/formula verification**: deterministic researcher core + science capsule is the strongest validation path currently present.
4. **Fact-checker contract**: the agent prompt correctly separates semantic evidence judgment from deterministic numerical arbitration.
5. **Academic route contracts**: discovery, source resolution, document analysis and evidence validation already exist in the capability router.

### Present but currently degraded by environment

1. SearXNG discovery.
2. OpenAlex/arXiv academic metadata.
3. Crossref/Unpaywall canonical source/OA resolution.

The provider implementations exist; preflight reports no live provider in this sandbox. Production should treat this as `DEGRADED_CAPABILITY`, never silently fall back to model memory.

### Stale/inconsistent

1. `agents/source-fetcher.md` still describes Browser-MCP tools (`browser_search`, `browser_fetch`, etc.) that are not present in the current MCP registry/runtime bindings. The current authority exposes SearXNG + academic search + logical gateway instead.
2. `agents/research-orchestrator.md` documents a ten-brick deterministic runner, but the actual `scripts/research/run_research.sh` is Linux/server-specific, hardcodes `/home/orangepi/...`, and references a `scripts/verification` tree that is absent from this repository snapshot.
3. Only `numeric_comparator.py`, `judge_brief.py`, `synthesizer.py`, units/formulas/uncertainty and the shell runner are locally present from that described deterministic stack. `post_processor.py`, `evidence_contract.py`, `justification_check.py`, `escalation.py`, `merge_numeric.py`, `cascade.py` are not found under the expected local tree.

This is currently the largest weakness of the Researcher chain. The prompts describe a stronger apparatus than the repository can execute.

## 7. What should be added next

### R1. `reference.prepare` should gain section-level fingerprints

Current bundle is document-level. Production selection needs a `ReferenceFragment` layer:
- source hash;
- page/span locator;
- section type;
- discourse role;
- argument role;
- paragraph-length/citation/hedging features;
- allowed use (`structure`, `rhetoric`, `style`, `evidence`).

Then “take the style of Meka” becomes a controlled request such as “use Results/Discussion paragraph transition patterns; do not copy factual content”.

### R2. Add deterministic `reference.select`

Do not make it a single opaque similarity score. Selection should first filter hard constraints:
1. role permission;
2. document kind;
3. language;
4. requested section/discourse role;
5. provenance/locator availability.

Only then rank soft traits. LLM may choose among the top-N and explain which features it wants, but code must reject illegal role use.

### R3. Build a real Researcher re-entry executor

`ValidationPlan` should become executable routing:
- ready evidence -> `academic-research/evidence-validation`;
- source without locator -> `document-analysis`;
- DOI/title candidate -> `source-resolution`;
- no source -> local corpus first, then discovery.

The router already supports explicit `--stage`; therefore this does not require a new universal researcher agent.

### R4. Reconcile or replace the stale research runner

Do not patch the current shell runner incrementally while preserving hardcoded server paths. Rebuild it against current logical tools/providers and Job/Attempt state:

```text
ClaimValidationJob
 -> ValidationPlan
 -> corpus.search
 -> optional source.resolve/search.discovery
 -> document.inspect + exact EvidenceSpan
 -> deterministic numeric/formula checks
 -> semantic fact-checker evidence
 -> deterministic verdict normalizer
 -> uncertainty/justification gate
 -> Writer ResearchBundle
```

Missing deterministic pieces from the promised BRICKS runner must either be restored with tests or removed from agent claims.

### R5. Evidence spans need exact locators

`pdf_page:N` is retrieval-grade, not publication-grade. Add paragraph/span anchors (page + text hash + char/token range or stable normalized excerpt hash). This is required for robust citation trace and later revalidation when source extraction changes.

### R6. Knowledge library needs a catalog above FTS

FTS5 should remain the exact first layer. Add a source catalog containing:
- stable source_id;
- file hash/version;
- bibliographic metadata;
- DOI/URL when available;
- source class/trust policy;
- language;
- extraction version;
- indexed locators;
- supersedes/duplicate relation.

Do not start with embeddings. Add embeddings only as optional recall after exact lexical/numeric retrieval.

### R7. ChangeLedger should be registered as provenance evidence

Every applied draft revision should create:
`DraftArtifact -> ChangeLedger -> updated DOM hash -> release gate evidence`.
This closes the user-visible question “where did this claim come from and what changed after revision?”.

## 8. Tests and verification

New focused tests: 9 assertions/groups across PDF corpus, reference-role separation, validation routing, change ledger and stage routing.

Full repository Python suite after changes:
- 94 tests: PASS;
- capability runtime compiler: PASS;
- base runtime compiler: PASS;
- `compileall`: PASS;
- `git diff --check`: PASS.

Real PDF benchmark:
- 6 PDFs indexed;
- 655 page segments;
- FTS search returns stable SHA-256 + page locators;
- all six produce reference bundles;
- role separation is machine-visible.

## 9. Recommended next implementation boundary

The next boundary should not be “more agents”. It should be `REFERENCE-TRACE-001`:

1. `ReferenceFragment/1.0`.
2. deterministic `reference.select` with hard role filters.
3. exact EvidenceSpan locator contract.
4. source catalog for the local knowledge library.
5. executable ValidationPlan -> researcher stage re-entry.
6. register ChangeLedger into Job/Artifact provenance.
7. replay the six-PDF alternating-role benchmark and one complete chapter-writing scenario.

Only after this boundary is green should the research runner be rebuilt. Otherwise a stronger runner will merely automate ambiguous reference/evidence contracts faster.
