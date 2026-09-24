# Tech Debt Master — единый реестр проекта

Дата: 2026-09-24
Всего: 186 | open: 128 | closed: 58 (счётчики пересчитаны по фактическим строкам реестра; AG-D3/TD-D3 закрыт 2026-09-24: документирование transitional-статуса регистрации плагина + гейт check_plugin_registration_status.py, issue #16; TD-003/TD-D10 закрыт гейтом route-дублирования 2026-09-24; AG-A1 закрыт 2026-09-24: генератор субагентов + регресс-тесты контракта; AG-D2/TD-D2 закрыт 2026-09-24: канонический plugin-aware doctor + health_check-обёртка + гейт check_health_canonical.py, issue #10)

Префиксы: CD-* Coder, WR-* Writer, RS-* Researcher, PL-* plugin, TD-* общий.
Реестр TECH_DEBT_AGENTS.md (TD-A*/TD-D*/TD-I*/TD-T*): закрыто в 2026-09-24 — TD-A4, TD-D4, TD-D7, TD-D9; частично — TD-A3, TD-D5.

## Активные (open)

| ID | Sevr | Owner | Title | Source/Created |
|---|---|---|---|---|
| CD-004 | medium | coder-worker:factory | Pre-commit hook: проверка coder_dom в sync + stub-детекция на коммит | - |
| RS-001 | critical | research-orchestrator | Автореферат v20: исправить завышенную плотность дислокаций ρ в литобзо | - |
| RS-002 | critical | research-orchestrator | Автореферат v20: уточнить формулировку по ВКС-10 (термостабильность 55 | - |
| RS-003 | high | research-orchestrator | Автореферат v20: дополнить состав ВКС-10 (W≈1%, V≈0.1%) и Р6М5 (W≈6%,  | - |
| RS-004 | medium | research-orchestrator | Автореферат v20: вынести числа глубины проникновения рентгеновского из | - |
| RS-006 | high | research-orchestrator | Список литературы НКР: УБРАТЬ ссылку [6] Гусакова (Al-Si сплавы) — не  | - |
| RS-007 | high | research-orchestrator | Список литературы НКР: УБРАТЬ ссылку [13] Bacca (спектральное слияние  | - |
| RS-009 | critical | research-orchestrator | Список литературы НКР: ИСПРАВИТЬ [7] — в тексте 'Энтин [7]', в списке  | - |
| RS-010 | medium | research-orchestrator | Список литературы НКР: ИСПРАВИТЬ [9] — используется для Лахтина, но пр | - |
| RS-011 | critical | research-orchestrator | Список литературы НКР: ДОБАВИТЬ реальные статьи, цитируемые в тексте,  | - |
| RS-012 | high | research-orchestrator | Дерево клаймов: ИСПРАВИТЬ привязку c20-c24 (ВКС-10) — ошибочно привяза | - |
| RS-013 | high | research-orchestrator | Список литературы НКР: ДОБАВИТЬ Trubin & Szasz 1991 (регуляризация XRD | - |
| RS-014 | medium | research-orchestrator | Получить недостающие работы: статьи — sci-bot; монографии/книги — толь | - |
| RS-015 | high | research-orchestrator | Sci-bot: баланс аккаунта = 0 (ниже floor 300000) — требуется пополнени | - |
| RS-016 | medium | research-orchestrator | Найти sci-bot skill на Linux-машине orangepi (клиент лежал в /home/ora | - |
| RS-017 | medium | research-orchestrator | Направление «лазер-индуцированные деформации»: добавлены статьи в клай | - |
| RS-018 | medium | research-orchestrator | Направление «легирование»: Zhang 2014 (alloyed ε-(Fe1-xMx)3N) + Yang&S | - |
| RS-019 | medium | research-orchestrator | Направление «напряжения/микродеформации в γ′-Fe4N»: Somers&Mittemeijer | - |
| RS-020 | medium | research-orchestrator | Направление «избыточный азот»: Hekker 1985 (Fe-Cr) + Jung&Meka 2011 (F | - |
| RS-021 | medium | research-orchestrator | Направление «термомеханическая обработка»: поиск по ТМО+азотирование д | - |
| RS-022 | medium | research-orchestrator | Рекурсивное раскручивание дерева: собраны 39 DOI из списков литературы | - |
| RS-023 | medium | research-orchestrator | Глубокий рекурсивный шаг: найдены классики диффузии N из списка Leinew | - |
| RS-024 | critical | research-orchestrator | ГЛОБАЛЬНЫЙ ДОЛГ RESEARCHER: формализация отделения мусора от ценных ст | - |
| RS-025 | high | research-orchestrator | Поисковый контракт: ОБЯЗАТЕЛЬНО сначала шерстить локальную БД (ChromaD | - |
| RS-026 | critical | research-orchestrator | АВТОМАТИЗАЦИЯ КЛАСТЕРНОГО МЕТОДА ИЗУЧЕНИЯ ЛИТЕРАТУРЫ (cluster → Q&A →  | - |
| TD-001 | high | code-orchestrator | Хардкод Linux путей | - |
| TD-002 | high | profile_config | Legacy plugin hook не зарегистрирован в runtime | - |
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
| TD-098 | high | research-orchestrator | Двойственность research-orchestrator: блок верификации текста не адапт | - |
| TD-099 | high | code-orchestrator | Мост между оркестраторами (cross-orchestrator dispatch): code-orchestr | - |
| TD-101 | high | claim-parser | claim-parser: контракт требует записать файл claims_parsed.json, но у  | - |
| TD-102 | high | research-orchestrator | Детерминированная генерация claims_parsed.json даёт воду и плохо режет | - |
| TD-103 | high | research-orchestrator | Нет переиспользуемой библиотеки research-модулей (sci-hub качальщик, п | - |
| TD-105 | medium | research-orchestrator | Кросс-сессионное засорение временной папки C:\Temp\opencode: файл h2.p | - |
| TD-106 | high | research-orchestrator | Нет авто-валидации внешних данных в пайплайне: sci-bot выдал фейк-DOI  | - |
| TD-109 | critical | code-orchestrator | Нет исполнения бандла: harness_run возвращает route/bundle/skills/tool | - |
| TD-111 | medium | code-orchestrator | semantic_execute отключён по умолчанию (HARNESS_SEMANTIC_ENABLED!=1),  | - |
| TD-112 | high | code-orchestrator | Маппинг путей (path_resolution_map.json / runtime_integration_policy.j | - |
| TD-116 | high | research-orchestrator | BRICKS-скрипты перенесены с сервера в рабочий harness, но требуют закр | - |
| TD-117 | high | code-orchestrator | opencode run --agent НЕ вызывает субагентов: закрыт детерминированный слой (gen_runners.py + гейт инвариантов); live-прогон CLI — за хост-runtimes | 2026-09-24 |
| TD-120 | medium | research-orchestrator | run_research.py: фактор времени агентов не учтён в budget — PER_CALL_E | - |
| TD-126 | high | research-orchestrator | Цикл перфекционизма агента: «я ещё недостаточно хорошо реализовал код/ | - |
| TD-129 | critical | research-orchestrator | КЛАСТЕР CL-16: Предварительная лазерная обработка → градиентные поля д | - |
| TD-130 | high | researcher-orchestrator | Режим «сыщика» для researcher: раскрутка клубка зависимостей (citation | - |
| TD-131 | high | researcher-orchestrator | Аналитика склонированных OSINT/детективных репозиториев: СНАЧАЛА тести | - |
| TD-132 | critical | research-orchestrator | ИНТЕГРАЦИЯ СОВРЕМЕННЫХ ПАРАДИГМ В ЛИТОБЗОР (S-фаза, анизотропия XRD, t | - |
| TD-133 | high | research-orchestrator | c18: исследовать возможности line profile analysis для корректного опр | - |
| TD-134 | high | research-orchestrator | c22: проработать ОБОСНОВАНИЕ выбора температуры и времени азотирования | - |
| TD-135 | high | research-orchestrator | Лазер: подобрать из литературы ОБОСНОВАНИЕ типов обработки, мощности л | - |
| TD-136 | low | research-orchestrator | Папка литературных данных: F:\1\_STRUCTURED\09_LITERATURE\1_Литература | - |
| TD-138 | medium | code-orchestrator | Консолидация реестров техдолгов: канонический реестр = portable; иссле | - |
| TD-139 | medium | code-orchestrator | Экранирование кавычек в PowerShell ломает inline python -c: агенты вын | - |
| TD-141 | medium | code-orchestrator | harness_run (плагин) расходится с core resolve(): core возвращает прав | - |
| TD-149 | high | research-orchestrator | Найти аналог модуля глубокого исследования (как GPT Deep Research / Qw | - |
| TD-150 | high | research-orchestrator | Агент не может прочитать сессию субагента (субагентская ветка opencode | - |
| TD-151 | high | research-orchestrator | Резолвер извлекает только первые 4 страницы (свойства на других страни | - |
| TD-155 | high | research-orchestrator | MCP-tools подключены в .mcp.json (4 сервера), но НЕ инжектированы в те | - |
| TD-158 | high | research-orchestrator | Обход капчи sci-hub: «проверка на робота» (Cloudflare/анти-бот) блокир | - |
| AG-A2 | high | code-orchestrator | [TECH_DEBT_AGENTS] Нет иерархии parent/child сессий (semantic.execute не сертифицирован live) | 2026-09-24 |
| AG-A1 | high | code-orchestrator | [TECH_DEBT_AGENTS] Агенты не зарегистрированы как субагенты OpenCode (генератор .opencode/agent/*.md) | 2026-09-24 |
| AG-A3 | medium | code-orchestrator | [TECH_DEBT_AGENTS] Маппинг роль→агент→model: нет `model:` во frontmatter и `agent_hint` в harness_run (частично: формат агентов готов) | 2026-09-24 |
| AG-A4 | high | code-orchestrator | [TECH_DEBT_AGENTS] ЗАКРЫТО 2026-09-24: обязательный шаг 0 git-ритуала добавлен в agents/code-orchestrator.md | 2026-09-24 |
| AG-D1 | medium | code-orchestrator | [TECH_DEBT_AGENTS] Списки модулей в доке vs фактический состав v1 (writer/kanban/memory/capsules/shared не перенесены) | 2026-09-24 |
| AG-D2 | medium | code-orchestrator | [TECH_DEBT_AGENTS] ЗАКРЫТО 2026-09-24: doctor.py — живой bridge.hello/harness.status probe + protocol compat + host snapshot; health_check.py — обёртка; гейт scripts/tools/check_health_canonical.py + tests/test_health_doctor.py (issue #10) | 2026-09-24 |
| ~~AG-D3~~ | low | code-orchestrator | ЗАКРЫТО 2026-09-24: transitional-статус задокументирован (docstring register_plugin.py + config v3 status/note/canonical_path + docs/ARCHITECTURE_NOTES.md); гейт scripts/tools/check_plugin_registration_status.py (I1-I6) + tests/test_plugin_registration_status.py (8); issue #16 | 2026-09-24 |
| AG-D4 | low | code-orchestrator | [TECH_DEBT_AGENTS] ЗАКРЫТО 2026-09-24: capability hash синхронизирован с runtime_snapshot (df07cc…, 12 роутов) | 2026-09-24 |
| AG-D6 | medium | code-orchestrator | [TECH_DEBT_AGENTS] Launchers на legacy `opencode run`; зафиксировать transport=opencode_cli_legacy | 2026-09-24 |
| AG-D7 | medium | code-orchestrator | [TECH_DEBT_AGENTS] ЗАКРЫТО 2026-09-24: smoke-тесты tests/test_job_ctl.py + host_ref mapping документирован | 2026-09-24 |
| ~~AG-D8~~ | closed | code-orchestrator | [TECH_DEBT_AGENTS] compatibility/1.18.30.json: привести к шкале evidence LIVE_CERTIFIED | 2026-09-24 |
| AG-D9 | low | code-orchestrator | [TECH_DEBT_AGENTS] ЗАКРЫТО 2026-09-24: MANIFEST.json + SHA256SUMS.txt + decision_aliases.json (scripts/tools/gen_manifest.py) | 2026-09-24 |
| AG-D10 | medium | code-orchestrator | [TECH_DEBT_AGENTS] Дублирование route-данных JSON vs TS: нет validation snapshot↔schemas | 2026-09-24 |
| TD-200 | low | qwen-coder | Тестирование работы git qwen-coder'ом: загрузка в репо (push) и коммиты — проверка токена/веток/кредов в изолированном репо | 2026-09-24 |

## Закрытые (closed)

| ID | Title | Закрыт |
|---|---|---|
| AG-A2 | ЗАКРЫТО 2026-09-24: semantic.execute parent/child E2E-сертификация — tests/test_bridge_semantic_execute.py (4 теста: handshake контрактов, roundtrip request→child-result со schema-валидацией, error propagation) | 2026-09-24 |
| AG-D5 | ЗАКРЫТО 2026-09-24: cancel/timeout E2E-сертификация — tests/test_bridge_cancel_timeout.py (5 тестов: TIMED_OUT по timeout_ms запроса с восстановлением сервера, harness.cancel{execution_id} кооперативная отмена in-flight, идемпотентность/NOT_PENDING, отсутствие resurrection поздним ответом); bridge_peer: handlers в worker-потоках (cancel доставляем во время blocking execute), pending-drop после timeout/cancel; протокол harness-bridge-rpc/1.0 и схемы без изменений | 2026-09-24 |
| AG-D8 | ЗАКРЫТО 2026-09-24: compatibility/1.18.30.json schema 2.0 — feature_probes {level, evidence} по шкале LIVE_CERTIFIED/HOSTLESS_REPORTED/TYPE_VERIFIED/NOT_CERTIFIED; гейт scripts/tools/check_evidence_levels.py + tests/test_evidence_levels.py (11); issue #14 | 2026-09-24 |
| CD-003 | verify_claim бросает AttributeError на не-dict входе (contract: должен | 2026-09-18 |
| RS-005 | СПРАВКА: ссылка [3] Березина = АЗОТИРОВАНИЕ КОБАЛЬТСОДЕРЖАЩИХ СТАЛЕЙ ( | - |
| RS-008 | Список литературы НКР: ИСПРАВИТЬ [4] — в тексте 'Гуляев [4]', в списке | - |
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
| TD-066 | harness_run live-инструмент возвращает no_route_match при рабочем brid | - |
| TD-067 | doc_extract_server зависит от неустановленных MCP-doc зависимостей (py | 2026-09-17 |
| TD-083 | extract не извлекает citation/reference маркеры из markdown (только pa | - |
| TD-084 | graphs строит только 7 из 13 графов на paragraph-artifact; G1/G2/G7/G8 | - |
| TD-085 | register (R3) возвращает verdict PASS при непустых MINOR issues — разм | - |
| TD-087 | dom --qwen-dir даёт duplicate source id / claim id при слиянии plan-cl | - |
| TD-088 | dom --qwen-dir: нумерация claims от qwen непоследовательна (C-9001, C- | - |
| TD-100 | RESEARCH_RUNNER_SH — старый легаси-переменная в окружении research-orc | - |
| TD-104 | ChromaDB-инфраструктура семпоиска хрупкая: batch 17662 > лимит 5461 (п | - |
| TD-107 | harness_run: роуты не покрывают естественные формулировки задач — 'вер | - |
| TD-108 | Роуты в runtime_snapshot.json не назначают агентов: agent: None почти  | - |
| TD-110 | portable harness рассинхронизирован с исходным: OPENCODE_HARNESS_ROOT  | - |
| TD-113 | Архитектурная ревизия BRICKS-кода (перенесён с сервера): мёртвая конфи | - |
| TD-114 | Хардкод API-провайдера в synthesizer.py (base_url=https://api.aitunnel | - |
| TD-115 | topics_tree.py: покрытие claim_id расходятся — test_c5: совпало 14/20  | - |
| TD-118 | Таймауты агентов BRICKS-runner: source-fetcher упал по timeout 600с пр | - |
| TD-119 | Primary-обёртки субагентов (10 <name>-runner) созданы ТОЛЬКО в глобаль | - |
| TD-121 | Кросс-оркестрация (TD-099) закрыта ТОЛЬКО для research-контура (resear | - |
| TD-122 | Задача «собрать ГОСТы/ТУ + Фазовые_составы» не покрыта ролевым контрак | - |
| TD-123 | Маппинг материал→норматив отсутствует: для 5 марок (Fe-тех, Р18, Р6М5, | - |
| TD-124 | Нет провенанс-стандарта для собираемых материалов: пользователь требуе | - |
| TD-125 | Прослеживаемость скачанных материалов не автоматизирована: сбор PDF ГО | - |
| TD-127 | Агенты плодят временные скрипты: каждый виток/сессия создаёт ad-hoc py | - |
| TD-128 | SearXNG-инстанс: установка полного SearXNG на Windows невозможна без D | - |
| TD-137 | Канонический стек tools/ создан: scripts/tools/tech_debt_cli.py (add/c | - |
| TD-140 | Нет единой карты диспатча 'задача → контур → инструмент': агент путает | - |
| TD-142 | Разные Python-окружения: chromadb (1.5.9) доступен только в системном  | - |
| TD-143 | Аудит: почему агент НЕ использует инструменты harness — нужна прослойк | - |
| TD-144 | Авто-фиксация техдолга: агент, столкнувшись с блоком, вызывает функцию | - |
| TD-145 | Аудит повторяющихся действий агента: если один и тот же паттерн (ad-ho | - |
| TD-146 | agent повторно пишет ad-hoc скрипты для скачивания PDF вместо использо | - |
| TD-147 | Проверить авто-добавление техдолгов (tech_debt_cli auto) на дупликаты  | - |
| TD-152 | Универсальный PDF-resolver с каскадом источников: агент вручную боретс | - |
| TD-153 | Обход DNS-блокировок в downloader: ENOTFOUND polza.ai / doi.org / SINT | - |
| TD-154 | MCP-инструменты не проброшены в сессию субагентов + RESEARCH_WORKSPACE | - |
| TD-156 | Агент не знает, что sci-bot — это просто API-запрос (sci-bot.ru, WebSo | - |
| TD-157 | downloader.py resolve: каскад падает, хотя прямой doi-путь (тот же sci | - |
| TD-003 | medium | code-orchestrator | Дублирование route данных JSON vs TS — закрыто гейтом check_route_duplication.py (TD-D10) + tests/test_route_duplication.py | 2026-09-24 |
| AG-A1 | [TECH_DEBT_AGENTS] Агенты не зарегистрированы как субагенты OpenCode — ЗАКРЫТО: пайплайн registry+compile_agents, артефакты .opencode/agent/*.md (26), регресс-тесты tests/test_agent_gen.py (qwen-coder) | 2026-09-24 |
| AG-D2 | [TECH_DEBT_AGENTS] health_check→doctor: канонический plugin-aware doctor с живыми probes (bridge.hello/harness.status/protocol.compat/host snapshot/semantic readiness), health_check — тонкая обёртка; гейт + 8 тестов (TD-D2, qwen-coder) | 2026-09-24 |
