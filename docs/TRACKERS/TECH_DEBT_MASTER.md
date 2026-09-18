# Tech Debt Master — единый реестр проекта

Дата: 2026-09-18
Всего: 99 | open: 79 | closed: 20

Префиксы: CD-* Coder, WR-* Writer, RS-* Researcher, PL-* plugin, TD-* общий.

## Активные (open)

| ID | Sevr | Owner | Title | Source/Created |
|---|---|---|---|---|
| CD-004 | medium | coder-worker:factory | Pre-commit hook: проверка coder_dom в sync + stub-детекция на коммит | - |
| TD-001 | high | code-orchestrator | Хардкод Linux путей | - |
| TD-002 | high | profile_config | Legacy plugin hook не зарегистрирован в runtime | - |
| TD-003 | medium | code-orchestrator | Дублирование route данных JSON vs TS | - |
| TD-004 | high | profile_config | Guard env / OPENCODE_SESSION_DB coupling | - |
| TD-005 | medium | code-tester | Source-fetcher fallback не покрыт тестом | - |
| TD-006 | low | code-orchestrator | Исторически отсутствовал config/tech_debt.json | - |
| TD-007 | medium | code-orchestrator | Нет единого индекса актуальной документации | - |
| TD-008 | medium | code-orchestrator | WP-0 contracts не сгенерированы как JSON Schema | - |
| TD-009 | critical | code-orchestrator | Runtime core live integration pending | - |
| TD-010 | high | code-orchestrator | Policy layer not yet at machine-readable parity | - |
| TD-011 | high | code-orchestrator | Router contract duplication | - |
| TD-013 | high | code-orchestrator | Guard degradation matrix not formalized | - |
| TD-014 | low | code-orchestrator | MANIFEST inventory исторически устаревал | - |
| TD-016 | medium | researcher-orchestrator | Duplicate root resercher-core copy shadows canonical scripts/researche | - |
| TD-017 | high | researcher-orchestrator | evidence.verify capability provider priority overlaps code-factory pro | - |
| TD-020 | low | researcher-orchestrator | Researcher full suite emits SQLite ResourceWarnings for unclosed conne | - |
| TD-021 | medium | researcher-orchestrator | Writer SourceCatalog and Researcher Source use different identity doma | - |
| TD-022 | medium | researcher-orchestrator | GraphEdge lifecycle lacks dedicated durable latest-state/history query | - |
| TD-023 | medium | researcher-orchestrator | Researcher restore/recovery lacks single automated acceptance verifier | - |
| TD-024 | medium | researcher-orchestrator | Peer delegation lacks live Coder/Writer transport and durable dispatch | - |
| TD-026 | medium | researcher-orchestrator | Legacy local-document capsule source/hash contract conflicts with admi | - |
| TD-027 | medium | researcher-orchestrator | R3.2 identity map depends on R0 accepted-ID ordering | - |
| TD-028 | medium | researcher-orchestrator | Cross-admission semantic linking has no explicit endpoint authorizatio | - |
| TD-032 | medium | researcher-orchestrator | Relation assessment lacks specialized derivation/measurement validator | - |
| TD-033 | medium | researcher-orchestrator | R3.5 uncertainty field lacks complete automatic axis adapters | - |
| TD-034 | medium | researcher-orchestrator | Numeric uncertainty is not canonical Quantity state | - |
| TD-035 | medium | researcher-orchestrator | AssessmentNeed has no canonical durable identity | - |
| TD-036 | medium | researcher-orchestrator | Domain Tribunal role packs are static policy, not admitted modular pac | - |
| TD-037 | medium | researcher-orchestrator | Tribunal live capability execution lacks provider-health binding | - |
| TD-038 | high | researcher-orchestrator | No universal cross-layer traceability/lineage substrate | - |
| TD-039 | medium | researcher-orchestrator | FRESH_CONTEXT has structural but not semantic provenance blindness | - |
| TD-041 | medium | researcher-orchestrator | Portable RoleCard / RoleReference / RoleParameterGraph interchange is  | - |
| TD-042 | medium | researcher-orchestrator | Interaction-specific dialectic issue proposals need live calibration | - |
| TD-044 | medium | researcher-orchestrator | Dialectic issue semantic identity is text-sensitive at L1 | - |
| TD-046 | high | researcher-orchestrator | Response ownership and Defender/Advocate arbitration are not modeled a | - |
| TD-047 | high | researcher-orchestrator | Multidisciplinary Claim review has no typed fork/join case model | - |
| TD-048 | high | UNASSIGNED | Canonical HypothesisCase / revision / verification lifecycle is not im | - |
| TD-049 | high | UNASSIGNED | Evidence support does not model independence/dependency groups | - |
| TD-050 | medium | UNASSIGNED | Hypothesis-specific EvidenceDigest/support-limit-counter projection is | - |
| TD-053 | high | UNASSIGNED | Provider readiness semantics | - |
| TD-054 | medium | UNASSIGNED | OpenCode transport matrix | - |
| TD-056 | medium | UNASSIGNED | Legacy OpenCode router plugin retirement | - |
| TD-057 | high | UNASSIGNED | OpenCode plugin API/runtime compatibility | - |
| TD-058 | high | UNASSIGNED | Semantic worker recursion isolation | - |
| TD-059 | medium | UNASSIGNED | Structured-output portability | - |
| TD-060 | medium | UNASSIGNED | Historical host-integration shell | - |
| TD-061 | medium | UNASSIGNED | OpenCode session DB coupling | - |
| TD-062 | high | UNASSIGNED | Semantic transport duplication | - |
| TD-064 | high | UNASSIGNED | Host readiness overclaim | - |
| TD-065 | medium | UNASSIGNED | Agent/skill discovery dependency | - |
| TD-066 | critical | code-orchestrator | harness_run live-инструмент возвращает no_route_match при рабочем brid | - |
| TD-068 | high | researcher-orchestrator | Writer DOM extractor не извлекает числовые/фактические claims | - |
| TD-069 | high | research-orchestrator | uncertainty_bridge не распознаёт уровень 'assumed' из DOM -> research_ | - |
| TD-070 | high | research-orchestrator | claim_type не типизирован: нет enum ClaimType, CAUSAL_HYPOTHESIS/EXTER | - |
| TD-071 | high | research-orchestrator | Evidence-quality tribunal (Q1A1..Q3A3 поиск и классификация неопределё | - |
| TD-072 | medium | research-orchestrator | DOM-блок утверждения не связывает claim_type с ветвями тематик трибуна | - |
| TD-073 | major | code-orchestrator | project_context.py падает с UnicodeEncodeError на Windows cp1251 (кири | - |
| TD-074 | medium | code-orchestrator | Glossary registry: M1-генератор и M2-M4 сделаны, M5-M6 (синк docs в об | - |
| TD-075 | medium | code-orchestrator | Синхронизация docs между workspace и portable не автоматизирована (руч | - |
| TD-076 | high | coder-orchestrator | Кодеру нужен DOM-аналог для функций кода (как Writer DOM YAML): манифе | - |
| TD-077 | critical | code-orchestrator | Отдельные контракты для code-reviewer и code-tester + инструменты испо | - |
| TD-078 | high | researcher-orchestrator | Интерфейсы vs заглушки: детектор готов (interface=Protocol/ABC, stub=p | - |
| TD-079 | high | research-orchestrator | Вложенная спека HARNESS_SEMANTIC_RESEARCH_METHOD (87 секций) — оформит | - |
| TD-080 | high | writing-orchestrator | plan --topic всегда строит академический каркас (RELEVANCE/METHODS/RES | - |
| TD-081 | medium | writing-orchestrator | Writing Brief не формализован как JSON-контракт (audience/vibe/thesis/ | - |
| TD-082 | medium | writing-orchestrator | session_memory.json не инициализирована/не читается — кросс-сессионные | - |
| TD-083 | high | writing-orchestrator | extract не извлекает citation/reference маркеры из markdown (только pa | - |
| TD-084 | medium | writing-orchestrator | graphs строит только 7 из 13 графов на paragraph-artifact; G1/G2/G7/G8 | - |
| TD-086 | low | writing-orchestrator | L1-ревью считает Mermaid-блоки, таблицы и код «предложениями» (LONG_SE | - |
| TD-089 | medium | code-orchestrator | extract не извлекает markdown-таблицы (meta.table_count=0, tables=[])  | - |
| TD-090 | medium | code-orchestrator | Пассивный скилл кодера: сбор тех долгов и актуализация в едином докуме | - |
| TD-091 | high | code-orchestrator | Воркер-сессии падают на network timeout/DNS (chatgpt.com) без прогресс | - |
| TD-092 | medium | writing-orchestrator | Нет детерминированного пакера 'raw → intermediate → results → DOM + nu | - |
| TD-093 | medium | code-orchestrator | Пер-графовый аудит информативности/шума: ревьюер заметил, что некоторы | - |
| TD-094 | high | code-orchestrator | G8_policy_constraint даёт ложный позитив: сигнал 'policy' матчится на  | - |
| TD-095 | medium | code-orchestrator | G9_revision_dependency дублирует ClaimRef-ноды (по одной на каждую rev | - |
| TD-096 | low | code-orchestrator | G7_citation_provenance строится ClaimRef-only (1 нода) на параграфах Б | - |
| TD-097 | medium | writing-orchestrator | Раздел результатов SEM/EDS Р18 540C: 8 подразделов и их проза в главе  | - |

## Закрытые (closed)

| ID | Title | Закрыт |
|---|---|---|
| CD-003 | verify_claim бросает AttributeError на не-dict входе (contract: должен | 2026-09-18 |
| TD-012 | Memory policy lacks schema/storage contract | - |
| TD-015 | Researcher baseline Guard/LocalCorpus failures remain unresolved | 2026-09-13 |
| TD-018 | R2.3 dependency records are explicit and not yet derived from canonica | - |
| TD-019 | SourceCatalog semantic changes are not yet wired into Researcher R2.3  | - |
| TD-025 | Execution output admission boundary | - |
| TD-029 | Assessed relation gate is not mandatory in all reasoning paths | - |
| TD-030 | Relation lifecycle update lacks one canonical registry/reducer persist | - |
| TD-031 | Blocked relation assessment does not create adaptive ResearchChallenge | - |
| TD-040 | Researcher test invocation requires manual import-path bootstrap | - |
| TD-043 | Generic dialectic disclosure is not canonical across all role phases y | - |
| TD-045 | DialecticHistory is not branch-scoped yet | - |
| TD-051 | Code-factory implicit CWD Git snapshot could mutate Harness repository | 2026-09-13 |
| TD-052 | Coder acceptance assumed a Git-backed Harness checkout | 2026-09-13 |
| TD-055 | Versioned bidirectional bridge protocol | - |
| TD-063 | Workspace identity normalization | - |
| TD-067 | doc_extract_server зависит от неустановленных MCP-doc зависимостей (py | 2026-09-17 |
| TD-085 | register (R3) возвращает verdict PASS при непустых MINOR issues — разм | - |
| TD-087 | dom --qwen-dir даёт duplicate source id / claim id при слиянии plan-cl | - |
| TD-088 | dom --qwen-dir: нумерация claims от qwen непоследовательна (C-9001, C- | - |
