# Writer E2E real-data review

Date: 2026-09-10
Branch point: after WRITER-UNIFY-001 Phase 6C (`c8095b5`).
Run: `.runs/e2e_real_001/`.

## 1. Purpose

Exercise the canonical Writer as a connected system rather than as isolated unit tests. The probe covers:

`writing object -> plan -> reference ingestion -> reference selection -> agent draft ingestion -> DOM update -> Researcher verification -> traceability -> semantic round-trip -> release decision`.

No claim is made that the local deterministic runtime itself generates prose. Draft prose is an input from a specialized writer agent; the Writer runtime plans, binds, validates, persists and releases it.

## 2. Real inputs

Repository-native documents were used as the reference corpus:

- `shared/writer-traceability-contract.md`;
- `WRITER_UNIFICATION_PHASE6_REVIEW.md`;
- `WRITER_CORE_HANDOFF_RECONCILIATION.md`.

The full release control uses the existing scientific fixture already retained by the repository:
`experiments/writer_extractor_phase3/fixtures_baseline_7case.json` (`900 МПа`).

## 3. Writing-object selection and planning

### Topic path

`writer plan --topic` produced:

- 11 sections;
- 14 required slots;
- 14 explicit WORK_BLOCKING gaps;
- no runtime errors.

This is useful fail-open planning: the runtime does not invent research content and creates research requests for missing slots.

### Existing-document path

`writer plan --doc WRITER_UNIFICATION_PHASE6C_REVIEW.md` parsed the document but recognized one `UNKNOWN` section and zero slots. Therefore object/section inference is currently tuned to the academic registry and is weak for engineering/review Markdown.

Verdict: **PARTIAL**. Topic-driven object creation works; arbitrary real-document genre detection requires a registry/genre-selection layer.

## 4. Reference ingestion and selection

`writer extract` processed the three real Markdown references without parser errors (25, 19 and 28 paragraphs respectively). `writer graphs` also produced nested graph artifacts.

Two integration defects were found:

1. extracted real Markdown paragraphs can contain useful digest/linguistic data while `claims=[]`; a zero claim count is not currently surfaced as degraded extraction;
2. `draft-loop --ref` historically expected a shallow edge artifact, while public `writer graphs` emits a nested document/paragraph graph shape.

The nested graph shape is now accepted. However a larger contract mismatch remains: the draft-loop similarity graph and the public analysis graph use different graph families. Consequently three real public graph artifacts are loaded (`refs_available=3`) but yield no suggestion.

A control using two reference bundles prepared in the same canonical graph family as `draft-loop` works:

- hardness reference: similarity `1.0`;
- nitriding-kinetics reference: similarity `0.5`.

Verdict: **ALGORITHM WORKS, PUBLIC PIPELINE NOT YET WIRED END-TO-END**.

Required next component: a deterministic `reference.prepare` adapter producing one versioned `ReferenceBundle` contract consumed by `draft-loop`, instead of requiring callers to understand graph-family internals.

## 5. Draft ingestion and DOM mutation

A repository-grounded three-claim paragraph using explicit `[C-*] [S-*]` markers initially produced `total_claims=0`. Root cause: the semantic extractor returned an empty claim list without throwing, so the existing fallback was never used.

Hardening implemented:

- non-empty `text + zero extracted claims` is treated as degraded extraction;
- sentence-level fallback spans preserve citation markers;
- citation suffixes remain attached to the preceding sentence;
- lowercase technical sentence starts after citations are supported;
- the degraded path is marked explicitly (`degraded_extraction=true`).

After hardening:

- 3 claims detected;
- 3/3 linked to DOM by explicit claim IDs;
- `needs_source=0`;
- paragraph `complete=true`;
- `--apply` adds no duplicate claims and links all three existing claims.

Verdict: **PASS after hardening**.

## 6. Researcher boundary

The read-only adapter preserved the canonical authority:
`scripts/researcher/verify_claims.py`.

Important observed behavior:

- non-numeric textual claims remain `OPEN` even when `sources[].text` is identical; the current Researcher bridge intentionally does not perform general textual evidence entailment;
- project bookkeeping quantities such as `54 tracked files` become `AMBIGUOUS / NOT_COMPARABLE` because `tracked` is not a registered scientific unit;
- the scientific control `900 МПа` is normalized to `mpa` and returns `SUPPORTED`, confidence `0.8`, numeric `MATCH`.

Verdict: **CORRECT BUT NARROW**. The bridge is reliable for its implemented numeric/formula/guard scope. It is not yet a general evidence entailment verifier.

