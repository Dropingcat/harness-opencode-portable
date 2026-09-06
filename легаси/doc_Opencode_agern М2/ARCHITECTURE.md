# Архитектура единого harness

## Целевая схема

```text
User
  ↓
Code/Research Orchestrator
  ↓
Task Classifier
  ↓
Context Filter / Scope Builder
  ↓
Contract Builder
  ↓
Specialist Delegate Layer
  ├─ coder-worker / fixer
  ├─ source-fetcher / librarian
  ├─ reviewer / oracle
  ├─ tester
  ├─ auditor / OpenWorkers-style trust gate
  └─ experimenter / autoresearch
  ↓
Verification + Safety Gate
  ├─ factory_ctl state machine
  ├─ doc_guard pre-resume / untrusted-output scan
  ├─ schema validators
  ├─ tests/build checks
  └─ evidence gate: no evidence → unsupported
  ↓
Report + Memory + Tracker
```

## Источники паттернов

- текущий `code-orchestrator`: фабрика worker/reviewer/tester/auditor;
- `oh-my-opencode-slim`: роли Orchestrator/Explorer/Oracle/Council/Librarian/Designer/Fixer, background delegation, tool routing;
- OpenWorkers: planner → deterministic researcher → checker + trust gate → critic;
- `doc_guard`: provenance-aware prompt-injection guard для `opencode.db`;
- `агент кодер`: contract-first, sandbox, verifier, critic, process auditor;
- `Z:\server\.hermes\mcp`: hardcoded launchers для разных классов задач.

## Роли

| Роль harness | Аналог OMO | Текущий агент | Назначение |
|---|---|---|---|
| Orchestrator | Orchestrator | code-orchestrator / research-orchestrator | классификация, декомпозиция, маршрутизация |
| Explorer | Explorer | explore / source-fetcher | разведка codebase, grep/glob, codemap |
| Librarian | Librarian | source-fetcher / researcher | внешние источники, docs, papers |
| Fixer | Fixer | coder-worker | bounded implementation |
| Oracle | Oracle | code-reviewer / code-auditor | архитектура, сложный debugging, review |
| Council | Council | tribunal-judge | multi-perspective conflict resolution |
| Observer | Observer | read/image/pdf flows | визуальные/PDF артефакты |

## Stop criteria

Stop criteria не решаются моделью. Их ведёт код:

1. `APPROVE/PASS` → done;
2. `requires_user=True` → blocked;
3. `auditor_block=True` → blocked;
4. `iteration_limit` → blocked;
5. guard `FAIL` → blocked until user decision.
