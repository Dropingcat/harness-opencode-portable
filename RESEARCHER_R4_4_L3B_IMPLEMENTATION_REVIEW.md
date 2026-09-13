# R4.4 L3B grounded dialogue + live conditional Advocate — implementation review

Date: 2026-09-13
Review basis: performed after process-level E2E and full Researcher regression.

## Scope actually reviewed

This review covers the structural/runtime L3B slice only:

- live answer grounding classification;
- research coupling for model-prior-only answers;
- conditional Advocate provider binding and execution;
- Advocate grounding and branch-local disclosure;
- Advocate response admission to ArgumentGraph;
- compatibility with existing L3A Q1/A1/Q2/A2 process E2E.

It does not claim production semantic-provider quality because `opencode` is unavailable.

## E2E findings

### F1 — role authority is not evidence authority

A specialist can be correctly addressed and correctly executed while still producing an epistemically weak answer. The new grounding profile captures this explicitly. This closes an important conceptual hole exposed by `answer_role_id`: knowing who answered is not enough to know why the answer should matter scientifically.

### F2 — model prior is useful but must create research debt

A MODEL_PRIOR-only specialist answer is retained as a traceable hypothesis but receives blocking MISSING_EVIDENCE and a typed AdditionalEvidenceRequest. This is preferable to either discarding potentially useful domain knowledge or silently treating training memory as literature.

### F3 — Advocate without evidence was previously too easy to rationalize

The structural Advocate path could produce DEFEND based on prose justification. Live grounding makes this unsafe. L3B converts prior-only DEFEND to REQUEST_EVIDENCE and creates no DEFENDS relation. This sharply reduces rationalization risk.

### F4 — grounding visibility must be validated separately from citation visibility

A provider could theoretically cite only allowed refs while describing a hidden branch as its reasoning basis. Grounding refs are therefore separately checked against DDC/ADC visibility. Hidden sibling grounding now fails closed.

### F5 — live Advocate should reuse provider authority, not own another runtime

The existing RPB/TEX/PER substrate was sufficient. Adding a second Advocate-specific provider registry would have duplicated capability health, cardinality and runtime-binding policy for no benefit.

### F6 — multidisciplinary review should not destructively split Claim identity

The current ArgumentGraph already proves that independent branches can coexist under one root. Future ClaimReviewCase should reuse this principle at the Claim review level: one root CLM, independent facet branches, explicit cross-facet dependency/conflict/synergy, deterministic non-voting join.

## Known limitations

1. Actual OpenCode/LLM semantic execution is not available in this environment.
2. Grounding honesty is currently provider-declared and deterministically checked for ref visibility, not semantically proven. Real traces are needed to calibrate false grounding declarations.
3. `MODEL_PRIOR` detection is explicit-contract based. A dishonest model could phrase remembered knowledge as a derivation. Future observer calibration and Writer/Researcher semantic checks should test this.
4. Existing historical first-pass ArgumentArtifacts are often `UNCHARACTERIZED`; migration should not retroactively invent grounding provenance.
5. EVD/SRC provenance remains the authoritative route for “where was this written/measured/who asserted it”. Grounding points to EVD/ARG/etc.; it does not replace source provenance.
6. ResponseAssignment and multidisciplinary ClaimReviewCase remain future architecture (TD-046/047).

## Acceptance evidence

- R4 targeted: 109/109 PASS.
- Full Researcher: 586 total / 582 PASS / only four known TD-015 failures.
- runtime compiler PASS, hash unchanged from L3A authority update.
- capability compiler PASS, hash unchanged from L3A authority update.
- compileall PASS.
- git diff --check PASS before documentation freeze.
- actual shared preflight: `existing.opencode_tribunal_role` implemented=true, available=false, detail=`missing:opencode`.
- pre-production feature checkpoint: `8204ce6bcbca56c42d6e4fb5ec458c2e1d71e99e`.
- milestone ZIP: `RESEARCHER-R4.4-L3B-PREPROD-GROUNDED-DIALOGUE-001.zip`, SHA256 `1ba3840813ccec2709288470c10852b4e9837a6b025ac157b0f2a9c35cf7bcf1`.

## Review conclusion

The L3B structural/process slice is coherent enough to preserve as a checkpoint. It materially improves scientific traceability by distinguishing semantic response provenance from source evidence provenance and proves conditional Advocate execution through the same bounded runtime.

Do not label the production semantic dialogue gate complete until one authorized real semantic provider runs the unchanged DQC/ADC contracts and its grounding/closure behavior is evaluated on actual traces.
