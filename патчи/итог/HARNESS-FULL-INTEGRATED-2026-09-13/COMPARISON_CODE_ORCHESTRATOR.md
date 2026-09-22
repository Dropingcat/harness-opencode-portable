# Сравнение: harness vs живой code-orchestrator OpenCode + режим моей работы

Дата: 2026-08-31. Источник правды: `C:\Users\Arhys\.config\opencode\opencode.jsonc`, `agents/code-orchestrator.md` (live), `agents/code-orchestrator.md` (harness), `shared/` и `scripts/code-factory/` на этой машине, `GLOBAL_TASK_CONTROLLER.md`, `CODER_DESIGN_PRINCIPLES.md`.

## 1. Что есть в живой системе сейчас (факт на диске)

**opencode.jsonc (live, Windows):**
```json
{
  "plugin": ["@bluelovers/opencode-arise","@hiai-gg/hiai-opencode","opencode-command-inject","envsitter-guard","opencode-token-tracker"],
  "subagent_depth": 2,
  "compaction": {"auto":true, "prune":true, "tail_turns":15},
  "tool_output": {"max_lines":1000, "max_bytes":32768}
}
```
- Нет `mcp` секции, нет кастомных MCP серверов в runtime (harness предполагает `academic_search`, `searxng_search`, `doc_extract`, `coder_router`).
- Нет `skills.paths/urls` — skills берутся из `~/.config/opencode/skills` и внешних (`~/.claude/skills`).
- `shared/` и `scripts/code-factory/` существуют, но **пустые** (`[]`): нет `code-factory-process.md`, нет `factory_ctl.py`, нет `contract_validator.py`, нет `code_factory_runner.py`.

## 1.1 Что найдено на `W:\server2`

Серверный комплект фабрики кода реально существует:

- `W:\server2\shared\code-factory-process.md`
- `W:\server2\scripts\code-factory\factory_ctl.py`
- `W:\server2\scripts\code-factory\contract_validator.py`
- `W:\server2\scripts\code-factory\code_factory_runner.py`
- `W:\server2\agent\code-orchestrator.md`
- `W:\server2\agent\coder-worker.md`
- `W:\server2\agent\code-reviewer.md`
- `W:\server2\agent\code-tester.md`
- `W:\server2\agent\code-auditor.md`

Значит, проблема не в потере фабрики кода, а в том, что **live OpenCode на Windows сейчас не использует этот комплект как runtime-модуль**.

**Живой code-orchestrator.md (C:\Users\Arhys\.config\opencode\agent\code-orchestrator.md):**
- Шаги 1-10: read process → memory search → decomposition → plan → dispatch workers → dispatch reviewers → dispatch testers → tribunal → integrate → memory add.
- Валидация: `factory_ctl.py submit <agent_type> <output.json> --state <state.json> --module <id>` (`/home/orangepi/...`), exit 0/2/3, retry max 2, falsification check, аудитор без кода.
- Трекер: `python3 -c "from global_kanban import GlobalKanban; gk.report('code-factory',...)'` на `/home/orangepi/.hermes/kanban`.
- Контракты делегирования: worker `{module,code,description,notes}`, reviewer `{module,verdict,comments[falsification]}`, tester `{module,result,passed/failed,coverage}`, auditor `{verdict,justification,process_analysis}`, experimenter.
- State machine `PENDING→RUNNING→PASSED|FAILED|AMBIGUOUS|BLOCKED`, приоритет `requires_user > auditor_block > iteration_limit`.
- Guard упомянут только в общем виде, не как mandatory gate.

**Вывод факта:** документация оркестратора описывает Pi-пути, которых на этой Windows-машине нет, но сам комплект контроллера найден на `W:\server2`. Рантайм сейчас — **"документация есть, контроллер лежит отдельно от live OpenCode"**.

## 2. Что добавил harness (doc_Opencode_agern)

Важно: после сверки с `E:\барахло\Documents\Default Project` видно, что harness не должен выдумывать отдельную философию для code-factory. Он должен наследовать researcher-style architecture: R0 contracts, deterministic runtime, policy-driven heuristics, typed stop reasons, projection/gap/conflict separation. См. `UNIFIED_ORCHESTRATION_PRINCIPLES.md`.

