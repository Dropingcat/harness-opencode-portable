# MASTER-ПЛАН: Миграция E:\opencode_harness_portable → LIVE-основная версия

**Версия:** 1.0
**Дата:** 2026-10-04
**Статус:** СПЕЦИФИКАЦИИ ГОТОВЫ, ИСПОЛНЕНИЕ НЕ НАЧАТО

---

## 1. Цель и принципы

Единый сводный документ миграции: сводит все спецификации, выработанные серией аудитов и планеров (блоки B1–B5, ветки автоматики W1–W13, эксперименты EXP-0..EXP-5, решения RUD-1..RUD-8, матрёшка M0..M6). Документ не создаёт новых фактов — только структурирует и связывает уже утверждённые.

Ключевые принципы:

- **portable = source of truth.** `E:\opencode_harness_portable` — канонический источник, из которого ведётся миграция.
- **Канон → legacy.** Старый `E:\opencode_harness` легализуется (переименование в `_LEGACY_ARCHIVE`, reparse point), прекращает быть рабочим деревом.
- **live = зеркало.** live-дерево поддерживается как зеркало portable через `sync_to_live.py`, а не редактируется вручную.
- **CWD-контракт.** Все оркестраторы и preflight валидируют CWD (запуск только из корректного корня harness).
- **Рантайм в .gitignore.** `dist/`, `venv/`, `.runs/`, `.meta_state/`, `.l2_memory/`, `.kanban.db`, `agents-data/**/*` и прочие рантайм-артефакты не попадают в git.
- **Никаких ссылок на канон в исполняемых файлах.** Хардкоды путей канона (14 файлов) устраняются; пути в агентах переносятся на `HARNESS_ROOT/shared`.

---

## 2. Карта блоков и веток

| Блок | Подзадачи | Зависимость | Статус |
|------|-----------|-------------|--------|
| **B1** Целевая структура | B1-T1..B1-T5 | — | ГОТОВО |
| **B2** live-зеркало | B2-T1..B2-T5 | B2-T2/T3/T4/T5 → REQUIRES_USER_DECISION / BLOCKED_ON_EXPERIMENT | Частично (см. статусы) |
| **B3** сессии/env | B3-T1..B3-T5 | B3-T2 → REQUIRES_USER_DECISION (RUD-2) | ГОТОВО (кроме B3-T2) |
| **B4** точечные | B4-T2, T4..T11 | B4-T5 → требует EXP-2; B4-T10 → POST-миграция (W8) | ГОТОВО |
| **B5** миграция 8 шагов | E2E-приёмка (6 команд) | B1–B4 | ГОТОВО |
| **W1** git-хуки | pre-commit / post-commit / pre-push, merge m5/m6 | — | ГОТОВО |
| **W2** оркестраторы | ритуалы старта/закрытия, kanban_report, idle_tasks, CWD-валидация | B3-T3 | ГОТОВО |
| **W3** субагенты/runner | gen_runners --check, runner = единственная точка CLI | EXP-0 | ГОТОВО |
| **W4** аудит/трибунал | guard finalize + tribunal_trigger.py | B4-T4 | ГОТОВО |
| **W5** роутер | harness_run → bundle → route, runtime_snapshot.json | — | ГОТОВО |
| **W6** координаторы | agent_loop + sync_to_live + memory_router | B4-T5 | ГОТОВО |
| **W7** мета-цикл | V-архитектура V1–V8, ночной прогон, L2→L3 | PLAN_W7_B1T3 | ГОТОВО |
| **W8** canon-поиск | B4-T10: SQLite FTS5, docs/canon 46 файлов | POST-миграция | ГОТОВО |
| **W9** peer-координация | peer_coordinator.py, W9-T1..T4 | T4 → BLOCKED (Слой 2 матрёшки) | ГОТОВО |
| **W10** модуль самообучения (RUD-3) | session_analyzer, lesson_extractor, skill_promoter, memory_integration, legacy_bootstrap | POST-миграция, ПОСЛЕ W8 (нужен canon_search) | СПЕЦИФИКАЦИЯ ГОТОВА |
| **W11** harness = универсальный агент (RUD-2) | shim → opencode-ai, mcp/harness_control_server, agent_loop --attach, serve-лаунчер | B3-T2 (shim) | СПЕЦИФИКАЦИЯ ГОТОВА |
| **W12** аудит интеграции цепочек (RUD-5/6) | реестр пустых интеграций (18), NEW-1..7 | после импорта shared (B1-T4/B2-T4) | СПЕЦИФИКАЦИЯ ГОТОВА |
| **W13** глубокий git-аудит снов (RUD-7) | sleep_git-расширение, sleep_report_check, meta_nightly, check_sleep_after | ПОСЛЕ M4 (матрёшка Слой 4) | СПЕЦИФИКАЦИЯ ГОТОВА |
| **Матрёшка** | M0..M6, test_e2e_matryoshka.py | Привязка к шагу 7 E2E | СПЕЦИФИКАЦИЯ ГОТОВА (M0-M5 ГОТОВО, M6 BLOCKED_ON_EXPERIMENT) |

