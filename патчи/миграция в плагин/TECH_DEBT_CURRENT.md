# Tech Debt — Current Reconciled View

Дата: 2026-09-14.

Этот документ является представлением полного реестра `config/tech_debt_current.json`.

Категории:
- ACTIVE: 35
- RECONCILE_REQUIRED: 8
- DEVELOPMENT: 7
- CLOSED_REPORTED: 15
- TOTAL: 65

`CLOSED_REPORTED` означает исторически сообщённое закрытие, а не новую повторную проверку.

## Active

| ID | source status / severity | owner | problem | acceptance |
|---|---|---|---|---|
| TD-001 | open / high | code-orchestrator | Хардкод Linux путей | env-driven paths and smoke pass |
| TD-009 | open / critical | code-orchestrator | Runtime core live integration pending | live OpenCode uses module-owned runtime or synced copy |
| TD-010 | open / high | code-orchestrator | Policy layer not yet at machine-readable parity | all core policy files exist and are wired as source of truth |
| TD-011 | open / high | code-orchestrator | Router contract duplication | plugin loads registry or has validation against registry |
| TD-013 | open / high | code-orchestrator | Guard degradation matrix not formalized | strictness profiles define allowed guard modes |
| TD-016 | open / medium | researcher-orchestrator | Duplicate root resercher-core copy shadows canonical scripts/researcher/researcher_core | zero runtime/doc references to duplicate root copy, archive inventory recorded, canonical imports unchanged |
| TD-017 | open / high | researcher-orchestrator | evidence.verify capability provider priority overlaps code-factory provider | evidence.verify resolves to research evidence capability for academic-research stages and routing tests prove no code-factory shadowing |
| TD-020 | open / low | researcher-orchestrator | Researcher full suite emits SQLite ResourceWarnings for unclosed connections | full Researcher regression runs without sqlite ResourceWarning and without changing state semantics |
| TD-021 | open / medium | researcher-orchestrator | Writer SourceCatalog and Researcher Source use different identity domains | shared canonical Source identity or durable deterministic binding registry removes per-call manual SourceIdentityBinding while preserving version reconciliation |
| TD-022 | open / medium | researcher-orchestrator | GraphEdge lifecycle lacks dedicated durable latest-state/history query adapter | canonical SQLite relation repository/projector persists EDGE_STATE_CHANGED history and queries latest relation state/revision without replaying unrelated entities |
| TD-023 | open / medium | researcher-orchestrator | Researcher restore/recovery lacks single automated acceptance verifier | one restore command verifies .git, expected tree/boundary hashes and ordered patch lineage before development resumes |
| TD-024 | open / medium | researcher-orchestrator | Peer delegation lacks live Coder/Writer transport and durable dispatch outbox | typed DelegationRequest is durably dispatched to live peer orchestrator and reconciled through child job result without test fixture injection |
| TD-026 | open / medium | researcher-orchestrator | Legacy local-document capsule source/hash contract conflicts with admission validators | capsule and validator share explicit source_type vocabulary and hash wire format with migration tests and no silent evidence rewriting |
| TD-027 | open / medium | researcher-orchestrator | R3.2 identity map depends on R0 accepted-ID ordering | registry admission returns/persists proposal-temp to canonical-ID mapping so R3.2 does not depend on accepted_ids ordering |
| TD-028 | open / medium | researcher-orchestrator | Cross-admission semantic linking has no explicit endpoint authorization contract | typed external endpoint binding authorizes run/scope/revision-checked linking from new outputs to existing canonical entities with provenance tests |
| TD-032 | open / medium | researcher-orchestrator | Relation assessment lacks specialized derivation/measurement validators and automatic signal adapters | DERIVED_FROM and QUANTIFIES use typed reproducibility/assumption/measurement validators; assessment signals come from explicit validated artifacts rather than hand-built fixture fields |
| TD-033 | open / medium | researcher-orchestrator | R3.5 uncertainty field lacks complete automatic axis adapters | typed canonical adapters populate source provenance, freshness, causality, assumption and extrapolation axes; Gap taxonomy is closed/typed and absent axes are not silently resolved |
| TD-034 | open / medium | researcher-orchestrator | Numeric uncertainty is not canonical Quantity state | versioned measurement uncertainty contract stores interval/distribution/coverage/conditions canonically and R3.5 consumes it without projection-only fixture input |
| TD-035 | open / medium | researcher-orchestrator | AssessmentNeed has no canonical durable identity | canonical/versioned AssessmentNeed identity removes the R4 content-addressed bridge while preserving migration/replay compatibility |
| TD-037 | partial / medium | researcher-orchestrator | Tribunal live capability execution lacks provider-health binding | one actual production-provider bounded role E2E with RPB/TEX/PER trace plus one live conditional Advocate path; runtime failures remain separate from semantic OPEN |
| TD-038 | open / high | researcher-orchestrator | No universal cross-layer traceability/lineage substrate | typed non-authoritative traceability links support consumed/produced refs and revisions, transformation/policy/attempt lineage, aliases, replay/invalidation queries, and one E2E source-to-inquiry trace without owning semantic truth |
| TD-039 | open / medium | researcher-orchestrator | FRESH_CONTEXT has structural but not semantic provenance blindness | separate reversible blind-evidence projection handles provenance-bearing text with fidelity tests and staged reveal while canonical EvidenceSpan text remains unchanged |
| TD-042 | open / medium | researcher-orchestrator | Interaction-specific dialectic issue proposals need live calibration | bounded live observer plus benchmark traces and calibration tests for answer evasion/contradiction/capability gap; labels remain non-authoritative proposals |
| TD-044 | open / medium | researcher-orchestrator | Dialectic issue semantic identity is text-sensitive at L1 | typed issue facet/equivalence identity with paraphrase/distinct-facet replay/no-progress tests plus bounded Researcher-Writer claim/facet decomposition round-trip where Writer proposals are scope-checked and non-authoritative |
| TD-053 | open / high | UNASSIGNED | Provider readiness semantics | Разделить adapter presence, bridge, runtime, auth, health, semantic smoke и certification; использовать readiness при provider selection. |
| TD-054 | open / medium | UNASSIGNED | OpenCode transport matrix | Версионируемая matrix Native Plugin / Server / CLI / deterministic process с явными fallback правилами. |
| TD-056 | partial / medium | UNASSIGNED | Legacy OpenCode router plugin retirement | После сертифицированных native релизов убрать legacy hook из runtime/install path; сохранить migration/rollback. |
| TD-057 | partial / high | UNASSIGNED | OpenCode plugin API/runtime compatibility | Live Desktop install: tool visibility, host context, handshake, health/cancel, session API, semantic smoke. |
| TD-058 | open / high | UNASSIGNED | Semantic worker recursion isolation | Read-only worker не вызывает harness_* и не имеет mutating tools; negative E2E fail-closed. |
| TD-059 | open / medium | UNASSIGNED | Structured-output portability | Per-host/model certification, auto/strict/off, mandatory Core revalidation, no silent fallback. |
| TD-060 | partial / medium | UNASSIGNED | Historical host-integration shell | Production paths не зависят от legacy registration scripts/direct opencode run; Native Plugin installer/doctor canonical. |
| TD-061 | partial / medium | UNASSIGNED | OpenCode session DB coupling | Correctness paths работают без private OpenCode DB; scanner optional diagnostics only. |
| TD-062 | open / high | UNASSIGNED | Semantic transport duplication | One SemanticExecutionRequest/Result transport: Tribunal first, then Writer/Coder; CLI explicit legacy only. |
| TD-064 | open / high | UNASSIGNED | Host readiness overclaim | Launcher/config presence not equal provider availability; readiness checked before selection. |
| TD-065 | open / medium | UNASSIGNED | Agent/skill discovery dependency | Internal roles defined by Harness contracts; OpenCode agent/skill autodiscovery optional UX layer. |