| Слой | Live | Harness | Разрыв |
|---|---|---|---|
| **Принципы** | 8 правил внутри orchestrator.md | Вынесены в `CODER_DESIGN_PRINCIPLES.md` + ARIZ-light 0-7, DoD из 7 пунктов | Было внутри агента → стало переиспользуемый док |
| **Contracts** | Только в тексте агента | Машиночитаемо: `config/tool_skill_routes.json` (10 routes) + `config/guard_policy.json` + `DYNAMIC_HEURISTICS.md` + `TECH_DEBT.md` | Live не имеет JSON-контрактов |
| **Guard** | Опционально упоминается | `SECURITY_GUARD.md` + `config/guard_policy.json` → mandatory fail-closed для code/research orchestrator, 4 guard points, `tool.execute.after` hook | Live guard = плагин `envsitter-guard`, не `doc_guard` |
| **TRIZ** | Раздел "TRIZ при инженерии" (4 шага) | `TRIZ_FOR_CODERS.md` — Provisor/Generator/Critic/Kanban/ARIZ 8×3 из `triz-agent` с копиями в `references/triz-agent/` | Live = кратко, harness = полный цикл с метриками |
| **Dynamic heuristics** | Нет | `DYNAMIC_HEURISTICS.md` — 6 эвристик кода + 7 валидации, конфиг `dynamic_heuristics.json` | Новое |
| **NoAgents** | Только Stub упоминание в WP-2 | `NO_AGENTS.md` — детерминированная ветка без LLM (CoderStub/CriticStub/Verifier/Guard P0/Schema/Kanban), контракт `mode=noagents` | Новое |
| **Tech debt** | Нет отдельного учета | `TECH_DEBT.md` + `config/tech_debt.json` (TD-001..TD-008, Sunset Clause) | Новое |
| **Task tracker** | Только `GlobalKanban` вызов в тексте | `GLOBAL_TASK_CONTROLLER.md` + `references/global-kanban/global_kanban.py` (agents/statuses) + Doc Controller (MANIFEST + WP-0..WP-4) | Live вызывает несуществующий путь |
| **MCP** | Нет в opencode.jsonc | `mcp/coder_router_server.py`, `academic_search_server.py`, `doc_extract_server.py`, `searxng_search_server.py` + 5 launchers (`code_work`, `research_web/academic`, `service_task`, `profile_config`) | Разрыв: harness подготовил, live не подключил |
| **Router hook** | Нет | `plugins/tool-skill-contract-router.ts` — `tool.definition` + `experimental.chat.system.transform` + `tool.execute.after` (guard) | Live plugins: arise/hiai/command-inject/envsitter/token-tracker |

**harness/ agents/code-orchestrator.md отличия от live:**
- Добавлены шаги: `CODER_DESIGN_PRINCIPLES.md` + `Guard preflight` (шаг 2), `decomposition contract-first` с `scope in/out, guard, sunset` (шаг 4), `gate` планирование (шаг 5), `guard/test/schema gates` на интеграции (шаг 10).
- Добавлен раздел "Принципы проектирования кодеров" (6 инвариантов) прямо в агента.
- Остальное идентично (валидация, трекер, контракты, escalation, state machine, TRIZ).

## 3. Как я работаю сейчас как модуль с OpenCode

Ты сейчас общаешься не с "встроенным code-orchestrator", а со мной — **универсальный AI-агент OpenCode** (muse-spark), который выполняет твой запрос на доработку harness.

Моя текущая архитектура работы:

```
[Ты: "продолжай"] -> [Я: primary agent, mode=all, subagent_depth=2]
   |-- read (читаю md/py/json на E: и C: и Z:)
   |-- bash/python (исполняю команды, проверяю guard, валидирую JSON)
   |-- write/apply_patch (правлю bundle, не трогая live opencode.jsonc)
   |-- glob/grep (ищу принципы, TRIZ, wp)
   |-- todowrite (веду план, но не GlobalKanban — локальный todo)
   \-- question (если нужна развилка, спрашиваю через инструмент)
```

**Что совпадает с code-orchestrator:**
- Использую `read` перед `edit/write` (как требует orchestrator).
- Декомпозирую задачу (principals → TRIZ → tech debt → trackers → heuristics → noAgents).
- Пишу по контракту: каждый модуль имеет вход/выход/acceptance (см. TODOWRITE).
- Валидирую JSON (`tool_skill_routes.json`, `guard_policy.json`, `py_compile`).
- Соблюдаю `LLM свидетельствует, код решает` — проверяю через `bash` (py_compile, json load, grep секретов).
- Не дублирую секреты, не коммичу без запроса, не ставлю плагины без валидации.

**Что отличается от code-orchestrator (и почему это нормально):**
- Я **не диспатчу subagents через `task`** для этой задачи — делаю всё сам как primary agent. Code-orchestrator в своей роли обязан диспатчить `coder-worker`, `code-reviewer`, `code-tester`, `code-auditor` параллельно. Я же — твой "оркестратор верхнего уровня" над harness, а не над кодом `src/core`.
- Я **не пишу в `factory_ctl.py` live** — в live runtime его нет на диске. Хотя серверная версия найдена на `W:\server2`, она ещё не импортирована в `C:\Users\Arhys\.config\opencode\scripts\code-factory`.
- Я **не пишу в `global_kanban` live** (`/home/orangepi/...`) — пишу в локальный `todowrite` + готовлю `GLOBAL_TASK_CONTROLLER.md` с инструкцией для Windows `.kanban.db`.
- Я **не подключаю MCP live** — только готовлю `mcp/*.py` и `plugins/tool-skill-contract-router.ts` как артефакты для будущего подключения.
- Guard у меня — **документационный + ручной grep**, а не runtime `tool.execute.after` (т.к. плагин еще не зарегистрирован).