---

## 3. Критические блокеры (факты)

1. **OPENCODE_BIN мёртвый.** Значение не используется/устарело; в B3-T1 заменяется на shim, в agent_loop (B4-T5) — fallback `env → which → bunx-glob`.
2. ~~Парсер agent_loop сломан~~ **Парсер agent_loop КОРРЕКТЕН.** `step-finish` с дефисом — это `part.type` (и `type` в БД `part.data`), а не внешний ключ stdout; внешний `type` = `step_finish` (подчёркивание), `reason/text/tool` — внутри `part`, `sessionID` — верхний уровень события. Подтверждено EXP-2: парсер строк 74-105 НЕ требует переписывания (`parser_conclusion: FIELDS_DIFFER`, но парсер корректен). Осталось: fallback `OPENCODE_BIN` (B3-T1/B4-T5), флаги волн (B4-T5), замер steps (EXP-2 выполнен, см. раздел 6).
3. **.venv рассинхрон 62/76.** portable venv содержит 62 пакета против 76 в каноне. Решение — whitelist-перенос (B1-T1), НЕ бинарное копирование.
4. **git-хуков нет.** В portable отсутствуют хуки; W1 создаёт их (pre-commit/post-commit/pre-push), `core.hooksPath`, gitignore + exception `.runs/worker_m11.json`.
5. **sleep_git / git_session_sync в ветках m5/m6.** Не слиты; W1: merge m5/m6 как перенос файлов (`git checkout <branch> -- path`, конфликтов нет), sleep_git/git_session_sync мержить как есть.
6. **portable несамостоятелен.** Плагин и MCP указывают на канон (опция B, Слой 0 матрёшки); для самостоятельности нужен EXP-5 (MCP на portable venv) и решение по активации плагинов (B2-T5).

---

## 4. Спецификации по блокам

### B1 — Целевая структура (единый документ миграции) — ГОТОВО

| ID | Что | Файлы/проверка | Статус |
|----|-----|----------------|--------|
| **B1-T1** | venv: portable 62 пакета vs канон 76. Whitelist: pytest, rich, pymorphy3, pymorphy3-dicts-ru, pypdf, DAWG2-Python, razdel, typer, colorama, Pygments, markdown-it-py, mdurl, annotated-doc, pluggy, iniconfig, shellingham, websockets; searXNG — по требованию. НЕ бинарно копировать. | pip freeze vs whitelist | ГОТОВО |
| **B1-T2** | Ядро: opencode.json строки 6/12/20/28/36 → portable `dist`+`venv`. `.Replace()` не regex; `WriteAllText` UTF-8 без BOM. 8 DoD. Детальная спецификация в сессии. | 8 DoD-проверок | ГОТОВО |
| **B1-T3** | Мета-комплект: 28 py, граф импортов без циклов, единственная внешняя зависимость pydantic. `.meta_state` канона НЕ переносить. | Детали в `PLAN_W7_B1T3_META_CYCLE_PORTING_2026-10-04.md` | ГОТОВО |
| **B1-T4** | shared: 9 недостающих файлов + новый `route-preflight.md`. | diff против канона | ГОТОВО |
| **B1-T5** | Легализация `E:\opencode_harness` → reparse point, переименование в `_LEGACY_ARCHIVE`. | reparse point, FS | ГОТОВО |

### B2 — live-зеркало

