# Academic Sentence Realization Engine

## Principle
A weak LLM SHOULD NOT be asked to produce a polished academic sentence from a blank page. It should construct or rank a typed `SentencePlan`.

## Pipeline
```text
Semantic IR
 -> CommunicativeAct
 -> RhetoricalPattern
 -> AcademicFrame
 -> ClausePlan
 -> lexical candidates
 -> syntax/linearization
 -> morphology/agreement/government
 -> surface candidates
 -> rerank
 -> linguistic RTT
```

## SentencePlan
Contains:
- semantic anchors / claim refs;
- communicative act;
- sentence frame;
- clause graph;
- theme/rheme plan;
- lexical concept choices;
- connective choice;
- split/merge decision;
- required qualifiers and scope;
- forbidden semantic upgrades.

## Construction registries
The realization engine uses independent registries:
- `AcademicFrameRegistry`;
- `SyntacticConstructionRegistry`;
- `LexicalChoiceGraph`;
- `ValencyRegistry`;
- `CollocationRegistry`;
- `ConnectiveRegistry`;
- `AcademicRUExpressionRegistry`.

## Code-owned operations
Agreement, inflection, stable cross-references, quantity rendering and basic government checks SHOULD be deterministic wherever feasible.

## Model-owned choices
Frame selection, clause ordering, lexical reranking, information structure and controlled reformulation remain semantic choices inside bounded affordances.

## Candidate generation
Prefer generation/reranking of 3–5 structurally different candidates over unconstrained one-shot prose. Candidate diversity concerns construction, not semantic truth.
