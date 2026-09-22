# 13. Writing Compiler Pipeline

## Compilation stages

### C0 Requirements compile
Input: user/project requirements. Output: policy snapshot + writing objective.

### C1 Semantic bind
Resolve ClaimSlots against eligible Researcher claims. Missing claims create typed `WriterGap` and optional `ResearchRequest`.

### C2 Argument compile
Instantiate argument schemes. Bind claims as premises/conclusion/counterclaim/warrant references. Argument roles are contextual and do not mutate epistemic truth.

### C3 Discourse compile
Transform argument needs into rhetorical moves: definition, result, contrast, limitation, synthesis, transition, conclusion.

### C4 Artifact bind
Bind quantities, equations, figures, tables, code, datasets, citations and terms by stable IDs. Hard factual objects are selected, never hallucinated.

### C5 Surface realization
Create Inline IR / structured prose. LLM may realize language within the writing contract.

### C6 Micro RTT
Sentence/paragraph semantic back-extraction and diff.

### C7 Integration
Compose section, resolve cross-references, local terminology and section interface contracts.

### C8 Meso/Macro RTT
Check section/document compression, conclusions, novelty, abstract and cross-section semantic fidelity.

### C9 Commit + dependency edges
Commit only after gates pass. New revision records exact inputs and validators.

### C10 Build/release
Global consistency, review, blocker closure, export and parse-back/visual QA.

## Compiler diagnostics are first-class

Every phase outputs diagnostics with:
`code`, `severity`, `entity`, `source phase`, `evidence`, `blocking`, `suggested operations`.

## Incremental compilation

A changed upstream entity triggers `affected_closure()` and recompiles only stale/rebuildable nodes, except when policy explicitly requests full audit.