## Reconcile required

Эти записи обнаружены в историческом MD, но отсутствуют в текущем прочитанном JSON-реестре. Отсутствие в новом файле не означает закрытия.

| ID | source status / severity | owner | problem | reconciliation acceptance |
|---|---|---|---|---|
| TD-002 | historical_open / high | profile_config | Legacy plugin hook не зарегистрирован в runtime | Подтвердить замещение native plugin; deprecated hook не регистрировать ради формального закрытия. |
| TD-003 | historical_open / medium | code-orchestrator | Дублирование route данных JSON vs TS | Свести к единому реестру или автоматической проверке соответствия; сохранить lineage. |
| TD-004 | historical_open / high | profile_config | Guard env / OPENCODE_SESSION_DB coupling | Пересмотреть требование: OpenCode DB не должен быть correctness dependency; связать с TD-061. |
| TD-005 | historical_open / medium | code-tester | Source-fetcher fallback не покрыт тестом | Найти реализацию и выполнить положительный/отрицательный fallback test. |
| TD-006 | historical_open / low | code-orchestrator | Исторически отсутствовал config/tech_debt.json | Проверить exact current release tree; отдельный экспорт JSON недостаточен. |
| TD-007 | historical_open / medium | code-orchestrator | Нет единого индекса актуальной документации | Единый current-doc index + проверка ссылок/manifest. |
| TD-008 | historical_open / medium | code-orchestrator | WP-0 contracts не сгенерированы как JSON Schema | Сопоставить исходные контракты с действующими схемами и runtime validation. |
| TD-014 | historical_open / low | code-orchestrator | MANIFEST inventory исторически устаревал | Сгенерировать inventory по точному release tree и проверить его. |

