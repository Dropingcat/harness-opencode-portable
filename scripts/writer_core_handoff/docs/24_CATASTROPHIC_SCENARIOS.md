# 24. Catastrophic Scenario Protocols

Architecture is tested against failure narratives, not only happy-path unit tests.

## S1 Source retracted before submission

Expected: source version event → evidence reassessment → affected claim closure → stale/invalid downstream → release blocker → alternative evidence/rewrite/retraction resolution.

## S2 Raw table corrected after figures are approved

Expected: immutable new raw-data version → computation closure → quantities/figures/tables rebuild → claims reverify → conclusions/abstract stale as needed.

## S3 Two agents rewrite same chapter

Expected: semantic merge; conflicts classified; no line-based silent overwrite; merged version runs RTT/global consistency.

## S4 Reviewer demands stronger/weaker interpretation

Expected: ReviewIssue + Decision; Writer may change rhetorical strength only within epistemic contract. Stronger-than-evidence request creates conflict, not automatic compliance.

## S5 150 pages compressed into 20-page abstract

Expected: visibility selection + compression plan + macro RTT; qualifiers/scope/uncertainty protected; omissions recorded intentionally.

## S6 New experiment contradicts defense position #3

Expected: conflict admitted in Researcher → defense claim dependency stale/invalid → contribution/novelty/conclusion closure → release block until resolved.

## S7 Export silently breaks equations/figure numbering

Expected: parse-back/visual preflight fail; source IR remains unchanged; export rebuild only.

## S8 Template/policy upgraded mid-project

Expected: versioned policy snapshot; no silent retroactive mutation. Explicit migration/rebuild plan.

## S9 LLM inserts plausible but nonexistent DOI/number

Expected: structured object binding rejects free factual token; RTT/citation validator fail closed.

## S10 Human manually edits DOCX after build

Expected: external artifact hash divergence; import/reconcile operation required; built DOCX is not authoritative state.

Each scenario has a YAML fixture in `examples/catastrophic/` and must become an integration test before production release.
