# Architecture Decisions v0.2

- ADR-001: Document containment and epistemics are separate bounded contexts.
- ADR-002: Argument graph is separate from Researcher epistemic graph; argument roles are contextual.
- ADR-003: Git/YAML stores static program/config; SQLite + append-only event log stores runtime authoritative Writer state.
- ADR-004: Researcher owns epistemic truth; Writer gets immutable projection/version references.
- ADR-005: RTT is a mandatory semantic commit gate and independently benchmarked.
- ADR-006: dependency freshness is orthogonal to validity (`STALE != INVALID`).
- ADR-007: quantities/uncertainty/formulas/data/figures/tables are typed executable artifacts.
- ADR-008: first-class Blocker and state-driven orchestrator replace vague agent progress.
- ADR-009: section interfaces and claim visibility govern macro composition/compression.
- ADR-010: novelty/contribution are explicit graphs tied to prior-art coverage snapshots.
- ADR-011: review conflicts and branch merges require semantic resolution + validation.
- ADR-012: release is a reproducible build with parse-back and visual QA.
- ADR-013: corpus pattern learning starts only after M1–M4 gates.
- ADR-014: Forensics/OSINT is read-only analytical projection with open-world/inconclusive outcomes.
- ADR-015: catastrophic scenario suite is required for production declaration.
