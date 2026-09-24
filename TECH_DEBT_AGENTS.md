# Технический долг v1 → v1.1: агенты и их интеграция в OpenCode

Статус: **v1 зафиксирован тегом `v1`** (коммит `a5cf6d6`).
Этот документ — реестр технического долга по агентам и их интеграции, который
необходимо закрыть в **v1.1**. Здесь же — дорожная карта работ.

> **Аудит соответствия коду: 2026-09-24.** Сводка статусов:
> - **Закрыто**: TD-D4 (хэш синхронизирован), TD-A4 (шаг 0 добавлен в `code-orchestrator.md`).
> - **Частично закрыто**: TD-A3 (роли уже содержат frontmatter `mode: subagent`; не хватает
>   `model:` и `agent_hint`), TD-D5 (перенос тестов выполнен, live-сертификация P3 не выполнена).
> - **Открыто (подтверждено фактом отсутствия)**: TD-A1 (`.opencode/agent/` отсутствует),
>   TD-D7 (нет тестов `job_ctl.py`), TD-D9 (нет `MANIFEST.json` / `SHA256SUMS.txt` /
>   `config/decision_aliases.json`), а также TD-A2, TD-D1–D3, TD-D6, TD-D8. TD-D10 закрыт
>   2026-09-24 (гейт `check_route_duplication.py` + тесты). Остальное: TD-I*, TD-T*.
> - Единый реестр проекта: `docs/TRACKERS/TECH_DEBT_MASTER.md` (185 записей, open: 130).

---

## 1. Что уже работает в v1

