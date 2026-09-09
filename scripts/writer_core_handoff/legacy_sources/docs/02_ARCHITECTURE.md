# 02. Writer Core 2 — Architecture v0.2

## 1. System boundary

```text
                           REQUIREMENTS
                               │
                     Requirement Compiler
                               │
                        Policy Resolution
                               │
                               ▼
RESEARCHER CORE ────── Epistemic Projection ──────────────┐
(read-only truth)             │                            │
                              ▼                            │
                       Writing Contract                   │
                              │                            │
                              ▼                            │
                  Writing Decomposition DAG               │
                              │                            │
               ┌──────────────┼───────────────┐            │
               ▼              ▼               ▼            │
          Argument Graph  Discourse Graph  Artifact Plan   │
               └──────────────┼───────────────┘            │
                              ▼                            │
                       Semantic Compiler                   │
                              │                            │
                       Surface Realizer                    │
                              │                            │
                              ▼                            │
                    Document AST / Inline IR               │
                              │                            │
              ┌───────────────┼────────────────┐           │
              ▼               ▼                ▼           │
        Back-extraction   Object checks   Citation checks  │
              └───────────────┼────────────────┘           │
                              ▼                            │
                    Round-trip Validator ◄─────────────────┘
                         │             │
                       FAIL           PASS
                         │             │
                   Repair/Blocker     Commit
                                       │
                                       ▼
                           Dependency Build Engine
                                       │
            ┌──────────────────────────┼────────────────────┐
            ▼                          ▼                    ▼
 Global Consistency            Review/Decisions        Artifact Rebuild
            └──────────────────────────┼────────────────────┘
                                       ▼
                                Release Candidate
                                       │
                           Export + Visual/Parse-back QA
                                       │
                                       ▼
                              Reproducible Artifact
```

Forensics is separate:

```text
Reference/Public Artifacts → Fingerprints → Confounder-aware comparison
                          → Work Lineage → calibrated hypotheses
```

## 2. Bounded contexts

1. **Document Structure**: containment/order only.
2. **Writing Decomposition**: communication objective → needs/slots/operations.
3. **Discourse**: rhetorical moves and local/global composition.
4. **Argumentation**: premises, warrants, rebuttals, conclusions as use-contexts.
5. **Epistemic Projection**: read-only Researcher truth references.
6. **Artifact/Symbol**: quantities, uncertainty, formulas, figures, tables, datasets, code, terms.
7. **Citation/Provenance**: exact trace from realized span to evidence/source/version.
8. **Policy/Constraint**: genre/domain/risk/institution/journal/style/numeric/review rules.
9. **Revision/Dependency**: freshness, impact closure, selective rebuild.
10. **Execution**: operations/model calls/validators/snapshots/builds.
11. **Forensics Fingerprint**: analytical feature projections.
12. **Work Lineage**: reuse/evolution relations between artifacts.

No context may silently become another context's source of truth.

## 3. Semantic compiler phases

```text
P1 Bind semantics
P2 Compile argument
P3 Compile discourse
P4 Bind artifacts/symbols
P5 Surface realization
P6 Micro RTT
P7 Section integration + meso RTT
P8 Global consistency + macro RTT
P9 Dependency commit
P10 Review/release build
```

Each phase accepts typed IR, emits typed IR + diagnostics. LLM is allowed only in declared model-assisted transforms.

## 4. Runtime authority

Static program/config:
`schemas/`, `templates/`, `policies/`, registries → Git/YAML.

Runtime state:
SQLite materialized state + append-only event log.

Epistemics:
Researcher snapshot/version references, immutable from Writer.

Build artifacts:
MD/DOCX/PDF and rendered figures are disposable/rebuildable outputs.

## 5. Completion semantics

`TEXT_COMPLETE` does not mean document complete.

Release readiness requires:

```text
required writing slots closed
AND no RELEASE_BLOCKING blockers
AND no STALE critical dependencies
AND hard RTT passes
AND quantitative/artifact integrity passes
AND review policy satisfied
AND export QA passes
```

## 6. Critical architectural property

The system must be able to answer for any final factual span:

> Which claim does this realize? Which evidence/source version supports it? Which scope/qualifier applies? Which template/policy/model produced it? Which data/formula/figure dependencies exist? What changes would invalidate it?

If this trace cannot be reconstructed, the build is not auditable.