## 7. Semantic round-trip and release

A second real-data defect was found in RTT: when hybrid extraction returned only a digest and zero claims, contract claims present verbatim in the draft were reported as `CLAIM_OMISSION`.

Hardening implemented:

- digest-only/non-empty draft paragraphs receive sentence-level fallback candidates with absolute spans;
- these candidates are marked `qa_status=DEGRADED_FALLBACK`;
- the RTT comparator still performs the actual semantic comparison, so fallback segmentation cannot turn a mismatch into an automatic PASS.

After hardening, the project-count example has:

- semantic round-trip: `PASS`;
- evidence: `FAIL` (`AMBIGUOUS` quantities);
- traceability: `FAIL` because unresolved evidence is asserted without uncertainty marking.

This is the desired diagnostic separation.

The scientific control (`900 МПа`) gives a complete release:

- draft linked: PASS;
- Researcher evidence: SUPPORTED / MATCH;
- traceability: PASS;
- semantic round-trip: PASS;
- release: **PASS**, `release_allowed=true`.

## 8. CLI side-effect defect

`research-adapt --help` and `release-check --help` emitted Python `runpy RuntimeWarning` because package `__init__.py` eagerly imported the module that was then executed with `-m`.

The package initializers are now side-effect free. CLI stderr is clean.

## 9. What the module currently builds as artifacts

Observed artifact chain for this run:

1. `01_structure_plan.json` — topic decomposition, slots and gaps;
2. `*_extract.json` — reference paragraph extraction/digests;
3. `*_graphs.json` — reference graph artifacts;
4. `04_real_dom.yaml` / `13_numeric_dom.yaml` / `21_science_dom.yaml` — writing object state;
5. `*_draft_apply.json` — claim binding, completeness and style-selection result;
6. `*_dom_applied.yaml` — DOM after bounded draft application;
7. `*_verification.json` — read-only Researcher verdict projection;
8. `*_release.json` — aggregate evidence/traceability/RTT release decision.

The strongest property of the current architecture is that a failed release still retains all diagnostic gate outputs rather than collapsing into one generic FAIL.

## 10. Missing link for actual prose production

The deterministic Writer runtime does not contain a local prose-generation command. This is consistent with the agent architecture: `writing-orchestrator` dispatches article/chapter writer roles, and the resulting text enters `draft-loop`.

Therefore a fully automated chain still needs an explicit machine artifact between planning/DOM and the writer agent, for example:

`DraftRequest -> specialized writer agent -> DraftArtifact -> draft-loop`.

The current repository describes this behavior in agent/process contracts, but the canonical CLI does not yet materialize that handoff as a first-class artifact. This should be implemented before claiming that the subsystem itself executes “write section” end-to-end.

## 11. Hardening changes from the E2E probe

- side-effect-free `scripts.writer.research` package init;
- side-effect-free `scripts.writer.release` package init;
- draft-loop degraded extraction fallback;
- citation-aware/lowercase-safe fallback splitting;
- nested public graph artifact traversal in reference signature extraction;
- RTT degraded sentence fallback for digest-only extraction;
- six deterministic regression tests in `tests/test_writer_e2e_hardening.py`.

## 12. Regression gate

After all hardening changes:

- root Writer test discovery: **93/93 PASS**;
- `compileall scripts/writer`: PASS;
- base runtime compiler `--check`: PASS;
- capability runtime compiler `--check`: PASS;
- `git diff --check`: PASS.

## 13. Recommended next implementation order

1. Define `ReferenceBundle/1.0` and implement `writer reference-prepare` so public `extract/graphs` artifacts can feed reference selection without graph-family knowledge.
2. Define `DraftRequest/1.0` and `DraftArtifact/1.0`; make the writing orchestrator persist both.
3. Add genre/object registry selection (`dissertation`, `article`, `technical_report`, `chapter`, etc.) instead of silently using the autoreferat registry for every `plan --topic` and returning `UNKNOWN` for engineering Markdown.
4. Extend evidence verification beyond numeric/formula checks with exact-locator textual evidence entailment, while preserving Researcher as the authority.
5. Only then run the same E2E against the real dissertation DOM and source corpus; those data are not present in this repository snapshot.

## 14. Overall verdict

**The core Writer contracts are coherent and the release boundary works, but the complete authoring workflow is not yet end-to-end.** Draft binding, Researcher isolation, traceability, RTT and release are operational. The two missing production seams are reference preparation and the explicit planner/DOM -> writer-agent draft handoff. Object/genre inference also needs widening beyond the current academic registry.
