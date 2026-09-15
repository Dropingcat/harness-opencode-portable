# Tech Debt Archive — Legacy and Closed Records

Дата консолидации: 2026-09-15.
Реестр: `config/tech_debt.json` (version 2, канонический, 65 записей).
Этот документ фиксирует историю замещения и закрытые записи; он не переоткрывает долги.

## 1. Замещение legacy r0-реестра

`config/tech_debt.json` (version 1) содержал 6 записей раннего поколения:

| ID | title | status in v1 | судьба |
|---|---|---|---|
| TD-001 | Хардкод Linux путей | open | перенесён в канонический реестр v2 (open) |
| TD-009 | Runtime core live integration pending | open | перенесён в v2 (open) |
| TD-010 | Policy layer not yet at machine-readable parity | open | перенесён в v2 (open) |
| TD-011 | Router contract duplication | open | перенесён в v2 (open) |
| TD-012 | Memory policy lacks schema/storage contract | done | перенесён в v2 (closed, CLOSED_REPORTED) |
| TD-013 | Guard degradation matrix not formalized | open | перенесён в v2 (open) |

Источник канона v2: `патчи/миграция в плагин/tech_debt_current.json` (65 записей, 2026-09-14).
Прочие архивные представления: `патчи/миграция в плагин/TECH_DEBT_CURRENT.md`, `CLOSED_TECH_DEBT.md` — исторические, не primary.

## 2. Закрытые записи (CLOSED_REPORTED, из канона)

Закрытие — по сохранённому каноническому evidence, не новая повторная проверка.

| ID | title | закрытие |
|---|---|---|
| TD-012 | Memory policy lacks schema/storage contract | schema/storage контракт памяти: lesson schema, evidence refs, memory_bridge |
| TD-015 | Researcher baseline Guard/LocalCorpus failures | Guard fallback WEAK_RU + STRONG_EN fail-closed; restored fixture; 588/588 PASS |
| TD-018 | R2.3 dependency records explicit | KnowledgeDependency из provenance |
| TD-019 | SourceCatalog semantic changes not wired | Writer SourceCatalog → Researcher invalidation |
| TD-025 | Execution output admission boundary | admission результатов; task success != epistemic success |
| TD-029 | Assessed relation gate not mandatory | обязательная relation assessment в strict reasoning path |
| TD-030 | Relation lifecycle update lacks canonical path | каноническое применение GraphEdge revision |
| TD-031 | Blocked relation assessment no ResearchChallenge | typed Gap/ResearchChallenge при blocked assessment |
| TD-040 | Researcher test invocation manual bootstrap | repository-owned Researcher acceptance runner |
| TD-043 | Generic dialectic disclosure not canonical | общая DDC модель для всех фаз роли |
| TD-045 | DialecticHistory not branch-scoped | branch-scoped DialecticHistory (R4.4 L2b) |
| TD-051 | Code-factory implicit CWD Git snapshot | запрет implicit CWD; explicit workspace authority |
| TD-052 | Coder acceptance assumed Git-backed checkout | независимо от наличия .git в distribution |
| TD-055 | Versioned bidirectional bridge protocol | hostless P1 full-duplex bridge |
| TD-063 | Workspace identity normalization | HostContext/WorkspaceRef boundary P1 |

## 3. Правило

- При регрессии закрытие не переписывается; добавляется reopening event.
- Расширение требований — новая связанная запись.
- Для записей без commit/log/date неполнота evidence остаётся видимой (status_detail).