| ID | Что | Проверка | Статус |
|----|-----|----------|--------|
| **B2-T1** | `sync_to_live.py`: 8 групп `scripts/agents/shared/plugins/skills/config/guard/hooks`, флаги `--harness-root`, `--prune`, `--import`, `--list-groups`; `config/SYNC_WHITELIST.txt`. НЕ копировать `meta/agent_gen/writer-core`. | dry-run + --list-groups | ГОТОВО |
| **B2-T2** | Прогон + конвергенция. **Бэкап live ОБЯЗАТЕЛЕН.** | конвергенция diff=0 | REQUIRES_USER_DECISION (судьба live shared/writer) |
| **B2-T3** | `CONFIG_MERGE.md`: merge глобал+проект, склейка plugin-массивов. | подтвердить EXP-1b | BLOCKED_ON_EXPERIMENT |
| **B2-T4** | Импорт `scripts/writer/` + 7 лишних shared из live. `code-factory-process.md` ОБЯЗАТЕЛЬНО импортировать (на него ссылается аудитор). | наличие файлов | REQUIRES_USER_DECISION |
| **B2-T5** | Систематизация 5 плагинов: arise 0.1.40, hiai 0.6.4, command-inject 1.3.1, envsitter-guard 0.0.4, token-tracker 1.7.1. `portable/plugins/package.json` с пинами; live `package.json` → `{"private":true}`. Активация: junction A / file:// B. | пин-файл, пакеты | REQUIRES_USER_DECISION |

### B3 — Сессии/env — ГОТОВО (кроме B3-T2)

| ID | Что | Проверка | Статус |
|----|-----|----------|--------|
| **B3-T1** | `setup_env.ps1`: User scope только при `OPENCODE_HARNESS_SETUP_USER=1`; `OPENCODE_BIN=shim`. | env-тест | ГОТОВО |
| **B3-T2** | Shim `opencode.cmd` → bunx-кэш; PATH. | запуск из любого CWD | REQUIRES_USER_DECISION (RUD-2) |
| **B3-T3** | CWD-валидация в ритуале старта 3 оркестраторов + preflight. | preflight | ГОТОВО |
| **B3-T4** | `agents-data/<agent>/{runs,memory,kanban,notes,artifacts,progress}` + `deliberation/`. Правка `.gitignore`: `.runs/`, `.meta_state/`, `.tmp_l2.json`, `.l2_memory/`, `.kanban.db`, `agents-data/**/*`. | git status чист | ГОТОВО |
| **B3-T5** | Архив-политика: `.kanban.db`, `.tmp_l2.json`, `.meta_state`, `.runs`, `.l2_memory` канона НЕ переносятся. | список исключений | ГОТОВО |

### B4 — Точечные — ГОТОВО

| ID | Что | Проверка | Статус |
|----|-----|----------|--------|
| **B4-T2** | Пути в агентах: `.opencode/shared/` → `HARNESS_ROOT/shared`, `references/global-kanban` → `kanban_report`, `doc_guard` → `session_guard.py`. | grep по агентам | ГОТОВО |
| **B4-T4** | Guard finalize в factory_ctl: exit 5 `TRIBUNAL_REQUIRED` при непустом `tribunal_required` без `tribunal_resolved`. | exit code 5 | ГОТОВО |
| **B4-T5** | agent_loop: парсер КОРРЕКТЕН (см. блокер 2, подтверждён EXP-2); fallback `OPENCODE_BIN env→which→bunx-glob`; `--max-steps`/`--min-free-steps`/`--status-file`/`--ask-continue`/`WAVE_END`; done-regex/file; флаги волн `--check-continuation` (M6); замер steps по БД (EXP-2: 394 сессии, p50=16/p90=61/p95=147/max=1732); решение 60→120. | EXP-2 ВЫПОЛНЕН | ГОТОВО, требует флаги волн M6 |
| **B4-T6** | Хардкоды канона — 14 файлов: glossary×7, guard.py, writer-core, sync_tech_debt, docs. `tech_debt.json` пометить `(history)`. | grep канон-путей | ГОТОВО |
| **B4-T7** | Перегенерация `.opencode/agent` через `compile_agents.py`. | 26/26 DIFF | ГОТОВО |
| **B4-T8** | `idle_tasks` создаёт `.tmp_l2.json`. | файл создаётся | ГОТОВО |
| **B4-T9** | `setup_env.sh`. | bash-прогон | ГОТОВО |
| **B4-T10** | `canon_loader` + `canon_search`: SQLite FTS5, docs/canon 46 файлов, `.runs/canon_index/`, ch13=«хуки». Ветка W8. | FTS5-запросы | ГОТОВО, POST-миграция |
| **B4-T11** | `test_e2e_orchestration.py` + штраф solo в character_sheet. | тест | ГОТОВО |

