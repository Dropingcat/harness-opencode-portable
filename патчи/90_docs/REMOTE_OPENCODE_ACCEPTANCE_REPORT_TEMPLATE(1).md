# Remote OpenCode / Harness Acceptance Report

## A. Identity

- Harness package name:
- Harness Git HEAD:
- Git status before test:
- Host OS / architecture:
- Python version:
- OpenCode CLI path:
- OpenCode version:
- OpenCode binary SHA256:
- Model identifier:
- Provider identifier/config profile (sanitized):
- Test start UTC:
- Test finish UTC:

## B. Integrity and deterministic baseline

| Test | Result | Evidence file / command | Notes |
|---|---|---|---|
| T00 package/git integrity | | | |
| T01 environment capture | | | |
| T02 R4 acceptance | | | |
| T03 compiler/static gates | | | |
| T04 full Researcher baseline | | | |
| T05 named L3/L3B edge tests | | | |
| T06 production provider preflight | | | |

For T04, the expected pre-existing baseline is four TD-015 failures (2 Guard + 2 LocalCorpus). Any additional/different failure is a regression and must be listed verbatim.

## C. Production semantic trace

### S1 Q1 → A1

- Q1 IQT id:
- Q1 text:
- questioner role:
- answer role:
- RPB id/fingerprint:
- TEX id/fingerprint:
- `question_turn_id` visible in A1 TEX: YES / NO
- provider PER status:
- A1 ARG id:
- A1 position:
- grounding state:
- grounding items:
- evidence refs cited:
- target refs cited:
- discoveries:
- additional evidence requests:
- observer action after A1:

### S2 Q2 → A2 (only if a genuinely new issue surface was admitted)

- Was Q2 executed: YES / NO
- New issue signature targeted:
- Why Q2 was/was not allowed:
- Q2 text:
- A2 position:
- A2 grounding state:
- observer action after A2:
- research request created:

### S3 Conditional Advocate

- Advocate activated: YES / NO
- Activation reason codes:
- ADC id/fingerprint:
- RPB/TEX/PER ids:
- outcome: DEFEND / QUALIFY / CONCEDE_LOCAL_POINT / REQUEST_EVIDENCE / OPEN
- grounding state:
- REPLIES_TO relation created: YES / NO
- DEFENDS relation created: YES / NO
- If DEFENDS exists, identify disclosed evidence/derivation supporting it:
- If only MODEL_PRIOR was used, was DEFENDS prevented: YES / NO

### S4 Prior-only test

- Did provider fabricate/cite a non-disclosed evidence ref: YES / NO
- Position:
- Grounding:
- Did Harness preserve OPEN/research debt when evidence was absent: YES / NO
- Any hallucinated locator/source:

## D. Branch isolation and authority checks

- hidden sibling EVD present in Q1 TEX: YES / NO
- hidden sibling EVD present in A1 TEX: YES / NO
- provider attempted hidden ref: YES / NO
- if attempted, PER status was REJECTED: YES / NO
- runtime silently switched provider after binding: YES / NO
- more than one executor used for a single RPB: YES / NO

## E. Semantic-quality observations

Rate only after reading raw traces. Do not modify outputs.

- Did the question target the actual challenged issue rather than paraphrase the Claim?
- Did A1 distinguish evidence from remembered/model knowledge?
- Did discoveries add genuinely new surfaces or merely reword prior objections?
- Did Q2 depend on an admitted new issue from A1?
- Did Advocate test defensibility or merely rationalize the original position?
- Were uncertainty/scope qualifiers preserved?
- Any unsupported causality upgrade?
- Any invented source/ref/measurement?
- Any answer evasion?
- Any repeated/no-progress loop?

## F. Repetition / variability

For three repeated semantic runs using unchanged Harness/model/config:

| Run | Q1 fingerprint/text changed? | A1 position | Grounding | New issue count | Advocate outcome | Contract violation |
|---|---|---|---|---:|---|---|
| R1 | | | | | | |
| R2 | | | | | | |
| R3 | | | | | | |

List semantic differences that are material to scientific conclusions.

## G. Verdict

Choose one:

- PASS — production semantic provider respects contracts and no blocking semantic defect observed.
- PASS_WITH_FINDINGS — structurally valid but calibration/semantic issues need follow-up.
- FAIL_CONTRACT — provider output violated bounded contract/admission.
- FAIL_RUNTIME — provider/transport/runtime could not execute reliably.
- FAIL_REGRESSION — deterministic Harness baseline changed unexpectedly.

Verdict:

Blocking findings:

Non-blocking findings:

Suggested next experiments (do not implement during this acceptance):
