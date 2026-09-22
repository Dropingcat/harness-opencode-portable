# R4.4 L3A Pipeline Audit

Date: 2026-09-13

## Pipeline

```text
RWF AssessmentNeed
-> TribunalCompositionPlan
-> EvidenceSlice
-> ArgumentGraph branch
-> DDC
-> DQC/1.1(questioner, answer_role)
-> role-kind / contract / capability requirements
-> shared provider preflight
-> RoleProviderBinding (RPB)
-> TribunalExecutionEnvelope (TEX)
-> child Job / Attempt
-> provider invocation
-> ProviderExecutionReceipt (PER)
-> deterministic typed admission
-> IQT / ARG
-> ArgumentGraph admission
-> branch refresh
-> DialecticObserver
-> CONTINUE | OPEN | REQUEST_LOCAL_RESEARCH | RECOMPOSE
```

## Authority audit

| Layer | Owns | Must not own |
|---|---|---|
| DQC | question target + questioner + addressed responder + bounded refs/budget | provider choice, Claim truth |
| RPB | one authorized runtime provider selection | semantic role definition, evidence widening |
| TEX | exact serialized bounded provider input | search/discovery outside disclosure |
| Provider | semantic proposal within TEX | authority expansion/state mutation |
| PER | runtime outcome/provenance | semantic truth |
| ARG/IQT admission | schema/ref/need lineage checks | final Claim assessment |
| ArgumentGraph | historical review topology | KnowledgeGraph truth |
| DialecticObserver | typed issue/progress projection | Claim truth |

## Failure-state audit

```text
NO_HEALTHY_PROVIDER
  -> no Attempt / runtime unavailable

TIMED_OUT
  -> Attempt TIMED_OUT / child FAILED_NO_OUTPUT / PER only

FAILED
  -> provider/transport malformed or crashed / PER only

REJECTED
  -> provider returned data but violated DDC/DQC/admission / PER only

OPEN
  -> valid semantic ARG after successful provider execution
```

## Edge-case audit

- wrong role: fail closed;
- self-answer: fail closed;
- wrong provider: fail closed;
- wrong role kind: fail closed;
- wrong contract namespace: fail closed;
- no healthy provider: fail closed;
- more candidates than needed: deterministic single bind;
- more executors requested than allowed: fail closed;
- provider disappears after bind: no child job;
- hidden sibling citation: REJECTED;
- output not yet in AGP: cannot reach observer;
- domain responder vs higher-priority method provider: DOMAIN provider wins by compatibility.

## Trace audit

Minimum local replay chain:

```text
DQC/1.1
RPB/1.0
TEX/1.0
Job + Attempt
PER/1.0
IQT/ARG
ARL(REPLIES_TO)
AGP revision
DialecticObservation
```

Each provider-dependent object carries policy/authority/health/runtime fingerprints sufficient to detect stale or changed execution context.

## Remaining audit gap

No production semantic provider is live in this environment. Therefore quality/calibration assertions about question quality, answer-evasion detection and Advocate usefulness are explicitly not made here.
