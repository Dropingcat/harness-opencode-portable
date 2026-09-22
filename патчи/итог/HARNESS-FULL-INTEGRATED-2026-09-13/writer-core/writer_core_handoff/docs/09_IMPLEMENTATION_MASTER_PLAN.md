# 09. Implementation Master Plan v0.3

## Principle

Build semantics/invariants before corpus intelligence. Each phase has a gate. Agents may parallelize only after shared schemas are frozen.

## P0 Contract freeze
Schemas, IDs, reason codes, authority/mutability, event envelope, migration ADR. Gate: all YAML/schema fixtures validate.

## P1 Core bounded contexts
Document Tree, Writing Decomposition, Discourse, Argument Instance, Artifact/Symbol, Policy, Dependency, Execution entities. Gate: CRUD/referential/snapshot/diff tests.

## P2 Researcher bridge + semantic types
Lossless epistemic projection and ClaimWritingContract; semantic type checker. Gate: no writer strength upgrade; fixtures map scopes/evidence/statuses losslessly.

## P3 One-paragraph planner
Objective→ArgumentNeed→DiscourseNeed→Claim/Artifact slots. Gate: deterministic plan without prose.

## P4 Structured realization IR
Inline AST, typed references, renderer. Gate: changing quantity/citation/term does not require LLM rewrite.

## P5 RTT v1 + repair
Back-extraction, alignment, typed semantic diff, bounded repair. Gate: RTT benchmark hard mutations meet thresholds. **M1: Academic Paragraph Compiler**.

## P6 Dependency build engine + Blockers
Impact closure, freshness states, ready/blocked/rebuild queues. Gate: exact affected-set fixtures. **M2 foundation**.

## P7 Global terminology/symbol/consistency
Term/Symbol/Abbreviation registries, global claim/quantity checks. Gate: deliberate drift fixtures caught.

## P8 Quantitative/uncertainty/formula engine
Units, dimensions, raw/computed/reported values, uncertainty, formulas and implementation checks. Gate: numerical mutation suite.

## P9 Data/computation/artifact lineage
Datasets, scripts, tables, figures, captions, crossrefs. Gate: raw-data revision selectively rebuilds correct artifacts and revalidates dependent claims. **M3**.

## P10 Section interfaces + macro composition
Section contracts, visibility, compression/expansion, abstract/conclusion integrity. Gate: macro RTT and missing-interface tests.

## P11 Novelty/contribution/prior-art
NoveltyGraph, ContributionGraph, LiteratureCoverageSnapshot. Gate: unsupported novelty is blocking.

## P12 Review/decision/branch-merge/freeze
ReviewIssue, ReviewConflict, Decision, semantic merge, authority/freeze. Gate: conflicting reviewer/branch scenarios handled without silent overwrite.

## P13 Policy/compliance profiles
Genre/domain/risk/institution/journal/numeric/citation/review precedence. Gate: conflict resolution deterministic and versioned.

## P14 Release/export QA
BuildManifest, Pandoc/CSL, parse-back, visual preflight, format equivalence. Gate: catastrophic export fixtures. **M4: reproducible document release**.

## P15 Corpus admission & pattern learning
Dedup, quality/use labels, motif→candidate pattern→shadow→promotion. Gate: no lexical/factual leakage into target truth.

## P16 Advanced comparison
Only measured tasks: graph/structural/style vectors, never universal quality scalar.

## P17 Forensics foundation
Fingerprint feature extraction, confounder graph, work lineage. Read-only analytics.

## P18 Open-world authorship verification
Calibration/OOD, trajectory/regime analysis. Gate: cross-topic/time/template evaluation and inconclusive behavior.

## P19 Production orchestration
Critical-path scheduling, document debt, observability, migrations, recovery.

## P20 Catastrophic scenario certification
All scenarios in `docs/24_CATASTROPHIC_SCENARIOS.md` must pass end-to-end before production declaration.

## Parallel tracks after P1

- A Researcher bridge/semantic types
- B Artifact/symbol groundwork
- C Policy/template registry
- D Event store/CLI

Hard dependency: RTT waits for semantic bind + structured realization. Release waits for quantitative/artifact/review systems. Forensics never blocks M1–M4 implementation.

## v0.3 implementation extension

After the paragraph compiler foundation, implementation proceeds through P21–P27 from `agent_master_plan.yaml`: adaptive affordance control, linguistic IR, weak-model language tools, Tier-2 escalation, linguistic RTT/rhetoric, Linguistic Auditor learning, and the forensics bridge.

A critical acceptance test is comparative: the designated weak model with LinguisticDigest/tooling MUST outperform the same model with raw prompting on semantic-preservation fixtures at acceptable cost. If it does not, the linguistic tooling is complexity without leverage and must be redesigned.

