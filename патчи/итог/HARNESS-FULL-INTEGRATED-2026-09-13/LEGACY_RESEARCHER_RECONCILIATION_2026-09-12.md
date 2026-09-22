# Legacy Researcher reconciliation — 2026-09-12

Source archive: `doc_AI_ReWriter.zip` supplied by the user. These documents are treated as historical architecture evidence, not current runtime authority.

## 1. Legacy concepts confirmed by the archive

The archive confirms that the original Researcher was designed around several ideas now being restored in `researcher_core`:

- hierarchical `topics_tree`, not only a flat topic list;
- node depth/context determines specialist scope;
- node pattern inherits parent context plus local specialization;
- claims attach to topical/tree nodes;
- dynamic expert/tribunal composition from node semantics;
- permanent meta-critics such as skeptic/advocate plus domain specialists;
- search escalation only for unresolved/ambiguous branches rather than global brute-force search;
- OPEN/alarm as a legitimate result when evidence does not converge;
- iterative/local graph expansion around unresolved claims;
- accumulation of domain-map/knowledge relations across runs;
- deterministic limits on expansion depth, node count and budget;
- search-validation cycles that record accepted/rejected sources and queries.

Relevant legacy documents include:

- `36-master-plan.md`: tree of directions, inherited node patterns, local escalation graph, OPEN cutter, accumulated map;
- `34-dynamic-expert-system-plan.md`: topic profiler, expert router, expert registry, dynamic tribunal;
- `21-iteration-2-plan-final-v3-judiciary.md`: advocate and tribunal roles;
- `27-search-validation-cycles.md`: iterative source validation and search trace;
- `38-implementation-plan.md`: staged implementation, baseline-first integration, explicit non-goals;
- `07-dag-map-reduce-long-context.md`: DAG/map-reduce framing;
- `08-meta-modelirovanie-processa.md` and `09-distillyaciya-cherez-simulyaciyu.md`: iterative simulation/meta-optimization ideas.

## 2. Mapping legacy concepts to current architecture

| Legacy concept | Current canonical direction | Status |
|---|---|---|
| `topics_tree.json` | `ResearchMap + ResearchDOM + ResearchCard` | RESTORED / stronger typed form |
| topic profiler | `PlanningDialectic + DecompositionSession` | RESTORED partially |
| node pattern inheritance | lineage-folded `ResearchCard.dimensions` | RESTORED partially |
| expert registry | future `SpecialistCard / TribunalCompositionPolicy` | PLANNED |
| skeptic + advocate always present | permanent tribunal roles | PLANNED |
| dynamic judges by topic | `Dn + discipline + method + question type -> TribunalPanel` | PLANNED |
| local escalation graph | `Gap/Conflict -> Challenge -> subtree -> resolution/reopen` | RESTORED through R2.2 |
| cutter -> OPEN/alarm | fail-closed unresolved challenge / OPEN semantics | PARTIALLY RESTORED |
| domain_map accumulation | KnowledgeGraph + provenance + future RoutingHistory | PARTIALLY RESTORED |
| source search cycles | SearchMemory + future ResearchIteration | PARTIALLY RESTORED |
| old shell pipeline | event/state/runtime-backed peer orchestrator | REPLACED |
| direct backend names in prompts | logical capability routing | INTENTIONALLY NOT PRESERVED |

## 3. What is intentionally not restored literally

The following legacy implementation choices are treated as historical prototypes, not target architecture:

- `/home/orangepi/...` shell orchestration;
- file-to-file BRICKS as authoritative state;
- direct provider/backend knowledge in agent prompts;
- tribunal verdict overriding state directly;
- confidence thresholds interpreted as truth without provenance;
- reconstructing the topology independently on every run;
- a second parallel store for planning/knowledge when the shared UoW/event substrate already exists.

## 4. Important legacy idea to preserve in later Tribunal work

The archive is explicit that specialist composition depends on the path/node in the topic tree. Current architecture should preserve this as:

`ResearchCard lineage -> domain/method/question profile -> TribunalCompositionPolicy -> panel`.

A tribunal role should therefore be traceable to the branch that caused its inclusion.

## 5. Important legacy idea to preserve in search work

Search is not a one-shot lookup. Legacy documents already model:

`query -> candidate source -> relevance/uncertainty check -> accept/reject -> next query`.

Current implementation should express this with typed `ResearchIteration`, `SearchMemory`, `EvidenceSpan` and `ResearchChallenge`, rather than returning only the final list of sources.

## 6. Relation to current R2.3 direction

Legacy local escalation and the OPEN cutter support the current decision to model degradation/reopen explicitly:

`source/evidence change -> dependency impact -> stale resolution -> reopened challenge -> next iteration`.

The new system is stricter because the historical branch, previous resolution and provenance remain replayable rather than being overwritten by a new verdict.