То есть: я работаю как **подготовительный модуль** — собираю bundle, который потом станет частью OpenCode, когда ты зарегистрируешь плагин/MCP и заполнишь `shared/scripts`.

## 4. Интеграция harness как модуля в OpenCode (что нужно, чтобы заработало как задумано)

**Минимальный путь (Window, без Pi):**

1. Скопировать с `W:\server2` в live OpenCode:
   - `shared/code-factory-process.md`
   - `scripts/code-factory/factory_ctl.py`
   - `scripts/code-factory/contract_validator.py`
   - `scripts/code-factory/code_factory_runner.py`
   Сейчас live каталоги пустые — без этих четырёх файлов orchestrator не детерминирован и не исполним.
2. Создать `${OPENCODE_HARNESS_ROOT}\.kanban.db` через `GlobalKanban(db_path=...)` (см. `GLOBAL_TASK_CONTROLLER.md` §5).
3. Зарегистрировать `plugins/tool-skill-contract-router.ts` в `opencode.jsonc` → `plugin: [...]` (сейчас там 5 плагинов, добавить 6-й локальный путь), затем **перезапустить OpenCode**.
4. Добавить `mcp` секцию в `opencode.jsonc` для `academic_search`, `searxng_search`, `doc_extract`, `coder_router` (по шаблону из `CAPABILITY_REGISTRY.md`).
5. Выставить env: `OPENCODE_HARNESS_ROOT`, `OPENCODE_SESSION_DB`, `DOC_GUARD_ENTRYPOINT`, `PYTHON`, а также Windows-safe путь для state file вместо `/tmp/factory_state.json`.

## 4.1 Что уже совместимо с OpenCode как с модулем

Совместимо уже сейчас:

- agent-файлы в формате OpenCode frontmatter;
- plugin-файл `plugins/tool-skill-contract-router.ts` в формате OpenCode hooks;
- skills/docs bundle как внешний модуль документации и правил;
- MCP python servers как отдельные локальные MCP-процессы.

Не совместимо без адаптации:

- hardcoded `/home/orangepi/...` пути в agent/process docs;
- hardcoded `/tmp/factory_state.json` в `factory_ctl.py`;
- ожидание `global_kanban.py` по Linux-пути;
- отсутствие `mcp` секции в live `opencode.jsonc`;
- отсутствие plugin registration для `plugins/tool-skill-contract-router.ts`.

## 4.2 Как это соотносится с тем, как я работаю сейчас

Сейчас я работаю как **внешний модуль подготовки runtime**:

- не заменяю OpenCode runtime;
- не патчу live конфиг без твоего сигнала;
- собираю совместимый комплект, чтобы OpenCode потом использовал его нативно.

То есть архитектурно это выглядит так:

```
OpenCode runtime (live)
   ├─ built-in/tools/plugins (сейчас)
   ├─ code-orchestrator agent (есть, но недозапитан runtime-зависимостями)
   └─ doc_Opencode_agern (готовящийся модуль совместимости)
        ├─ docs/contracts/guard/triz/noagents
        ├─ future plugin hook
        ├─ future MCP servers
        └─ migration plan from W:\server2 -> Windows runtime
```

Иными словами: я сейчас не "альтернативный orchestrator", а **migration/integration layer author** для OpenCode.

После этого мой текущий режим работы (primary agent → read → bash → write) бесшовно перейдет в режим code-orchestrator:
- `task` диспатч → `factory_ctl submit` → `global_kanban report` → `doc_guard` gate → `TRIZ` при конфликте → `tech_debt` при просрочке sunset.

## 5. Рекомендация

Не ломай живой `opencode.jsonc` сейчас. Оставь harness как **параллельный модуль** (`doc_Opencode_agern` + `references/`), а интеграцию делай волнами (см. `INTEGRATION_PLAN.md`): Wave 0 — docs & bundle (готово), Wave 1 — Windows alignment (скопировать factory_ctl + kanban), Wave 2 — MCP подключение, Wave 3 — guard mandatory.

Так ты получишь: code-orchestrator остается мозгом, harness — его машиночитаемыми контрактами, TRIZ/NoAgents/эвристики — режимами, а я — исполнителем, который одинаково работает и как "сборщик bundle" сейчас, и как диспетчер воркеров потом.
