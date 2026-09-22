# Harness — Current Documentation Release

**Дата:** 2026-09-14  
**Статус документации:** `CURRENT / RECONCILED / LIVE_PLUGIN_CERTIFICATION_PENDING`

Этот архив является текущим входным комплектом для продолжения разработки Harness. Он отделяет подтверждённое состояние интегрированного Harness, hostless Native Plugin P1, ещё не сертифицированную live-интеграцию OpenCode и дальнейшие архитектурные направления.

## Читайте в таком порядке

1. `PROJECT_STATE.md` — какой baseline сейчас считается текущим и какие уровни доказательств существуют.
2. `CURRENT_ARCHITECTURE.md` — Writer/Researcher/Coder/shared runtime и границы полномочий.
3. `OPENCODE_NATIVE_PLUGIN_CURRENT.md` — состояние Native Plugin и что ещё не доказано.
4. `HARNESS_OPENCODE_INTERFACE_CONTROL.md` — стабильная граница Core ↔ plugin.
5. `TEST_AND_EVIDENCE_MATRIX.md` — какие утверждения чем подтверждены.
6. `IMPLEMENTATION_TRACKER_CURRENT.md` — текущие workstreams.
7. `TECH_DEBT_CURRENT.md` и `config/tech_debt_current.json`.
8. `DEVELOPMENT_TRACKER.md` и `NEXT_PHASE_PLAN.md`.
9. `NEXT_SESSION_HANDOFF.md` — короткий handoff для продолжения разработки.

## Три baseline, которые нельзя смешивать

- **Integrated Harness FINAL 2026-09-13**: Writer + Researcher + Coder + shared runtime, deterministic acceptance подтверждён.
- **Windows deployment 2026-09-14**: тот же code-only release развернут и прошёл deterministic acceptance.
- **Native Plugin P1**: по актуализированной документации реализован hostless bridge/tool boundary, но live Desktop certification ещё не выполнена.

Название `COMPLETE`, `FINAL` или `P1` само по себе не повышает уровень доказательства.

## Главный следующий gate

Не новая предметная архитектура, а:

`Native Desktop P2 -> live plugin load -> tools visible -> HostContext -> handshake -> health/cancel -> read-only semantic smoke`.

До его прохождения `semantic.execute` нельзя считать production-ready.

## Канонические машинные файлы

- `config/project_state.json`
- `config/tech_debt_current.json`
- `config/decision_aliases.json`
- `MANIFEST.json`
- `SHA256SUMS.txt`

Исторические и исходные материалы лежат в `references/` и не являются текущим source of truth.
