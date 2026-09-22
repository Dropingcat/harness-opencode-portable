# R4.4 L3B pipeline audit — grounded dialogue / conditional Advocate

Date: 2026-09-13

## Audited path

```text
Claim / AssessmentNeed
-> ArgumentGraph branch
-> DDC
-> DQC or ADC
-> RoleProviderBinding
-> TEX
-> Job / Attempt
-> provider output
-> PER
-> grounding validation
-> IQT / ARG
-> ArgumentGraph admission
-> DialecticObserver / ResearchChallenge
```

## Authority checks

| Boundary | Owner | L3B result |
|---|---|---|
| role selection | composition/response policy | unchanged; Advocate conditional |
| evidence visibility | DDC/DQC/ADC | PASS, hidden grounding rejected |
| provider selection | shared RPB policy | PASS |
| runtime endpoint | logical tool/runtime binding | PASS |
| semantic text | provider | untrusted until admission |
| grounding classification proposal | provider + deterministic characterization | PASS structural |
| source/evidence provenance | canonical EVD/SRC graph | unchanged authority |
| argument admission | deterministic runtime/ArgumentGraph | PASS |
| Claim truth | reducer/admission layer | not mutated |

## Edge cases exercised

- specialist answer grounded in disclosed evidence;
- specialist answer based only on MODEL_PRIOR;
- Advocate grounded QUALIFY;
- Advocate attempted prior-only DEFEND;
- Advocate hidden sibling evidence/grounding;
- previous L3A wrong/zero/multiple provider cases;
- stale provider, timeout, invalid JSON, hidden output refs;
- two role families.

## Observed routing semantics

```text
MODEL_PRIOR specialist answer
-> ARG retained
-> MISSING_EVIDENCE blocking discovery
-> AdditionalEvidenceRequest
-> research path remains required
```

```text
MODEL_PRIOR Advocate DEFEND
-> deterministic REQUEST_EVIDENCE
-> REPLIES_TO only
-> no DEFENDS
-> REQUEST_LOCAL_RESEARCH
```

```text
DOCUMENTED Advocate QUALIFY/DEFEND
-> REPLIES_TO
-> DEFENDS
-> possible continued cross-exam
```

## Traceability statement

L3B can now distinguish:

```text
who answered
which semantic role they held
which provider/runtime executed it
which branch/evidence they saw
which refs they cited
what grounding origin they declared
whether the response was admitted
what argument/relation was produced
what research debt followed
```

The remaining universal traceability debt TD-038 is about indexing/querying this lineage across all modules/phases, not absence of local lineage facts.

## Audit conclusion

No new runtime authority bypass was introduced. Conditional Advocate reuses existing provider/runtime authority. The major remaining risk is semantic honesty/calibration of a real production provider, which cannot be evaluated in the current environment.