### B5 — Миграция 8 шагов + E2E-приёмка — ГОТОВО

- 8 шагов миграции и E2E-приёмка из 6 команд. Подробный порядок — раздел 8.
- Матрёшка (M0..M6) привязывается к шагу 7 E2E-приёмки.

---

## 5. Спецификации по веткам автоматики W1–W13

| Ветка | Содержание | Детали | Статус |
|-------|-----------|--------|--------|
| **W1** | git-хуки. Merge m5/m6 как перенос файлов (конфликтов нет); sleep_git/git_session_sync мержить как есть. **pre-commit** = perfectionist warning-only + sleep_git `--dry-run`. **post-commit** = compile_agents `--check` WARN + health_check + session_sync `--no-commit`. **pre-push** = compile_agents `--check` БЛОК + coder-dom-verify. `core.hooksPath`; gitignore + exception `.runs/worker_m11.json`. | `PLAN_W1_GIT_HOOKS.md` (корень portable) | ГОТОВО |
| **W2** | Оркестраторы: ритуалы старта/закрытия, kanban_report, idle_tasks, CWD-валидация. | см. B3-T3, B4-T8 | ГОТОВО |
| **W3** | Субагенты/runner: `gen_runners --check`; runner = единственная точка CLI. | EXP-0 подтверждает | ГОТОВО |
| **W4** | Аудит/трибунал: B4-T4 guard + `tribunal_trigger.py` (новый: читает factory_state, review_fail_count, iteration_count → tribunal_required). | см. B4-T4 | ГОТОВО |
| **W5** | Роутер: `harness_run` → bundle → route; `runtime_snapshot.json` — источник правды. | EXP-4 | ГОТОВО |
| **W6** | Координаторы: `agent_loop` + `sync_to_live` + `memory_router`. | см. B4-T5, B2-T1 | ГОТОВО |
| **W7** | Мета-цикл: V-архитектура V1–V8, ночной прогон Task Scheduler (`meta_nightly.cmd` + XML), L2→L3. | `PLAN_W7_B1T3_META_CYCLE_PORTING_2026-10-04.md` (канон docs) | ГОТОВО |
| **W8** | canon-поиск: `canon_loader` + `canon_search` (B4-T10). | POST-миграция | ГОТОВО |
| **W9** | Peer-координация: `peer_coordinator.py` detect/zone/claim/check, `.runs/deliberation/`, max_rounds=2, timeout=10, эскалация оркестратору→question→AMBIGUOUS; conflict НЕ блокирует finalize (дефолт); arise/hiai НЕ движки (референс). W9-T1..T4: 3 ГОТОВО, 1 BLOCKED — зависит от Слоя 2 матрёшки. | W9-T1..T4 | ГОТОВО (T4 BLOCKED) |
| **W10** | Модуль самообучения (RUD-3): анализ завершённых блоков → принципы оптимальных сессий, навыки (полученные/НЕ полученные), паттерны скилов. Детерминированно (SQL+JSON, без LLM), read-only к источникам. Факты: opencode.db = **426 сессий** (portable 74, live 131, canon 4, other 217), 92 897 part, finish reasons: tool-calls 19155 / stop 940 / length 17 / error 1. Канон `.runs` = 29 json. Промоушен: memory_l3_policy (min_recurring 2), SKILL_MIN_COUNT=3, add_skill.py — официальный путь скилов. | W10-T1..T5 | СПЕЦИФИКАЦИЯ ГОТОВА |
| **W11** | Harness как универсальный агент (RUD-2): `opencode serve --port 4099` РАБОТАЕТ (headless HTTP, 401 basic-auth = жив) — это и есть API-контур, REST-обёртка НЕ нужна (fastapi/flask НЕТ в .venv, но uvicorn+starlette есть). Имя пакета `opencode-ai`, НЕ `opencode` (bunx opencode → 404); shim B3-T2 = вход CLI-контура → `bunx opencode-ai`. MCP: 4 сервера на канонный python — EXP-5 критичен. Desktop (Electron) запущен, использует ТУ ЖЕ БД opencode.db (426 сессий). | W11-T1..T6 | СПЕЦИФИКАЦИЯ ГОТОВА |
| **W12** | Аудит интеграции цепочек (RUD-5/6): реестр пустых интеграций (18 пунктов): 9 shared отсутствуют в portable (B1-T4/B2-T4), scripts/writer только в каноне (B2-T4), doc_guard→session_guard (B4-T2), unified_search не существует, harness_run/coder_run не в промптах (M1), agent_loop не вызывается, meta_daemon НЕТ в portable, хуков нет (W1/M4), env RESEARCH_*/WRITER_* не заданы, gk.report устаревшая сигнатура в code-orch:116/research-orch:137. NEW-1..7. | NEW-1..7 | СПЕЦИФИКАЦИЯ ГОТОВА |
| **W13** | Глубокий git-аудит снов (RUD-7): 3 критические дыры sleep_git.py: (1) конфликтная ветка при restore УДАЛЯЕТСЯ (статус ok в executed, не failed → branch -D; изменения не влиты — ПОТЕРЯ ДАННЫХ), (2) рефлексия отсутствует (нет диффов/изменений в отчёте, только статусы), (3) ночной прогон W7 идёт с `--simulate` — сны НЕ гитированы. Метод детекции: `git merge-tree --write-tree` (проверен на git 2.46, exit 1 = конфликт). | W13-T1..T4 | СПЕЦИФИКАЦИЯ ГОТОВА |