## Development view

Эти TD остаются `open`, но показываются как архитектурное развитие, а не как ближайший integration blocker.

| ID | status / severity | owner | direction | acceptance |
|---|---|---|---|---|
| TD-036 | open / medium | researcher-orchestrator | Domain Tribunal role packs are static policy, not admitted modular packs | typed versioned role-pack admission validates equivalence, compatibility and authority without widening central tool/evidence permissions |
| TD-041 | open / medium | researcher-orchestrator | Portable RoleCard / RoleReference / RoleParameterGraph interchange is not implemented | versioned PortableRoleDOM schema, graph vocabulary, round-trip role validation, import/export and authority-stripping tests; no automatic role admission |
| TD-046 | open / high | researcher-orchestrator | Response ownership and Defender/Advocate arbitration are not modeled above a single DQC | typed ResponseAssignment with facet/position ownership, response mode, deterministic responder policy, no implicit self-dialogue/generic fallback, and provider binding only after semantic responder assignment |
| TD-047 | open / high | researcher-orchestrator | Multidisciplinary Claim review has no typed fork/join case model | E2E one Claim with >=3 facets/role families, independent histories, dependencies/conflicts/blocking facet, preserved root Claim identity, non-voting join projection and reducer-only output |
| TD-048 | open / high | UNASSIGNED | Canonical HypothesisCase / revision / verification lifecycle is not implemented | Virtual E2E retain/qualify/revise/split/reject/open, competing/discriminating hypotheses, exact research-resume lineage, stale-source reopening and no scalar-confidence authority. |
| TD-049 | open / high | UNASSIGNED | Evidence support does not model independence/dependency groups | Fixtures distinguish repeated-source cascades from independent replication and preserve independent support during invalidation. |
| TD-050 | open / medium | UNASSIGNED | Hypothesis-specific EvidenceDigest/support-limit-counter projection is not first-class | Exact-locator digest round-trip, caveat/scope preservation and misleading-summary negative tests. |

## Closed archive

Подробности вынесены в `archive/CLOSED_TECH_DEBT.md`.
