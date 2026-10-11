# БЛОКИ B1–B5: МИГРАЦИЯ E:\opencode_harness_portable → LIVE

**Дата:** 2026-10-05
**Статус:** СПЕЦИФИКАЦИИ ГОТОВЫ, ИСПОЛНЕНИЕ НЕ НАЧАТО (кроме M0-a — ГОТОВО)
**CWD:** `E:\opencode_harness_portable` (все команды — из корня portable, если не указано иное)
**Python:** `.venv\Scripts\python.exe`

> Назначение: детали миграции структуры (B1), live-зеркала (B2), сессий/env (B3), точечных правок (B4) и финальной миграции 8 шагов (B5). Каждый блок самодостаточен: что, файлы, команды, DoD, роллбэк.

---

# B1 — ЦЕЛЕВАЯ СТРУКТУРА (ГОТОВО)

## B1-T1 — venv: whitelist-перенос (НЕ бинарное копирование)

**Проблема:** portable `.venv` содержит 62 пакета против 76 в каноне. Решение — whitelist, не бинарное копирование.

**Что:**
1. Установить в `.venv\Scripts\pip.exe` ровно 17 пакетов (whitelist):
   ```
   pytest rich pymorphy3 pymorphy3-dicts-ru pypdf DAWG2-Python razdel typer colorama
   Pygments markdown-it-py mdurl annotated-doc pluggy iniconfig shellingham websockets
   ```
2. searXNG — по требованию (НЕ ставить сейчас).
3. НЕ копировать venv канона бинарно.

**DoD (команда → результат):**
```
.venv\Scripts\pip.exe freeze | Measure-Object   # счётчик ≥62 (17 whitelist + уже установленные)
.venv\Scripts\pip.exe show pymorphy3 pypdf DAWG2-Python razdel typer websockets  # все 7 есть
.venv\Scripts\python.exe -c "import pydantic, starlette, uvicorn; print('OK')"  # pydantic 2.13.5 + uvicorn/starlette присутствуют (нужны meta и serve)
```

**Роллбэк:** удаление лишних пакетов `pip uninstall -y <pkg>`.

---

## B1-T2 — Ядро конфигурации: opencode.json → portable (5 правок + 8 DoD)

**Файл:** `.opencode\opencode.json` (42 строки).
**Текущие канонные строки:** 6 (plugin `file:///E:/Documents/Документы/doc_Opencode_agern-new/packages/...`), 12/20/28/36 (mcp `command[0]` = канонный python).

**Предусловие:** живой движок opencode 1.18.30 (проверить `compatibility/opencode/1.18.30.json` существует).

**Правки (5):**
| № | Строка | Было | Стало |
|---|--------|------|-------|
| 1 | 6 | `"file:///E:/Documents/Документы/doc_Opencode_agern-new/packages/opencode-harness-plugin/dist/index.js"` | `"file:///E:/opencode_harness_portable/packages/opencode-harness-plugin/dist/index.js"` |
| 2 | 12 | `E:\Documents\...\.venv\Scripts\python.exe` | `E:\opencode_harness_portable\.venv\Scripts\python.exe` |
| 3 | 20 | то же | то же |
| 4 | 28 | то же | то же |
| 5 | 36 | то же | то же |

**Механика:** `.Replace()` (НЕ regex); `WriteAllText` в UTF-8 **без BOM**.

