# Researcher R4.4 L3A — Provider Binding and Executable Bounded Dialogue Architecture

Date: 2026-09-13
Status: implemented structural/runtime slice; production semantic provider execution remains environment-blocked.

## 1. Purpose

L2b made questions, disclosures and branch history reproducible. L3A makes one bounded question/answer transaction executable without collapsing semantic role, provider selection and runtime transport into one opaque model call.

The authority chain is:

```text
ArgumentGraph branch
-> DialecticDisclosureContract (DDC)
-> DialecticQuestionContract (DQC)
-> RoleProviderBinding (RPB)
-> TribunalExecutionEnvelope (TEX)
-> existing child Job / Attempt
-> ProviderExecutionReceipt (PER)
-> InquiryTurn / ArgumentArtifact
-> ArgumentGraph admission
-> DialecticObserver
```

No provider output directly mutates Claim/GraphEdge/Gap/Conflict truth state.

## 2. Critical semantic distinction: questioner vs answerer

L2b DQC originally recorded the questioner's role but not an explicit addressed responder. Live E2E exposed that inferring the responder from the target ARG can route a Skeptic's question back to the Skeptic.

DQC is therefore upgraded to schema `dialectic-question-contract/1.1` and now records:

```text
role_id         = questioner role
answer_role_id  = addressed semantic responder
```

Current bounded dialogue rejects `role_id == answer_role_id`. If future self-review is desired it requires a separate explicit policy/contract rather than silent reuse of cross-examination semantics.

Legacy serialized DQC/1.0 cannot be safely upgraded by guessing the responder and is rejected with an instruction to recompile from branch context.

## 3. Role, provider and runtime tool are different objects

```text
Role
  semantic duty / competence

Provider
  authorized implementation capable of executing a role contract

Runtime tool
  concrete executable endpoint selected by existing runtime authority
```

Example:

```text
xrd_specialist
  != existing.opencode_tribunal_role
  != tribunal_role launcher
```

Provider priority never overrides semantic role-kind or contract compatibility.

## 4. RoleProviderBinding/1.0 (`RPB-*`)

`RoleProviderBinding` is a deterministic provider-selection snapshot. It records:

- DQC/IQC/ADC contract id;
- semantic role id and role kind;
- execution kind (`FIRST_PASS / QUESTION / ANSWER / DEFENSE`);
- required logical execution capability;
- all eligible candidate provider ids;
- reason-coded rejected providers;
- selected provider id;
- selected runtime tool/provider binding;
- requested/max executor cardinality;
- provider health snapshot fingerprint;
- selected provider-authority fingerprint;
- selected runtime-binding fingerprint;
- preflight fingerprint;
- composition policy version/hash;
- provider-binding policy version/hash;
- capability policy hash;
- final binding fingerprint.

Selection is fail-closed.

### 4.1 Compatibility filters

A candidate provider must satisfy all of:

```text
required capability
+ admitted role kind
+ execution contract namespace
+ allowed provider kind
+ enabled
+ live probe declared when required
+ executor cardinality
+ current preflight health
+ runtime tool binding exists
```

### 4.2 Multiple providers

If several providers are healthy and compatible, the policy selects exactly one using deterministic priority + provider-id tie-break.

This does not authorize redundant execution. `requested_executor_count > max_executors_per_contract` fails closed. Independent duplicate reviewers require a future explicit review policy.

### 4.3 Stale binding

Provider health is checked again before Attempt creation. A provider that becomes unavailable after binding invalidates execution before child-job creation.

No silent fallback mutates an existing RPB. Retry/fallback requires a new preflight and a new binding lineage.

## 5. Shared provider authority

L3A does not create a Tribunal provider registry.

It adds the logical capability/tool/provider into the existing authority sources:

```text
capability: tribunal.role.execute
logical tool: tribunal_role
provider: existing.opencode_tribunal_role
runtime binding: mcp/launchers/opencode_tribunal_role.py
```

The shared preflight currently reports the production provider as:

```text
implemented = true
available = false
status = degraded
detail = missing:opencode
```

This is treated as runtime unavailability, not epistemic `OPEN`.

## 6. TribunalExecutionEnvelope/1.0 (`TEX-*`)

TEX is the complete bounded provider input. It contains only material explicitly disclosed by DDC/DQC:

- RPB id/fingerprint;
- DQC id;
- role and execution kind;
- branch key;
- DDC id/fingerprint;
- instruction id/fingerprint;
- visible ARG ids;
- visible IQT ids;
- visible Evidence refs;
- visible target refs;
- serialized DQC control contract;
- bounded material payload;
- response token limit;
- expected provider-output schema;
- envelope fingerprint.

A hidden sibling object is not merely forbidden in prompt prose; it is absent from TEX.

TEX crosses Job/runtime boundaries through a canonical JSON-safe projection rather than internal immutable Python mappings.