---

## 6. Эксперименты

| ID | Тема | Протокол/суть | Статус |
|----|------|---------------|--------|
| **EXP-0** | subagent как primary | subagent не primary → нужен runner | ВЫПОЛНЕН |
| **EXP-1a** | extends-механизм | extends отсутствует | ВЫПОЛНЕН |
| **EXP-1b** | merge плагинов (после B1-T2) | исходы A/B/C; подтверждает B2-T3 (склейка plugin-массивов) | ОЖИДАЕТ B1-T2 |
| **EXP-2** | формат step-finish | **ВЫПОЛНЕН.** stdout: внешний `type`=`step_finish` (подчёркивание), `reason/text/tool` внутри `part` (как и ищет парсер), `sessionID` — верхний уровень; `step-finish` с дефисом = `part.type` (и `type` в БД `part.data`). Парсер строк 74-105 НЕ требует переписывания (`parser_conclusion: FIELDS_DIFFER`, парсер корректен). sessionID в `part.data` БД ОТСУТСТВУЕТ (в БД — колонка `part.session_id`); fallback `SELECT id FROM session WHERE directory LIKE '%opencode_harness_portable%' ORDER BY time_created DESC LIMIT 1` подтверждён. Рекомендации: (а) docstring-примечание, (б) defensive fallback `e.get("reason") or e.get("part",{}).get("reason")`, (в) БД-фолбэк sessionID при пустом stdout. **Замер по БД (394 сессии): p50=16, p90=61, p95=147, max=1732; ≥60: 40 сессий, ≥100: 28; E2E-сессия ses_f032c5656ffegUekYXBkUFPVtm=73 шага** → цель steps=120 ОБОСНОВАНА данными (B4-T5). Файлы: `tests/fixtures/exp2_stepfinish.ndjson` (4565 Б), `tests/fixtures/exp2_stepfinish.json` (1213 Б), `C:\Temp\opencode\exp2_result.md`. | ВЫПОЛНЕН |
| **EXP-3** | writer-core на portable venv | проверка рантайма writer-core | НЕ ВЫПОЛНЕН |
| **EXP-4** | harness_run route | проверка маршрутизации (W5) | НЕ ВЫПОЛНЕН |
| **EXP-5** | MCP на portable venv | самостоятельность portable (блокер 6) | НЕ ВЫПОЛНЕН |

---

## 7. Открытые вопросы / REQUIRES_USER_DECISION