**8 DoD (все — комманды):**
1. `Get-Content .opencode\opencode.json -Raw | Select-String "doc_Opencode_agern"` → **пусто** (канон-ссылок нет).
2. `Get-Content .opencode\opencode.json -Raw | Select-String "opencode_harness_portable"` → **6 совпадений** (plugin + 4 python + можно путь сервера, см. ниже).
3. Строка 12/20/28/36 → `E:\opencode_harness_portable\.venv\Scripts\python.exe`.
4. `Test-Path .opencode\opencode.json` → True; файл валидный JSON: `.venv\Scripts\python.exe -c "import json; json.load(open(r'.opencode\opencode.json')); print('JSON_OK')"` → `JSON_OK`.
5. UTF-8 без BOM: `(Get-Content .opencode\opencode.json -Encoding UTF8 -Raw).StartsWith($(Get-Content .opencode\opencode.json -Raw))` + `[System.IO.File]::ReadAllBytes(...)[0]` НЕ `EF` → без BOM.
6. `Test-Path packages\opencode-harness-plugin\dist\index.js` → True (plugin dist собран).
7. `Test-Path compatibility\opencode\1.18.30.json` → True (движок-предусловие; файл существует — LIVE_CERTIFIED).
8. `git status --porcelain` после правки → только `.opencode/opencode.json` изменён.

**Примечание:** серверные пути `E:\opencode_harness_portable\mcp\*.py` уже корректны (см. исходный конфиг); менять только `command[0]` (python).

**Роллбэк:** `git checkout -- .opencode/opencode.json`.

---

## B1-T3 — Мета-комплект (27 файлов + шаблон) + B4-T7 compile_agents

**Источник:** `E:\Documents\Документы\doc_Opencode_agern-new\scripts\meta` → `E:\opencode_harness_portable\scripts\meta`.
**Копировать как есть** (без правок кода): 27 py + `templates/orchestrator_templates.json`. `sleep_integration.py` в portable — НЕ трогать (28-й файл уже есть).

**27 файлов:**
```
aar.py auditor_v2.py auto_bootstrap.py branch.py contracts.py damage_basket.py
debt_cycle.py external_auditor.py health_monitor.py legacy.py memory_circulator.py
memory_injector.py merge_protocol.py meta_core.py meta_daemon.py orchestrator.py
orchestrator_integration.py perfectionist.py prompt_engine.py react_auditor.py
render_prompt.py run_audit_cycle.py skill_master.py sleep_controller.py
sleep_planner.py state.py trace_store.py validation_engines.py
```

**Команда:**
```powershell
$src = "E:\Documents\Документы\doc_Opencode_agern-new\scripts\meta"
$dst = "E:\opencode_harness_portable\scripts\meta"
$files = @("aar.py","auditor_v2.py","auto_bootstrap.py","branch.py","contracts.py","damage_basket.py","debt_cycle.py","external_auditor.py","health_monitor.py","legacy.py","memory_circulator.py","memory_injector.py","merge_protocol.py","meta_core.py","meta_daemon.py","orchestrator.py","orchestrator_integration.py","perfectionist.py","prompt_engine.py","react_auditor.py","render_prompt.py","run_audit_cycle.py","skill_master.py","sleep_controller.py","sleep_planner.py","state.py","trace_store.py","validation_engines.py")
foreach ($f in $files) { Copy-Item -Force -LiteralPath "$src\$f" -Destination "$dst\$f" }
Copy-Item -Force -Recurse -LiteralPath "$src\templates" -Destination "$dst\templates"
Remove-Item -Recurse -Force -LiteralPath "$dst\__pycache__" -ErrorAction SilentlyContinue
```

**DoD (детальные — `02_BRANCHES_W1_W13.md` §W7, Проверки 1-11):**
1. Импорт 29 модулей без канона: `ALL_IMPORT_OK 29 FAIL []` + exit 0.
2. `compileall -q scripts\meta` → exit 0.
3. `(Get-ChildItem scripts\meta -Filter *.py -File).Count` → **28** (27 + sleep_integration).
4. grep хардкодов канона → `NO_CANON_HARDCODES`.
5. `STATE_DIR_OK` (runtime-пути в корень portable).
6. `meta_daemon --once --orchestrator code-orchestrator` → JSON `{"sleep": false, "hp": N, ...}`.
7. Sleep cycle dry-run: `"simulated": true`, `"merged": ["fix/A"]`, exit 0.
8. Guard: `[{"id":"circle",...}]`, exit 1.
9. Liveness: после `meta_daemon --once` → `alive: true`.
10. V-1 veto: `True dead`.
11. `perfectionist` completion_hook: `needs_improvement` при TODO.

