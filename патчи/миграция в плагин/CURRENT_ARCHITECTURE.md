# Current Architecture — Harness

## 1. Authority model

### Writer
Владеет документным состоянием, drafting/review, reference/evidence projections, Writer DOM, provenance/change ledger, semantic round-trip validation и repair. Не превращает формулировку в научный факт автоматически.

### Researcher
Владеет ResearchDOM, Claim/Evidence, relation/uncertainty, ReviewWorkField, Tribunal composition, dialectic, ArgumentGraph, Gap/ResearchChallenge, grounding и admission.

### Coder
Владеет event-sourced factory state, worker/reviewer/tester/auditor loop, artifact provenance, replay, budgets/gates и explicit workspace authority.

### Shared runtime
Router, Job/Attempt, orchestration, capability/provider policy, capsules, memory и kanban. Это control plane, а не дополнительный источник предметной истины.

### OpenCode Native Plugin
Host adapter/transport:
- normalizes host context;
- exposes minimal tools;
- bridges to Python Core;
- later executes semantic requests through official OpenCode runtime.

Plugin не выбирает scientific role, route, evidence slice, claim truth или authoritative state.

## 2. Core invariants

1. LLM предлагает/аргументирует; код решает authoritative transitions.
2. Work plane и control plane разделены.
3. Observation != admission != relation assessment != claim truth.
4. ResearchDOM историчен/исполнительный; KnowledgeGraph предметный.
5. Challenge branches append-only/history-preserving.
6. Uncertainty многомерна; отсутствующая ось не считается RESOLVED.
7. Specialized roles остаются specialized; no god-agent.
8. Peer delegation использует общий Job/Attempt runtime.
9. Provider fallback создаёт новую binding lineage.
10. Semantic response != evidence; grounding/provenance обязательны.
11. `MODEL_PRIOR` может породить гипотезу, но не evidence.

## 3. Researcher R4.4 current boundary

Реализованные/описанные контракты:
- TribunalCompositionPlan;
- EvidenceSlice;
- independent role execution;
- DialecticBranchRef;
- DDC/DQC/ADC;
- ArgumentGraph;
- conditional Advocate;
- RPB;
- TEX;
- PER;
- grounding profile;
- graph admission before observer.

Defender трактуется как response function, а не отдельный обязательный agent. Response ownership и multidisciplinary ClaimReviewCase остаются развитием.

## 4. Future scientific layer

Запланированы:
- ResponseAssignment;
- ClaimReviewCase/ReviewFacet/JoinProjection;
- HypothesisCase + append-only revisions;
- evidence independence/dependency groups;
- EvidenceDigest + HypothesisEvidenceLink.

Эти объекты не должны быть протащены в plugin layer.

## 5. Module inventory

- `scripts/writer/`
- `scripts/researcher/`
- `scripts/code-factory/`
- `scripts/router/`
- `scripts/jobs/`
- `scripts/orchestration/`
- `scripts/capsules/`
- `scripts/memory/`
- `scripts/kanban/`
- `agents/`
- `skills/`
- `mcp/`
- `config/`
- `shared/`

Native plugin target package:
- `packages/opencode-harness-plugin`

Legacy host shell должен постепенно покинуть authority path.