| ID | Вопрос | Дефолт | Статус |
|----|--------|--------|--------|
| **RUD-1** | Канон заморозить | ДА | **РЕШЕНО (A)** — заморозка канона → `_LEGACY_ARCHIVE` (архивная версия), переход на portable после миграции |
| **RUD-2** | Shim opencode (B3-T2) | ДА | **РЕШЕНО (расширено)** — НЕ просто shim: harness = универсальный агент с равнозначными API/GUI/CLI контурами → ветка W11 |
| **RUD-3** | Данные канона не переносить | ДА | **РЕШЕНО (расширено → W10)** — данные канона — в легаси-архив как учебный материал; отдельный модуль самообучения W10 анализирует завершённые блоки → навыки/скилы |
| **RUD-4** | Плагин в глобальный — НЕТ; матрёшка Слой 0 = опция B | НЕТ | **РЕШЕНО (A)** — плагин это легаси; глобальная регистрация не нужна |
| **RUD-5** (новый) | Судьба live shared/writer (B2-T2) | — | **РЕШЕНО (A + W12)** — импорт live shared+writer в portable + аудит интеграции цепочек → ветка W12 |
| **RUD-6** (новый) | Вариант активации плагинов A (junction) / B (file://) (B2-T5) | — | **РЕШЕНО (A)** — junction live\node_modules ↔ portable\plugins\node_modules + циклы ревью/аудита по интеграции → W12 |
| **RUD-7** (новый) | pre-commit sleep_git dry-run vs полный | dry-run | **РЕШЕНО (A + W13)** — pre-commit dry-run + глубокий git-аудит снов: гитификация, рефлексия, траблы слияний → ветка W13 |
| **RUD-8** (новый) | E2E-01..07 зарегистрировать в tech_debt.json | ДА | **РЕШЕНО (A)** — уже зарегистрированы: `config/tech_debt.json` строки 4288-4455, status: open, sunset 2026-10-16. НЕ перерегистрировать. |

---

## 8. Порядок исполнения (критический путь)

1. **B1-T1..B1-T5** — целевая структура (venv-whitelist, ядро opencode.json, мета-комплект, shared, легализация канона).
2. **B4** — точечные правки (пути B4-T2, guard B4-T4, agent_loop B4-T5 после EXP-2, хардкоды B4-T6, compile_agents B4-T7, idle_tasks B4-T8, setup_env.sh B4-T9, canon B4-T10 POST-миграция, E2E-тест B4-T11).
3. **B3** — сессии/env (setup_env.ps1 B3-T1, shim B3-T2 по RUD-2, CWD B3-T3, agents-data B3-T4, архив-политика B3-T5).
4. **W11** — harness как универсальный агент (после B3-T2): shim → opencode-ai, mcp/harness_control_server, agent_loop --attach, serve-лаунчер. Приоритет HIGH.
5. **Ветки W1→W2→W3→W4→W5→W6→W9→W7→W8** — автоматика (хуки → оркестраторы → субагенты → аудит → роутер → координаторы → peer → мета-цикл → canon-поиск).
6. **W12** — аудит интеграции цепочек (после импорта shared B1-T4/B2-T4): закрывает 80% пустых интеграций. Приоритет HIGH.
7. **B5 — миграция 8 шагов** + E2E-приёмка (6 команд).
8. **Матрёшка** — merge веток e2e-s0..s6, правило «слой N после PASS N-1», стоп на первом FAIL; привязка к шагу 7 E2E. **СПЕЦИФИКАЦИЯ ГОТОВА** (детали — подраздел «Блок 6 (матрёшка) — детали» ниже). Статус слоёв: M0-M5 ГОТОВО, M6 BLOCKED_ON_EXPERIMENT (EXP-2).
9. **W13** — глубокий git-аудит снов (ПОСЛЕ M4): sleep_git-расширение, sleep_report_check, meta_nightly, check_sleep_after. Приоритет MEDIUM.
10. **W10** — модуль самообучения (в конец, ПОСЛЕ W8): session_analyzer, lesson_extractor, skill_promoter, memory_integration, legacy_bootstrap. Приоритет POST-миграция.

### Блок 6 (матрёшка) — детали

Спецификация: `docs/PLAN_E2E_MATRYOSHKA.md`, основа веток — `feature/m11-daemon-integration`.

| Слой | E2E-задача | Что | Статус |
|------|-----------|-----|--------|
| **M0** | E2E-06 | **M0-a** (якорь HARNESS_ROOT, junction shared, env guard, перенос 2 капсул `orchestration-thread-process.md` + `code-factory-process.md`, `path_resolution_map`, project-scope `opencode.json`) — ГОТОВО. **M0-b** (глобальный плагин) — REQUIRES_USER_DECISION RUD-4, дефолт НЕТ. | ГОТОВО |
| **M1** | E2E-02 | Роутер в промпте + route preflight + `shared/route-preflight.md`. **ИМЯ ТУЛА: `coder_run`, НЕ `coder_router_coder_run`** (`mcp/coder_router_server.py:216`). | ГОТОВО |
| **M2** | E2E-01 | `scripts/ci/test_e2e_orchestration.py` (статический аудит БД), обязательный `factory_ctl submit`, **штраф solo через переиспользование `self_edit`** (`delegation_score.py` ACTION_SCORE self_edit=-10, `character_sheet.py` XP_SELF_EDIT=-30) — не плодить новую сущность. | ГОТОВО |
| **M3** | E2E-04 | `scripts/code-factory/tribunal_trigger.py` (тонкая CLI-обёртка над `_convergence_view`, НЕ дублирует редьюсер), child-сессия code-auditor. | ГОТОВО |
| **M4** | E2E-03 | Перенос m5/m6 + хуки (по `PLAN_W1_GIT_HOOKS.md`), `core.hooksPath`. | ГОТОВО |
| **M5** | E2E-07 | Gate-пункты в `orchestration-thread-process.md`, `--check-rituals`. | ГОТОВО |
| **M6** | E2E-05 | Каркас ГОТОВО (волновой рубеж, agent_loop флаги, `--check-continuation`), steps 60→120 — **BLOCKED_ON_EXPERIMENT до EXP-2**. | BLOCKED_ON_EXPERIMENT |

**test_e2e_matryoshka.py**: CLI `[--only N] [--skip N] [--json] [--session ID] [--expect-workers N] [--min-steps N] [--runs-dir DIR]`, exit 0/1/2 (2 = BLOCKED слой), JSON-отчёт в `.runs/e2e_matryoshka/`, оборачивает 6 команд E2E-приёмки (не заменяет).

**Merge-порядок**: ветки e2e-s0..s6 от базы `feature/m11-daemon-integration`, правило «слой N после PASS N-1», merge m5/m6 = перенос файлов `git checkout <br> -- path`.

**Риск-12**: `W1_SKIP_HOOKS` для CI.

---

### W10 — Модуль самообучения (по RUD-3)

- **Цель:** анализ завершённых блоков задач → принципы оптимальных сессий, навыки (полученные/НЕ полученные), паттерны скилов. Детерминированно (SQL+JSON, без LLM). Read-only к источникам.
- **Факты аудита:** opencode.db = **426 сессий** (не 413!; portable 74, live 131, canon 4, other 217), 92 897 part, finish reasons: tool-calls 19155 / stop 940 / length 17 / error 1. Канон `.runs` = 29 json.
- **Промоушен:** memory_l3_policy (min_recurring 2), SKILL_MIN_COUNT=3, add_skill.py — официальный путь скилов.
- **Формат урока (JSON):** `{lesson_id, kind (interaction_principle/skill_used/skill_missing/stuck_escape), pattern, success_metric, skill_candidate, canon_fragment, lesson_text, evidence_refs, admissions, status}`.
- **Подзадачи:**
  - **W10-T1** `session_analyzer.py` (SQL-метрики) — **M**
  - **W10-T2** `lesson_extractor.py` (кластеризация tool-паттернов, статистика) — **L**
  - **W10-T3** `skill_promoter.py` (гейты L3-политики, add_skill.py --dry-run) — **L**
  - **W10-T4** `memory_integration.py` (L2/L3, canon через W8) — **M**
  - **W10-T5** `legacy_bootstrap.py` (однократный прогон по канону) — **L**
- **Приоритет:** POST-миграция, ПОСЛЕ W8 (нужен canon_search). **НЕ дублирует** W7 (не прокачивает скилы, не пишет legacy) / W8 (не строит FTS5) / W9 (не участник deliberation).

### W11 — Harness как универсальный агент (по RUD-2)

- **Ключевые факты аудита:**
  - `opencode serve --port 4099` **РАБОТАЕТ** (headless HTTP, 401 basic-auth = жив) — это и есть API-контур, НЕ нужна своя REST-обёртка (fastapi/flask НЕТ в .venv, но uvicorn+starlette есть).
  - **Имя пакета: `opencode-ai`, НЕ `opencode`** (bunx opencode → 404). Shim B3-T2 = вход CLI-контура → `bunx opencode-ai`.
  - MCP: 4 сервера указывают на **канонный** python — EXP-5 критичен. Desktop (Electron) запущен, использует ТУ ЖЕ БД opencode.db (426 сессий).
- **Подзадачи:**
  - **W11-T1** shim → opencode-ai — **S**
  - **W11-T2** `mcp/harness_control_server.py` (run_agent/get_status/submit) — **M**
  - **W11-T3** agent_loop `--attach` — **M**
  - **W11-T4** serve-лаунчер + `OPENCODE_SERVER_PASSWORD` — **M**
  - **W11-T5** E2E-шаг 7 API-проверка — **S**
  - **W11-T6** MCP python → portable (входит в EXP-5) — **S**
- **Приоритет:** HIGH.
- **JSON-артефакт:** `docs/AUDIT_RUD2_UNIVERSAL_AGENT_2026-10-04.json`.

### W12 — Аудит интеграции цепочек (по RUD-5/6)

- **Реестр пустых интеграций (18 пунктов):** 9 shared отсутствуют в portable (B1-T4/B2-T4), scripts/writer только в каноне (B2-T4), doc_guard→session_guard (B4-T2), unified_search не существует, harness_run/coder_run не в промптах (M1), agent_loop не вызывается, meta_daemon НЕТ в portable, хуков нет (W1/M4), env `RESEARCH_*`/`WRITER_*` не заданы, gk.report устаревшая сигнатура в code-orch:116/research-orch:137.
- **NEW-1..7 (новые подзадачи):**
  - **NEW-1** unified_search skill
  - **NEW-2** memory L3 в writing-закрытии
  - **NEW-3** writer → tribunal-judge для факт-споров
  - **NEW-4** writer-редьюсер (state machine)
  - **NEW-5** убрать gk.report
  - **NEW-6** env-контракт research
  - **NEW-7** env-контракт writer
- **Расхождения циклов оркестратор vs писатель:** едины ритуал старта/kanban/«Где я»; различия — память L3 (у писателя НЕТ), нет state machine у писателя, нет трибунала для факт-споров.
- **Приоритет:** HIGH (после импорта shared закрывает 80% пустых интеграций).

### W13 — Глубокий git-аудит снов (по RUD-7)

- **3 критические дыры `sleep_git.py`:**
  1. Конфликтная ветка при restore УДАЛЯЕТСЯ (статус ok в executed, не failed → branch -D; изменения не влиты — **ПОТЕРЯ ДАННЫХ**)
  2. Рефлексия отсутствует (нет диффов/изменений в отчёте, только статусы)
  3. Ночной прогон W7 идёт с `--simulate` — сны НЕ гитированы
- **Метод детекции конфликтов:** `git merge-tree --write-tree <target> <branch>` (проверен на git 2.46, exit 1 = конфликт) — сухой pre-check без рабочей копии.
- **Подзадачи:**
  - **W13-T1** расширение sleep_git.py (диффы веток, false_ready детекция, keep конфликтных веток, merge-tree pre-check) — **L**
  - **W13-T2** `sleep_report_check.py` + json-schema отчёта — **S**
  - **W13-T3** убрать `--simulate` из meta_nightly.cmd, отчёты в `.runs/sleep_reports/`, уроки конфликтов→L2 — **M**
  - **W13-T4** `check_sleep_after.py` (10 проверок) — **S**
- **Приоритет:** MEDIUM, ПОСЛЕ M4 (матрёшка Слой 4) — ветка `feature/w13-deep-sleep-git`.

---

## 9. Ссылки на детальные планы

- `PLAN_W1_GIT_HOOKS.md` — git-хуки (корень portable), ветка W1.
- `PLAN_W7_B1T3_META_CYCLE_PORTING_2026-10-04.md` — мета-цикл/мета-комплект, ветка W7 (канон docs).
- `AUDIT_RUD2_UNIVERSAL_AGENT_2026-10-04.json` — аудит RUD-2, ветка W11 (docs).
- `PLAN_MASTER_MIGRATION.md` — настоящий документ (сводный).
- Tool-output файлы: результаты аудитов/планеров, послужившие источниками фактов (в т.ч. замеры БД EXP-2: 394 сессии для B4-T5/M6, таблицы 60→120, протоколы EXP-0/EXP-1a, `tests/fixtures/exp2_stepfinish.*`, `C:\Temp\opencode\exp2_result.md`).
- W10/W12/W13 — спецификации в выводе сессий (tool-output): аналитика сессий/самообучение, реестр пустых интеграций + NEW-1..7, глубокий git-аудит снов sleep_git.
- `tech_debt.json` — реестр тех-долга; B4-T6 помечает `(history)`; E2E-01..07 УЖЕ зарегистрированы (строки 4288-4455, status: open, sunset 2026-10-16) — RUD-8 выполнен.