## 7. ProviderExecutionReceipt/1.0 (`PER-*`)

PER records what happened at the runtime boundary independently of semantic output:

```text
COMPLETED
FAILED
TIMED_OUT
REJECTED
```

Important distinction:

```text
FAILED / TIMED_OUT
  runtime/provider did not produce a usable result

REJECTED
  provider returned a result but deterministic contract admission rejected it

OPEN
  provider executed successfully and a valid scientific response concludes evidence is insufficient
```

PER is persisted even when no IQT/ARG is admitted.

Examples:

- timeout -> `PER(TIMED_OUT)`, child `FAILED_NO_OUTPUT`;
- invalid JSON -> `PER(FAILED)`;
- hidden sibling citation -> `PER(REJECTED)`;
- valid unresolved answer -> `PER(COMPLETED)` + `ARG(position=OPEN)`.

## 8. Provider-output admission order

Live output must pass the following order:

```text
provider output
-> expected output schema
-> DDC/DQC ref/need validation
-> IQT + ARG materialization
-> ArgumentGraph admission (REPLIES_TO)
-> branch refresh
-> DialecticObserver
```

Observer cannot consume a live ARG before that ARG exists in the current ArgumentGraphProjection.

## 9. Executable vertical

The process E2E exercises:

```text
material challenge
-> DDC(DIRECT_QUESTION)
-> DQC(Q1, questioner=skeptic, answer=xrd_specialist)
-> RPB(questioner)
-> TEX(question)
-> subprocess question worker
-> IQT Q1 + PER
-> RPB(answerer)
-> TEX(answer)
-> subprocess answer worker
-> IQT A1 + ARG A1 + PER
-> graph admission
-> observer admits new ASSUMPTION_ISSUE
-> DDC(QUESTION_ON_ANSWER)
-> DQC(Q2, questioner=methodologist, answer=xrd_specialist)
-> Q2 / A2 via Job/Attempt
-> ARG A2(position=OPEN, AdditionalEvidenceRequest)
-> graph admission
-> observer -> REQUEST_LOCAL_RESEARCH
```

Hidden sibling refs stay absent from all envelopes.

A second role-family E2E addresses `crystallographer (DOMAIN)` while a higher-priority METHOD provider is also healthy. Binding still selects the DOMAIN provider, proving priority is subordinate to role compatibility.

## 10. Edge cases covered

- wrong requested role -> `ROLE_MISMATCH`;
- questioner equals answerer -> DQC rejected;
- explicit wrong provider -> `WRONG_PROVIDER`;
- provider has capability but wrong role kind -> rejected;
- provider has capability/role kind but wrong contract namespace -> rejected;
- no healthy provider -> `NO_HEALTHY_PROVIDER`, no semantic OPEN;
- several compatible healthy providers -> deterministic single selection;
- requested executor count exceeds policy -> `EXECUTOR_CARDINALITY_EXCEEDED`;
- provider health changes after binding -> execution stops before child Job;
- timeout -> runtime failure, durable PER;
- invalid JSON -> runtime failure, durable PER;
- hidden sibling evidence in output -> deterministic rejection, durable PER;
- output ARG not yet in graph -> observer path blocked until graph admission.

## 11. Replay / traceability

RPB, TEX and PER support serialized round-trip and fingerprint validation.

The local reproducible lineage is now:

```text
DQC
-> RPB
-> TEX
-> Job / Attempt
-> PER
-> IQT / ARG
-> ArgumentGraph revision
-> DialecticObservation
```

This materially advances TD-038 but does not replace the future universal traceability index.

## 12. Response ownership is still larger than DQC addressing

Explicit `answer_role_id` fixes one turn. It does not determine who *ought* to answer a multidisciplinary/facet-specific question.

Future architecture is documented in `RESEARCHER_R4_4_FUTURE_RESPONSE_OWNERSHIP_MULTIDISCIPLINARY_REVIEW.md` and tracked as TD-046/TD-047.

The future control layer should separate:

```text
facet/position owner
response function
selected semantic responder
conditional Advocate
runtime provider
```

Provider binding must remain downstream of that semantic ownership decision.

## 13. Current limitations

1. Production OpenCode role provider is implemented but unavailable in the current environment, so semantic LLM quality is not tested here.
2. Conditional Advocate has not yet been executed through the live provider-binding path.
3. Live observer calibration remains TD-042.
4. Multidisciplinary response ownership/fork-join remains TD-046/TD-047.
5. Universal cross-module trace query/index remains TD-038.

## 14. Current milestone interpretation

This slice should be named **R4.4 L3A Provider Binding + Executable Bounded Dialogue Envelope**.

It is valid to freeze provider/runtime contracts and process-boundary E2E now. It is not valid to claim production semantic Tribunal completion until an actually available authorized semantic provider executes the same envelope and a live conditional Advocate path is tested.