| Слой | Состояние |
|---|---|
| Native plugin (`@harness/opencode-plugin`) | Загружается через `.opencode/opencode.json` (file:// → dist/index.js) |
| `harness_status` / `harness_run` | Детерминированный роутинг через Core (`resolve_route.py`) |
| Runtime policy (`runtime_snapshot.json`) | 12 роутов, 10 инструментов, policy_hash `df07cc…` (аудит 2026-09-24, `compile_runtime.py --check` PASS) |
| MCP-серверы | 10/10 импортируются; academic_search, coder_router, searxng (degraded без SearXNG), doc_extract |
| Guard (`guard/src`) | Встроенный `session_guard.py` подхватывается researcher'ом (`_HAS_DOC_GUARD=True`) |
| Bootstrap | venv + build + register + health, idempotent |

---

## 2. Технический долг: агенты

### TD-A1. Агенты не зарегистрированы как субагенты OpenCode
- **Факт**: `agents/*.md` — 15 ролей (orchestrators, coder-worker/reviewer/tester, tribunal-judge,
  fact-checker, source-fetcher, synthesizer, claim-parser, …) лежат как **спецификации ролей**.
- **Проблема**: в `.opencode/agent/` их нет. OpenCode Desktop **не видит** их как переключаемые
  агенты; `harness_run` возвращает имена ролей, но вызвать их как `@agent` нельзя.
- **Решение (v1.1)**: генерация `.opencode/agent/*.md` — конвертация каждой роли в формат агента
  OpenCode с frontmatter (`description`, `mode: subagent`, `tools`, `model`, `temperature`) и телом
  — промптом роли из `agents/*.md`.

### TD-A2. Нет иерархии parent/child сессий для субагентов
- **Факт**: `semantic_execute.ts` есть, но гейтится `HARNESS_SEMANTIC_ENABLED=1` (выкл. по умолчанию).
- **Проблема**: трибунал/факт-чек/ресечер не могут запускать изолированные дочерние сессии
  (`parentID`), потому что P3 не сертифицирован live.
- **Решение (v1.1)**: live-сертификация `semantic.execute`, затем миграция Tribunal на дочерние сессии (P4).

### TD-A3. Нет маппинга «роль → агент → модель» — ЧАСТИЧНО ЗАКРЫТО (аудит 2026-09-24)
- **Обновление**: роли в `agents/*.md` уже содержат корректный OpenCode-frontmatter
  (`name`, `description`, `mode: subagent`, `permission`, `steps`), т.е. формат агента готов —
  конвертация frontmatter не требуется. Остаётся: привязка `model:` и `agent_hint` в `harness_run`.
- **Факт**: `config/model_routing` в researcher-ядре есть, но в `agents/*.md` роли не привязаны к моделям.
- **Проблема**: `harness_run` не говорит, какой моделью исполнять роль; Desktop использует дефолт.
- **Решение (v1.1)**: в `.opencode/agent/*.md` проставить `model:` из `config/providers_auth` /
  `config/model_routing`; в `harness_run` вернуть `agent_hint` с моделью.

### TD-A4. Кодер: нет обязательной сверки с git-репо и создания принимающей репо-структуры при старте — ЗАКРЫТО (2026-09-24)
- **Закрытие**: в `agents/code-orchestrator.md` добавлен раздел «Шаг 0 — ритуал старта (обязателен)»:
  сверка `git rev-parse --is-inside-work-tree`, создание принимающей директории/репо
  (`git init` + `.gitignore` + базовый коммит), трекер, `MAP.md`, README, архитектурные файлы,
  фиксация базового среза коммитом до первой правки кода.
- **Исходная формулировка**:
- **Факт**: в `agents/code-orchestrator.md` есть только пассивное упоминание (строка «Безопасность
  работы»): «проверь, что воркспейс — git-репо (или создай при старте задачи)» и «factory_ctl submit
  при воркере автоматически делает git add -A && git commit в CWD». **Нет явного, обязательного
  ритуала сверки при получении задачи**.
- **Проблема**: при работе в новом/пустом окружении кодер может начать писать код вне какого-либо
  git-репо, без принимающей директории и без обязательной структуры проекта. Это приводит к:
  - потерям кода между сессиями (нет коммитов до начала работы);
  - отсутствию канонической структуры (трекер, карта, README, архитектурные файлы);
  - конфликтам с `factory_ctl submit` (который делает `git add -A && git commit` в CWD — если
    CWD — не репо, фабрика падает или создаёт bootstrap-init репо на месте, что нежелательно).
- **Требование (v1.1)**: добавить в `agents/code-orchestrator.md` (и зеркально в
  `coder-worker.md` / генератор `.opencode/agent/*.md`) **обязательный шаг 0-ритуала старта**:
  1. **Сверка с наличием git и рабочей репо**:
     - `git rev-parse --is-inside-work-tree` в рабочей директории;
     - если репо нет — определить/спросить принимающую директорию;
  2. **Создание принимающей директории** (если её нет) и оформление её как репо по всем правилам:
     - `git init` + `.gitignore` + базовый коммит;
     - **трекер** — инициализация канбана/задач (kanban-файл или `task_id` в глобальном канбане);
     - **карта** — `MAP.md`/структура модулей (codemap для нового проекта);
     - **README.md** — назначение, как запускать, контракты;
     - **архитектурные файлы** — шаблоны из `templates/` (ADR, component-spec), `docs/` при необходимости.
  3. **Фиксация базового среза** коммитом до первой правки кода.
- **Приоритет**: высокий (защита от потери кода и рассинхрона с фабрикой).
- **Связано**: TD-D1 (нет `scripts/kanban/`), TD-I2 (память), существующий git-коммит-гейт в `factory_ctl`.

---

## 3. Технический долг: интеграция в работу через OpenCode

### TD-I1. Динамические промпты с привязкой к ролям (ядро v1.1)
- **Факт**: промпты ролей статичны (`agents/*.md`), не подставляют контекст сессии
  (task, workspace_ref, route, capsule, tools).
- **Задача**: сделать **шаблоны промптов** (`templates/agent_prompts/*.md` + `config/agent_prompt_bindings.json`),
  которые Core подставляет при `harness_run`: `{task}`, `{workspace}`, `{route}`, `{capsules}`, `{tools}`,
  `{memory_context}`, `{contracts}`. Итог — готовый системный промпт агента, который plugin передаёт
  в дочернюю сессию (или агент-диспатч).

### TD-I2. Память в harness
- **Факт**: `scripts/` содержит модули памяти (memory), но они **не перенесены** в портированную репу,
  и в `harness_run` нет шага «прочитать память → вставить в промпт».
- **Задача**: портировать `scripts/memory/` (session_memory), добавить в Core:
  - чтение `memory_context` для задачи (по bucket/route/капсуле);
  - запись итогов сессии (что решено, какие контракты закрыты);
  - хранилище: `.runs/memory/*.json` (git-ignored) + опционально SQLite.
- **Контракт**: `MemorySpan/1.0` (scope, key, value, ts, source_session).

### TD-I3. Контракты ролей (проектные контракты, не JSON-схемы)
- **Факт**: есть `config/tool_contracts.json`, `tribunal_role_provider_contract.md`, но **нет контрактов
  «агент → агент»** (что coder-worker обязан вернуть reviewer'у, что researcher обязан отдать synthesizer'у).
- **Задача**: `config/role_contracts/*.json` — машиночитаемые контракты интерфейсов между ролями:
  вход/выход, обязательные поля, инварианты. `harness_run` должен валидировать передачу контракта
  при диспатче.

### TD-I4. Диспатч субагента (agent dispatch)
- **Факт**: плагин умеет только «роутинг + бандл». Нет механизма «вызвать субагента с контрактом».
- **Задача (P4)**: `harness.dispatch` — метод bridge: роль + входной контракт → создаёт дочернюю
  сессию OpenCode (через `semantic.execute`), ждёт результат, валидирует по контракту, возвращает
  `structured_output`.

### TD-I5. Легаси-слой guard (пограничный гейт)
- **Факт**: legacy `tool-skill-contract-router.ts` (с `session_guard` на каждый untrusted-инструмент)
  выпилен; native-плагин имеет только `tool.execute.before` блок на 3 запрещённых инструмента.
- **Задача**: вернуть пограничный guard в native-виде: hook `tool.execute.before` → вызов
  `guard/src/session_guard.py` для untrusted-инструментов (webfetch, searxng, doc_extract),
  с кэшем скоринга. Это закрывает дыру безопасности, оставшуюся после выпиливания legacy.

---

## 3a. Технический долг: Трибунал и его live-версия

### TD-T1. Трибунал перенесён, но **не самодостаточен** (критический долг переносимости)
- **Факт**: все 11 модулей трибунала скопированы
  (`tribunal_advocate/argument_graph/composition/dialectic/disclosure/evidence/inquiry/
  live_dialogue/provider_binding/role_handbook/role_runtime`), конфиги
  (`tribunal_composition.yaml`, `tribunal_provider_binding.yaml`, `tribunal_role_handbook.yaml`,
  `tribunal_role_provider_contract.md`) — на месте.
- **Проблема**: `tribunal_live_dialogue.py:21` и `tribunal_role_runtime.py` делают
  `from scripts.jobs import job_ctl`, а **`scripts/jobs/` НЕ перенесён** в репу. Сейчас импорт
  «работает» только потому, что venv запускается из каталога исходника
  (`E:\...\doc_Opencode_agern-new` попадает в `sys.path` через `''`). **На чистом сервере
  трибунал не загрузится** — `ModuleNotFoundError: No module named 'scripts.jobs'`.
- **Задача**: портировать `scripts/jobs/job_ctl.py` (и его зависимости) в репу;
  проверить, что `import researcher_core.tribunal_live_dialogue` работает на чистом клоне
  без исходника рядом.
- **Приоритет**: **P0** (ломает переносимость трибунала).

### TD-T2. Live-диалог трибунала требует `scripts/jobs` и transport, которого нет в v1
- **Факт**: `tribunal_live_dialogue.py` содержит `SubprocessJsonProviderTransport` (реальный процессный
  границы для E2E) и `LogicalToolProviderTransport` (адаптер к логическому tool-рантайму).
  Реальный live-вызов роли идёт через `job_ctl.create/save/event` + `subprocess`.
- **Проблема**: в v1 нет ни одного **живого** транспорта, подключённого к OpenCode:
  - `semantic.execute` выключен (`HARNESS_SEMANTIC_ENABLED` не задан);
  - plugin не умеет `harness.dispatch` (TD-I4);
  - `job_ctl` без `scripts/jobs` недоступен на чистом сервере (TD-T1).
  Значит «live»-часть трибунала в v1 **недостижима** из Desktop: трибунал может работать только
  детерминированно/на подложке, а живой диалог ролей через модель — нет.
- **Задача (P4)**: после live-сертификации `semantic.execute` мигрировать транспорт трибунала:
  `SubprocessJsonProviderTransport` → дочерняя сессия OpenCode (`semantic.execute` /
  `harness.dispatch`); `RoleProviderBinding` остаётся (роль/авторитет/провайдер разделены).

### TD-T3. Трибунал не имеет дочерних сессий (parent/child)
- **Факт**: плагин умеет `session.create` с `parentID` (подтверждено в P3 smoke), но
  `tribunal_role_runtime.py` / `live_dialogue` не используют дочерние сессии OpenCode.
- **Проблема**: судьи трибунала (физик/методолог/скептик/адвокат/агрегатор) должны исполняться
  в **изолированных** сессиях (нет утечки контекста между ролями), но сейчас такого нет.
- **Задача (P4)**: каждый судья — отдельная дочерняя сессия; `TribunalExecutionEnvelope`
  передаётся как контракт; ответ проходит `DDC/DQC admission` (детерминированный, уже есть
  в `tribunal_disclosure.py`/`tribunal_inquiry.py`).

### TD-T4. Нет live-ролей судей через agent-интерфейс
- **Факт**: в `agents/` есть роль `tribunal-judge.md` (спецификация), но она **не зарегистрирована**
  как субагент OpenCode (TD-A1) и не привязана к модели (TD-A3).
- **Проблема**: судья не может быть вызван как `@tribunal-judge`; live-трибунал не «видит»
  провайдера через OpenCode.
- **Задача**: включить `tribunal-judge` в генератор `.opencode/agent/*.md` (Фаза 1);
  в `harness.dispatch` — поддержка `tribunal.role.execute` (execution_capability из
  `config/tribunal_provider_binding.yaml`).

### TD-T5. Provider binding настроен, но исполнимых провайдеров нет
- **Факт**: `config/tribunal_provider_binding.yaml`:
  `execution_capability: tribunal.role.execute`, `require_live_execution_ready: true`,
  `allowed_provider_kinds: [process, agent, mcp]`, `selection_order: [priority_desc, provider_id_asc]`.
- **Проблема**: в реестре нет ни одного **зарегистрированного живого провайдера** с этим
  capability (нет записи «процесс/агент/MCP, который реально умеет `tribunal.role.execute`»).
  Binding детерминированно вернёт `NO_HEALTHY_PROVIDER` — трибунал fail-closed, что **корректно
  по дизайну**, но означает: live-трибунал в v1 недоступен намеренно.
- **Задача**: в v1.1 зарегистрировать провайдера «OpenCode Desktop agent» с
  `tribunal.role.execute` и связать с `semantic.execute`/`harness.dispatch`.

---

## 3b. Сверка v1 с документацией «миграция в плагин» (архив 2026-09-14)

Сверка проведена против пакета документов `E:\opencode_harness\патчи\миграция в плагин`
(`PROJECT_STATE.md`, `CURRENT_ARCHITECTURE.md`, `OPENCODE_NATIVE_PLUGIN_CURRENT.md`,
`HARNESS_OPENCODE_INTERFACE_CONTROL.md`, `HARNESS_OPENCODE_BOUNDARY_AUDIT_V1.md`,
`HARNESS_PLUGIN_BOUNDARY_MATRIX.json`, `TEST_AND_EVIDENCE_MATRIX.md`, `TECH_DEBT_CURRENT.md`,
`HARNESS_NATIVE_PLUGIN_MIGRATION_PLAN_V2.md`, `NEXT_PHASE_PLAN.md`, `NEXT_SESSION_HANDOFF.md`).

### TD-D1. **Списки модулей в документации vs фактический состав v1** (расхождение переноса)
- **Факт**: `CURRENT_ARCHITECTURE.md` (§5 Module inventory) и `BOUNDARY_MATRIX.json` перечисляют
  подсистемы, которые **есть в исходнике, но НЕ перенесены в v1**:
  - `scripts/writer/` (канонический Writer CLI) — **отсутствует** (в v1 только `writer-core`);
  - `scripts/kanban/` — отсутствует;
  - `scripts/memory/` — отсутствует (уже отмечено TD-I2);
  - `scripts/capsules/` — отсутствует;
  - `shared/` (research-orchestration-process.md и др.) — отсутствует.
- **Влияние**: Writer в v1 недоступен как authority-модуль; kanban/memory/capsules — недоступны.
  Это не «план», а **фактическая неполнота переноса** относительно объявленной архитектуры.
- **Задача v1.1**: портировать `scripts/writer/`, `scripts/capsules/`, `scripts/memory/`,
  `scripts/kanban/`, `shared/` (или явно задокументировать их исключение из v1).

### TD-D2. **`health_check.py` всё ещё legacy-ориентирован** (документация требует замены)
- **Факт**: `HARNESS_OPENCODE_INTERFACE_CONTROL.md` §2 RED-6 и `BOUNDARY_MATRIX.json` требуют
  заменить `scripts/health_check.py` (legacy: «plugin registered + DB accessible») на
  **plugin-aware doctor** (plugin loaded probe, bridge handshake, core health, protocol compat,
  host feature snapshot, semantic provider readiness).
- **Проблема**: в v1 `health_check.py` исправлен под native-проверку (plugin URI), но **не стал
  полноценным doctor**: нет bridge handshake probe, нет host feature snapshot, нет semantic
  provider readiness. `doctor.py` (`packages/.../core/doctor.py`) — статичен (config presence).
- **Задача**: свести `health_check.py` → `doctor.py` как единый канонический health-инструмент
  с живыми probes (bridge.hello, harness.status, capability snapshot).

### TD-D3. **`config/opencode_plugin_config.json` и `scripts/register_plugin.py`** — статус в v1
- **Факт**: `INTERFACE_CONTROL.md` §12 и `BOUNDARY_MATRIX.json` помечают:
  - `config/opencode_plugin_config.json` → REPLACE (by npm/local plugin package config);
  - `scripts/register_plugin.py` → REPLACE (by installer).
- **Проблема**: в v1 `opencode_plugin_config.json` переписан под native (mode=native), а
  `register_plugin.py` переписан под project-scoped — **функционально закрыто**, но формально
  не совпадает с целевой архитектурой (нет «installer/package registration»).
- **Задача**: понизить приоритет; документировать, что `register_plugin.py` в v1 — временный
  project-scoped helper, канонический путь — bootstrap + `.opencode/opencode.json`.

### TD-D4. **Capability hash расходится с документацией** — ЗАКРЫТО (2026-09-24)
- **Закрытие**: таблица §1 синхронизирована с фактическим `config/runtime_snapshot.json`
  (12 роутов, policy_hash `df07cc…`; подтверждено `compile_runtime.py --check`).
- **Исходная формулировка**:
- **Факт**: документация (`TEST_AND_EVIDENCE_MATRIX.md`, `PROJECT_STATE.md`) заявляет
  capability compiler hash `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`.
- **Реальность**: исходник и v1 дают `f9de8128f960000470c286b0b153861ec8ff906b2fa6f3be712dbf1d924e47a0`
  (base = runtime `8910fd…`, совпадает). Документация **устарела** (или относится к другому дереву).
- **Действие**: не наш долг; зафиксировать в доке расхождение (документация не синхронизирована с кодом).

### TD-D5. **`semantic.execute` reverse adapter не имеет cancel/timeout E2E на v1** — ЧАСТИЧНО ЗАКРЫТО (перенос тестов выполнен, аудит 2026-09-24)
- **Факт**: `INTERFACE_CONTROL.md` §1.2/§10 требует `AbortSignal → harness.cancel → session abort`,
  и M2 acceptance включает cancellation + 100 concurrent messages.
- **Проблема**: в v1 bridge-тесты (hostless) **не перенесены** (TD-F2), cancel propagation
  не проверен на живой сборке; `semantic_execute.ts` есть, но не сертифицирован.
- **Частично закрыто (local harness, DEV-05 M1–M3b, 2026-09-15)**: в `scripts/code-factory/semantic_transport.py`
  и `packages/opencode-harness-plugin/core/bridge_peer.py` реализован реальный reverse-канал
  `semantic.execute` с plugin-side consumer; timeout_ms пробрасывается из request (кап 120000);
  добавлен boundary E2E `tests/coder/test_bridge_channel_e2e.py` (таймаут, отказ плагина, спавн-сбой,
  missing peer → HOST_UNAVAILABLE) + 58 авто-тестов `test_bridge_peer_autotests.py` (итого 139 в tests/coder).
- **Задача (v1.1)**: перенести эти тесты в portable (уже скопированы в `tests/coder/` на этой ветке),
  добавить cancel propagation через AbortSignal на живой сборке Desktop; live-сертификация P3 остаётся.

### TD-D6. **Writer/Coder «semantic launcher leakage» сохранена** (legacy CLI)
- **Факт**: `INTERFACE_CONTROL.md` §1.6/RED-5: `mcp/coder_router_server.py`,
  `mcp/launchers/opencode_code_worker.py`, `_runner.py`, `opencode_research_*`,
  `opencode_tribunal_role.py` используют прямой `opencode run` (CLI legacy transport).
- **Проблема**: в v1 все эти launchers на месте и **не мигрированы** на `semantic.execute`.
  Это legacy-путь, который должен остаться только как явный fallback, но не стать production.
- **Задача**: зафиксировать `transport=opencode_cli_legacy` для них; не мигрировать до
  сертификации plugin semantic E2E (по `NEXT_PHASE_PLAN.md` — это P5).

### TD-D7. **`scripts/jobs/job_ctl.py` перенесён, но нет канонических job-тестов** — ЗАКРЫТО (2026-09-24)
- **Закрытие**: добавлен smoke-набор `tests/test_job_ctl.py` (create → start → attempt → artifact →
  stage/gate → complete, reconcile, reject-missing-job) + документирование host_ref mapping в
  разделе «Host-ref mapping» ниже. Оставшаяся корреляция session↔Job — metadata, не Job ID (осознанно).
- **Факт**: `INTERFACE_CONTROL.md` §1.2 называет `job_ctl.py` canonical Job/Attempt runtime
  с event-sourced JSON state, attempts, children, artifacts, stages, gates, reconciliation.
- **Проблема**: файл перенесён (закрыт TD-T1), но в v1 **нет тестов** Job/Attempt runtime
  и нет маппинга host_session_id ↔ Job ID (корреляция — metadata, не Job ID).
- **Задача**: добавить smoke-тест `job_ctl` и задокументировать host_ref mapping
  (OpenCode session ≠ Harness Job).

### TD-D8. **Документация P1→P2 status**: `compatibility/opencode/1.18.30.json` утверждает больше, чем доказывает
- **Факт**: `TEST_AND_EVIDENCE_MATRIX.md` строго различает evidence-уровни: `HOSTLESS_REPORTED`,
  `LIVE_CERTIFIED`, `PENDING`. В v1 `compatibility/opencode/1.18.30.json` содержит
  `LIVE_VERIFIED` для `PLUGIN_LOADED`, `CUSTOM_TOOL_VISIBLE`, `BRIDGE_FULL_DUPLEX`,
  `SESSION_CREATE/...` — но P1_STATUS.md сам говорит `P3 SEMANTIC LIVE SMOKE PASS` на движке
  1.18.30 (событие `session.created`).
- **Проблема**: mix: часть capability `LIVE_VERIFIED` (plugin load/tools) — согласовано с
  P1_STATUS (P2 live verification 2026-09-14); часть — `verified against package types` (session
  API). Это **не чистый LIVE_CERTIFIED** по строгой шкале документации.
- **Задача**: в v1.1 привести `compatibility/*.json` к шкале `TEST_AND_EVIDENCE_MATRIX.md`
  (`LIVE_CERTIFIED` только после live P2 gate на чистой установке).

### TD-D9. **Отсутствуют канонические машинные файлы из README_FIRST** — ЗАКРЫТО (2026-09-24)
- **Закрытие**: добавлен генератор `scripts/tools/gen_manifest.py` (stdlib, детерминированный);
  сгенерированы `MANIFEST.json`, `SHA256SUMS.txt` и стаб `config/decision_aliases.json`.
  Проверка поставки: `python3 scripts/tools/gen_manifest.py --check`.
- **Факт**: `README_FIRST(2).md` перечисляет канонические machine-файлы: `MANIFEST.json`,
  `SHA256SUMS.txt`, `config/decision_aliases.json`. В v1 их **нет**.
- **Проблема**: нет инвентаря точного дерева и чексумм — невозможно верифицировать
  «что в поставке» против объявленного состава.
- **Задача (низкий приоритет)**: сгенерировать `MANIFEST.json` + `SHA256SUMS.txt`
  из текущего release tree + `decision_aliases.json`.

### TD-D10. **Дублирование route-данных (TD-003) в v1 не проверено** — ЗАКРЫТО (2026-09-24)
- **Закрытие**: добавлен детерминированный гейт `scripts/router/check_route_duplication.py`
  (invariant-проверки I1–I4: snapshot ↔ авторитетные источники через пересборку
  `compile_runtime`, compat-вью `profile_routes/tool_skill_routes/skill_to_route_map`
  ↔ проекция snapshot + актуальность `generated_from_policy_hash`, hardcode route-id
  в TS плагина (`packages/opencode-harness-plugin/src/**/*.ts`) ↔ snapshot, идентичность
  id-наборов и индексов). Выход != 0 при любом дрейфе; готов к CI/pre-commit.
  Тесты: `tests/test_route_duplication.py` (7 тестов: позитив на реальном дереве +
  мутации каждой категории нарушений). На HEAD все инварианты выполняются (PASS).
- **Исходная формулировка**:
- **Факт**: `TECH_DEBT_CURRENT.md` (TD-003, RECONCILE_REQUIRED): «Дублирование route данных
  JSON vs TS»; `RECONCILIATION_REQUIRED.md` требует проверить exact release tree.
- **Проблема**: в v1 `runtime_snapshot.json` (компилируемый) и TS-схемы — потенциально
  рассинхронизированы; нет автоматической проверки соответствия.
- **Задача**: в v1.1 добавить validation «snapshot ↔ schemas» в `compile_runtime.py --check`
  (или отдельный скрипт).

---

## 4. Дорожная карта v1.1

### Фаза 1 — Агенты (базовая интеграция)
- [ ] Генератор `.opencode/agent/*.md` из `agents/*.md` (+ frontmatter, model из конфига)
- [ ] Пакет `scripts/agent_gen/` (детерминированный, stdlib)
- [ ] `harness_run` возвращает `agent_hint: {agent, model, prompt_template}`
- [ ] Проверка: агенты видны в Desktop, `@coder-worker` вызывается

### Фаза 2 — Динамические промпты + контракты
- [ ] `templates/agent_prompts/*.md` (шаблоны с плейсхолдерами)
- [ ] `config/agent_prompt_bindings.json` (роль → шаблон, правила подстановки)
- [ ] `config/role_contracts/*.json` (интерфейсы роль→роль)
- [ ] Core: подстановка `{task} {workspace} {route} {memory_context} {contracts}` в промпт
- [ ] `harness.dispatch`: роль + контракт → дочерняя сессия → валидация результата

### Фаза 3 — Память + guard
- [ ] Портировать `scripts/memory/` (session_memory, MemorySpan/1.0)
- [ ] Core: read memory → inject в промпт; write memory после диспатча
- [ ] Native guard: `tool.execute.before` → `session_guard.py` для untrusted-инструментов
- [ ] Live-сертификация `semantic.execute` (P3) → включить `HARNESS_SEMANTIC_ENABLED=1`

### Фаза 4 — Стабильность
- [ ] Тесты: `tests/` плагина (7 файлов из исходника) перенести и адаптировать
- [ ] E2E: полный цикл research → tribunal → synthesizer через Desktop
- [ ] Документация: `docs/AGENTS_INTEGRATION.md`

---

## 5. Границы (что НЕ входит в v1.1)
- Миграция всех вспомогательных подсистем исходника (kanban, caps, remote_acceptance).
- Семантическое исполнение без live-сертификации (strict gate).
- Поддержка публичных навыков (132) — уже полная в v1.

---

## 6. Критерии готовности v1.1
1. В Desktop видны 15 субагентов (`@coder-worker` и т.д.) и они исполняются с ролевыми промптами.
2. `harness.dispatch` прогоняет роль с контрактом и валидирует результат.
3. Память пишется/читается в `.runs/memory/`, контекст попадает в промпты.
4. Guard-гейт закрывает webfetch/searxng/doc_extract (native hook).
5. `doctor.py` и `health_check.py` — HEALTHY; bridge smoke green.