**Прочие шаги:** создать `.meta_state\` (пустой); добавить runtime-паттерны в `.gitignore` (см. §B3-T4/W1); вставить секцию «Meta-Cycle health (V-1)» в `agents/code-orchestrator.md` (точный текст — `02_BRANCHES_W1_W13.md` §W7.4.1); создать `meta_nightly.cmd` + XML.

**Роллбэк:** `git checkout -- scripts/meta` (после коммит-среза) или удалить `scripts/meta/*.py` кроме `sleep_integration.py` и повторить копирование.

---

## B1-T4 — shared: 9 недостающих + route-preflight.md

**Файлы:** `E:\Documents\Документы\doc_Opencode_agern-new\shared` → `E:\opencode_harness_portable\shared`.
**Состав:** в portable сейчас ТОЛЬКО 2 файла (`harness-dispatch-map.md`, `search-depth-contract.md`). Перенести 9 недостающих + создать новый `route-preflight.md` (см. `03_ACCEPTANCE.md` §M1).

**DoD:** `git diff --no-index E:\Documents\Документы\doc_Opencode_agern-new\shared E:\opencode_harness_portable\shared` → только ожидаемая разница (9 файлов + 2 существующих + route-preflight.md). Проверка каждого файла на хардкоды канона (grep) → пусто.

---

## B1-T5 — Легализация канона → _LEGACY_ARCHIVE

**Что:** переименование `E:\opencode_harness` → `E:\opencode_harness\_LEGACY_ARCHIVE` + reparse point (junction), чтобы старые пути продолжали работать как указатели на архив.

**Важно (P-MAJ-4):** Desktop (Electron) использует `session.directory` канона. После легализации:
1. Проверить, что Desktop-контур переживает переименование (тест запуска после B1-T2).
2. Если Desktop ломается — актуализировать глобальный `opencode.jsonc` (см. `03_ACCEPTANCE.md` §M0-b — дефолт НЕ регистрировать плагин глобально; но env/пути — да).

**Судьба канон-корня (~100 документов):** избранное → `docs/canon` (ENV_VARIABLES, REFACTOR_PLAN как история); действующие контракты → `shared` (MEMORY_POLICY, SECURITY_GUARD, ROLE_CARD); остальное → `_LEGACY_ARCHIVE` (не переносить).

**DoD:** `Test-Path E:\opencode_harness\_LEGACY_ARCHIVE` → True; `E:\opencode_harness` → junction/reparse на архив; `git status` portable чистый.

**Роллбэк:** reparse→восстановление: удалить junction, переименовать `_LEGACY_ARCHIVE` обратно в канон-имя (см. §B5).

---

# B2 — LIVE-ЗЕРКАЛО (Частично: REQUIRES_USER_DECISION)

## B2-T1 — sync_to_live.py

**Файл:** `scripts/sync_to_live.py` (создать).
**Что:** синхронизация portable → live по группам. **8+2 групп** (добавить группу `mcp/`!):
```
scripts/ agents/ shared/ plugins/ skills/ config/ guard/ hooks/   ← 8 базовых
mcp/    ← группа 9 (добавить: mcp/launchers, mcp/*_server.py, mcp/harness_control_server.py)
templates/  ← группа 10 (coder-dom.yaml, adr-template, component-spec)
```
**Флаги:** `--harness-root`, `--prune`, `--import`, `--list-groups`.
**Конфиг:** `config/SYNC_WHITELIST.txt`.
**НЕ копировать:** `meta/`, `agent_gen/`, `writer-core/` (эти живут только в portable; writer-core — см. B2-T4).

**DoD:** `python scripts/sync_to_live.py --list-groups` → 10 групп; `--dry-run` (добавить флаг) → diff=0 после конвергенции.

## B2-T2 — Прогон + конвергенция (REQUIRES_USER_DECISION)

**Что:** первый прогон `sync_to_live.py` + конвергенция (повтор до diff=0).
**Бэкап live ОБЯЗАТЕЛЕН** перед первым прогоном.
**Судьба live shared/writer (RUD-5, решено A + W12):** импорт live `shared`+`writer` в portable + аудит цепочек (W12).

## B2-T3 — CONFIG_MERGE.md (BLOCKED_ON_EXPERIMENT → EXP-1b)

**Что:** документ `CONFIG_MERGE.md`: merge глобал (`~/.config/opencode/opencode.jsonc`) + проект (`.opencode/opencode.json`), склейка plugin-массивов. Подтверждается EXP-1b (после B1-T2).

## B2-T4 — Импорт scripts/writer + 7 лишних shared (REQUIRES_USER_DECISION)

**Что:** импортировать `scripts/writer/` + 7 лишних shared из live в portable. **`code-factory-process.md` ОБЯЗАТЕЛЬНО импортировать** (на него ссылается аудитор).

## B2-T5 — Систематизация 5 плагинов (REQUIRES_USER_DECISION, решено A + W12)

**Что:** 5 плагинов: arise 0.1.40, hiai 0.6.4, command-inject 1.3.1, envsitter-guard 0.0.4, token-tracker 1.7.1.
- `portable/plugins/package.json` — с пинами.
- live `package.json` → `{"private":true}`.
- **Активация (RUD-6, решено A):** junction `live\node_modules` ↔ `portable\plugins\node_modules` + циклы ревью/аудита по интеграции (W12).

---

# B3 — СЕССИИ/ENV (ГОТОВО, кроме B3-T2)

## B3-T1 — setup_env.ps1

**Что:** скрипт `scripts/setup_env.ps1`: User scope env ставится ТОЛЬКО при `OPENCODE_HARNESS_SETUP_USER=1` (защита от случайной порчи пользовательского окружения); `OPENCODE_BIN=shim`.
**DoD:** env-тест — `$env:OPENCODE_HARNESS_ROOT` = portable; `$env:OPENCODE_BIN` = путь к shim.

## B3-T2 — Shim opencode.cmd (REQUIRES_USER_DECISION, решено → W11)

**Что:** shim `opencode.cmd` → `bunx opencode-ai` (имя пакета — `opencode-ai`, НЕ `opencode`); PATH.
**Расширение (RUD-2):** НЕ просто shim — harness = универсальный агент с равнозначными API/GUI/CLI контурами → ветка W11 (см. `02_BRANCHES_W1_W13.md` §W11).
**Принудительный CWD=portable в shim** (P-CRIT-1): shim ставит CWD=portable, чтобы роутер работал из любого запуска.

## B3-T3 — CWD-валидация

**Что:** валидация CWD в ритуале старта 3 оркестраторов (code-orchestrator, research-orchestrator, writer-orchestrator) + preflight (`shared/route-preflight.md`).
**DoD:** preflight `harness_status` из чужого CWD → ошибка с инструкцией запуска из корня portable.

## B3-T4 — agents-data + .gitignore

**Что:**
1. Создать `agents-data/<agent>/{runs,memory,kanban,notes,artifacts,progress}` + `deliberation/`.
2. `.gitignore` — добавить паттерны (полный блок — `02_BRANCHES_W1_W13.md` §W1.4.2):
```
.runs/session_sync_index.json
.runs/session_deltas/
.runs/sleep_state/
.runs/sleep_markers/
.runs/progress/
.runs/verification/
.runs/*.json
!.runs/worker_m11.json
.meta_state/
.damage_basket/
.auditor_state/
.auditor_v2_state/
.planner_state/
.skills_state/
.tmp_l2.json
.l2_memory/
.kanban.db
.kanban.db-*
agents-data/**/*
.runs/deliberation/
scripts/meta/_trace_store.json
```
**DoD:** `git status --porcelain | grep -E "\.runs|\.kanban|\.meta_state|\.tmp_l2|\.l2_memory|deliberation"` → пусто; `git ls-files .runs/` → `.runs/worker_m11.json`.

## B3-T5 — Архив-политика

**Что:** `.kanban.db`, `.tmp_l2.json`, `.meta_state`, `.runs`, `.l2_memory` канона **НЕ переносятся**. Список исключений — в `03_ACCEPTANCE.md` §Инвентарь/архив.

---

# B4 — ТОЧЕЧНЫЕ (ГОТОВО)

## B4-T2 — Пути в агентах

**Что:** в агентах `.opencode/agent/*.md`:
- `.opencode/shared/` → `HARNESS_ROOT/shared`
- `references/global-kanban` → `kanban_report`
- `doc_guard` → `session_guard.py`

**DoD:** grep по агентам → нет `doc_guard`, есть `session_guard`; нет `references/global-kanban`.

## B4-T4 — Guard finalize: exit 5 TRIBUNAL_REQUIRED

**Что:** в `factory_ctl` guard finalize: при непустом `tribunal_required` без `tribunal_resolved` → exit 5 с кодом `TRIBUNAL_REQUIRED`.
**DoD:** `factory_ctl submit --state с tribunal_required=[] ` → exit 0; с `tribunal_required: [module]` без resolved → exit 5.

## B4-T5 — agent_loop (EXP-2 ВЫПОЛНЕН)

**Факты (не обсуждаются):**
- Парсер agent_loop строк 74-105 **КОРРЕКТЕН** (`parser_conclusion: FIELDS_DIFFER`, но парсер не требует переписывания). Внешний `type` = `step_finish` (подчёркивание), `reason/text/tool` — внутри `part`, `sessionID` — верхний уровень. `step-finish` с дефисом — `part.type`.
- Замер по БД (394 сессии): p50=16, p90=61, p95=147, max=1732; ≥60: 40 сессий, ≥100: 28; E2E-сессия ses_f032c5656ffegUekYXBkUFPVtm = 73 шага → **steps 60→120 ОБОСНОВАН**.

**Что:**
1. Fallback `OPENCODE_BIN`: `env → which → bunx-glob`.
2. Флаги: `--max-steps`, `--min-free-steps`, `--status-file`, `--ask-continue`, `WAVE_END`.
3. done-regex/file.
4. Флаги волн M6: `--check-continuation`.
5. `--attach` — см. W11-T3.
6. Docstring-примечание о формате; defensive fallback `e.get("reason") or e.get("part",{}).get("reason")`; БД-фолбэк sessionID при пустом stdout: `SELECT id FROM session WHERE directory LIKE '%opencode_harness_portable%' ORDER BY time_created DESC LIMIT 1`.

## B4-T6 — Хардкоды канона — 14 файлов

**Что:** glossary×7, guard.py, writer-core, sync_tech_debt, docs. Заменить на `HARNESS_ROOT`/`shared`. `config/tech_debt.json` пометить `(history)`.
**Дополнительно (P-MAJ-6):** `sync_tech_debt.py` — простановка `plan_block` в tech_debt.json (не вручную).
**DoD:** grep канон-путей (`doc_Opencode_agern|agern-new|E:\Documents`) по `scripts/*.py` → `NO_CANON_HARDCODES` (0 совпадений в исполняемых файлах).

## B4-T7 — compile_agents (перегенерация агентов)

**Что:** перегенерировать `.opencode/agent` через `compile_agents.py`.
**DoD:** `compile_agents.py --check` → `26/26 DIFF` пусто (все агенты в синхроне).

## B4-T8 — idle_tasks создаёт .tmp_l2.json

**Что:** `scripts/orchestration/idle_tasks.py --check` → создаёт `.tmp_l2.json` (промежуточный L2, подхватывается memory_circulator).
**DoD:** `Test-Path .tmp_l2.json` → True после запуска.

## B4-T9 — setup_env.sh

**Что:** bash-версия `scripts/setup_env.sh` (для Git-Bash).
**DoD:** bash-прогон → env-переменные выставлены корректно.

## B4-T10 — canon_loader + canon_search (POST-миграция, ветка W8)

**Что:** SQLite FTS5, `docs/canon` (45 файлов: 42 главы + appA/appB/appC — **НЕ 46**, см. P-MAJ-2), `.runs/canon_index/`, ch13=«хуки». Детали — `02_BRANCHES_W1_W13.md` §W8.
**DoD:** FTS5-запросы возвращают результаты; `(Get-ChildItem docs\canon -File).Count` → **45**.

## B4-T11 — test_e2e_orchestration.py + штраф solo

**Что:** `scripts/ci/test_e2e_orchestration.py` (статический аудит БД: part.data.tool, task-вызовы, factory_ctl submit). Штраф solo через переиспользование `self_edit` (НЕ плодить новую сущность): `delegation_score.py` ACTION_SCORE self_edit=-10, `character_sheet.py` XP_SELF_EDIT=-30. Детали — `03_ACCEPTANCE.md` §M2.
**DoD:** `--session <id> --expect-workers >=3` → PASS/FAIL по списку модулей без делегирования.

---

# B5 — МИГРАЦИЯ 8 ШАГОВ С РОЛЛБЭКОМ + E2E-ПРИЁМКА

**Цель:** перевод на portable как на единственный рабочий канон, с контролем отката на каждом шаге.

## 8 шагов (порядок исполнения)

| # | Шаг | Действие | Роллбэк |
|---|-----|----------|---------|
| **1** | **Бэкап** | Полный бэкап portable (git tag `pre-migration-<date>` + копия `.venv` + `tech_debt.json` снимок). Бэкап live ОБЯЗАТЕЛЕН (B2-T2). | — (точка восстановления) |
| **2** | **EXP-прогоны** | EXP-1b (после B1-T2), EXP-3, EXP-4, EXP-5 (протоколы — `03_ACCEPTANCE.md` §EXP). | повтор после исправления |
| **3** | **Блок 1** | B1-T1..T5 (venv, ядро, meta, shared, легализация). | `git revert` коммитов Блока 1 + `git checkout -- .opencode/opencode.json scripts/meta shared`; восстановление venv из бэкапа |
| **4** | **Блок 4** | B4-T2..T11 (кроме B4-T10 — POST). | `git revert` + перегенерация `compile_agents.py` (B4-T7) |
| **5** | **Блок 2** | B2-T1..T5 (sync_to_live, CONFIG_MERGE, writer, plugins). | удаление junction live\plugins; `sync_to_live.py --import` обратно из бэкапа |
| **6** | **Блок 3** | B3-T1..T5 (setup_env, shim, CWD, agents-data, архив). | снятие env-переменных (`env -u OPENCODE_HARNESS_ROOT`); удаление shim из PATH |
| **7** | **Ветки автоматики** | W1→W13 (см. `02_BRANCHES_W1_W13.md`), матрёшка M0–M6, E2E-приёмка (6 команд). | роллбэк веток — см. таблицы рисков в `02_BRANCHES_W1_W13.md` |
| **8** | **Легализация + E2E** | Заморозка канона → `_LEGACY_ARCHIVE` (reparse), финальный прогон E2E-приёмки + матрёшки + CI. | **reparse→восстановление:** удалить junction канона, переименовать `_LEGACY_ARCHIVE` обратно; `git revert` финальных коммитов |

**Роллбэк-протокол (общий):**
1. **reparse→восстановление:** `Remove-Item E:\opencode_harness` (junction), `Rename-Item E:\opencode_harness\_LEGACY_ARCHIVE E:\opencode_harness`.
2. **git revert:** `git revert <коммиты блока>` — блочно, от последнего к первому.
3. **Бэкап:** восстановление `.venv` и `tech_debt.json` из шага 1.
4. Если повреждена ветка — `git checkout feature/m11-daemon-integration -- <path>` (перенос файла из базы).

## E2E-приёмка (6 команд)

Полный протокол — `03_ACCEPTANCE.md` §E2E. Шаг 7 (API-проверка) — `02_BRANCHES_W1_W13.md` §W11-T5.

## CI-пайплайн в приёмке (P-MAJ-10)

**Что:** `.github/workflows/ci.yml` — проверить, что CI работает на portable (запуск pytest, компиляторов). Включить в B5-приёмку.
**DoD:** CI-прогон зелёный с `W1_SKIP_HOOKS=1` (риск-12).

## Тестовые наборы B5 (регрессионная база, P-CRIT-4/P-MAJ-10)

Прогнать перед легализацией (все в `tests/`, ~35 файлов — см. P-MIN-2):
```
tests/coder/*            (139 тестов bridge)
tests/test_agent_gen.py
tests/test_health_doctor.py
tests/test_module_porting.py
tests/test_route_duplication.py
tests/test_e2e_orchestration.py      (B4-T11/M2)
scripts/ci/test_integration.py
scripts/ci/test_mcp_servers.py
scripts/ci/test_chromadb.py
tests/test_health_monitor.py         (11/11 PASS, W7)
tests/fixtures/exp2_stepfinish.*     (фикстуры EXP-2)
```
Гейты: `pytest` + `compile_runtime.py --check` + `compile_agents --check` + `check_*` (7 гейтов: module_porting, plugin_registration, route_duplication, evidence_levels, health_canonical).

---

# ПРИЛОЖЕНИЕ: Инвентарь portable (P-MAJ-7) — судьбы сущностей, не упомянутых в мастер-плане

| Сущность | Судьба |
|----------|--------|
| `compatibility/opencode/1.18.30.json` | Предусловие B1-T2 (LIVE_CERTIFIED); проверить актуальность после миграции |
| `mcp/launchers/` (6 файлов) + `opencode_code_worker.py` | **Сохранить** (CLI-legacy диспатч, TD-D6); включить в sync-группу `mcp/` (B2-T1) и W12 |
| `scripts/jobs/job_ctl.py` | **Сохранить** (рантайм Job/Attempt); добавить в B1-структуру + W6 |
| `scripts/glossary/*` (15 файлов) | **Сохранить** (coder_dom_build/verify/stub_gate — используются pre-push W1); B4-T6 хардкоды + W1 |
| `scripts/research/*`, `scripts/researcher/*`, `scripts/writer-core/*` | **Вне скоупа миграции** (уже портированы); проверить их тесты в B5; НЕ удалять |
| `config/feature_flags.json`, `anti_patterns_catalog.yaml`, `agent_prompt_bindings.json`, `role_contracts/` | **Создать/перенести** (требования REFACTOR_REVIEW §4/§8, TD-I1/I3) — B1/W7/W12 |
| `templates/` (coder-dom.yaml, writer-dom-dissertation.yaml, adr-template, component-spec) | Сохранить; `coder-dom.yaml` — целевой артефакт Coder DOM (B4-T7/pre-push) |
| `tests/` (35 файлов) | Регрессионная база — см. список выше (B5) |
| `.github/workflows/ci.yml` | В B5-приёмку (CI на portable) |
| `MANIFEST.json`, `SHA256SUMS.txt` | Перегенерировать после миграции (`gen_manifest.py`) |
| `skills/opencode-current/*` (~130) | Вне скоупа (контент) |
| `ROADMAP_v1.1.md`, `AGENT_REPO_ACCESS.md`, `DEVELOPMENT.md` | Вне скоупа (инфо) |
| `docs/TRACKERS/TECH_DEBT_MASTER.md` | Синхронизировать с `tech_debt.json` (+ поле `plan_block`) |