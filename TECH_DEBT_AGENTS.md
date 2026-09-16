# Технический долг v1 → v1.1: агенты и их интеграция в OpenCode

Статус: **v1 зафиксирован тегом `v1`** (коммит `a5cf6d6`).
Этот документ — реестр технического долга по агентам и их интеграции, который
необходимо закрыть в **v1.1**. Здесь же — дорожная карта работ.

---

## 1. Что уже работает в v1

| Слой | Состояние |
|---|---|
| Native plugin (`@harness/opencode-plugin`) | Загружается через `.opencode/opencode.json` (file:// → dist/index.js) |
| `harness_status` / `harness_run` | Детерминированный роутинг через Core (`resolve_route.py`) |
| Runtime policy (`runtime_snapshot.json`) | 11 роутов, 10 инструментов, policy_hash `8910fd…` |
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

### TD-A3. Нет маппинга «роль → агент → модель»
- **Факт**: `config/model_routing` в researcher-ядре есть, но в `agents/*.md` роли не привязаны к моделям.
- **Проблема**: `harness_run` не говорит, какой моделью исполнять роль; Desktop использует дефолт.
- **Решение (v1.1)**: в `.opencode/agent/*.md` проставить `model:` из `config/providers_auth` /
  `config/model_routing`; в `harness_run` вернуть `agent_hint` с моделью.

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