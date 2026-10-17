# TD-реестр проекта p2-adapter-opencode-v2

Канонический реестр: `config/tech_debt.json`. Здесь — подмножество проекта.

| ID | Title | Severity | Status | Sunset | Notes |
|---|---|---|---|---|---|
| TD-R1-P2-ADAPTER-01 | P2 adapter via OpenCode 2.0.29 native transport (R1) | high | open | after R2 host canary accepted and real P2 route verified | worker PASSED; gates PENDING; host_calls=0 |
| TD-DEV-57 | Роли диспатчатся неканонически (scope-контекст, НЕ scope R1) | high | open | after dispatch fix verified | см. docs/BLOCKERS-2026-10-17.md |
| TD-DEV-60 | Глобальные зеркала агентов hidden:true (БЛОКЕР-A) | high | open | after sync_to_live + restart | см. docs/BLOCKERS-2026-10-17.md |
| TD-DEV-58 | gen_runners.write сломан (reg.records) (БЛОКЕР-B) | high | open | — | — |
| TD-DEV-61 | glossary-maintainer без primary-обёртки (БЛОКЕР-C) | medium | open | decision by owner | — |