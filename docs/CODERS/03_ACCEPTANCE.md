# ПРИЁМКА: МАТРЁШКА M0–M6, ЭКСПЕРИМЕНТЫ, E2E, КРИТЕРИИ ГОТОВНОСТИ ФАБРИКИ

**Дата:** 2026-10-05
**CWD:** `E:\opencode_harness_portable`
**Python:** `.venv\Scripts\python.exe`

> Назначение: детерминированные чеки готовности. Всё проверяется командами, без LLM. Ни один слой/эксперимент не считается выполненным без PASS его проверок.

---

## 1. МАТРЁШКА M0–M6

**Принцип:** слои от ядра к оболочке. Слой N нельзя проверять, пока не пройден N-1. Прогон — `test_e2e_matryoshka.py`, стоп на первом FAIL.
**Ветки:** e2e-s0..s6 от базы `feature/m11-daemon-integration`. Merge-правило: слой N после PASS N-1. Merge m5/m6 = перенос файлов `git checkout <br> -- path`.

| Слой | E2E-задача | Что | Статус |
|------|-----------|-----|--------|
| **M0** | E2E-06 | **M0-a** (якорь HARNESS_ROOT, junction shared, env guard, перенос 2 капсул `orchestration-thread-process.md` + `code-factory-process.md`, `path_resolution_map`, project-scope `opencode.json`) — ГОТОВО. **M0-b** (глобальный плагин) — RUD-4, дефолт НЕТ. | ГОТОВО |
| **M1** | E2E-02 | Роутер в промпте + route preflight + `shared/route-preflight.md`. **Имя тула: `coder_run`.** | ГОТОВО |
| **M2** | E2E-01 | `scripts/ci/test_e2e_orchestration.py` (статический аудит БД), обязательный `factory_ctl submit`, штраф solo через `self_edit` (`delegation_score.py` self_edit=-10, `character_sheet.py` XP_SELF_EDIT=-30). | ГОТОВО |
| **M3** | E2E-04 | `scripts/code-factory/tribunal_trigger.py` (обёртка над `_convergence_view`), child-сессия code-auditor. | ГОТОВО |
| **M4** | E2E-03 | Перенос m5/m6 + хуки (`PLAN_W1_GIT_HOOKS.md`), `core.hooksPath`. | ГОТОВО |
| **M5** | E2E-07 | Gate-пункты в `orchestration-thread-process.md`, `--check-rituals`. | ГОТОВО |
| **M6** | E2E-05 | Волновой рубеж, agent_loop флаги, `--check-continuation`, steps **60→120**. **BLOCKED СНЯТ** — EXP-2 выполнен (замер по БД: 394 сессии, p50=16/p90=61/p95=147/max=1732; E2E-сессия = 73 шага; ≥60: 40 сессий, ≥100: 28 → steps=120 обоснован). | **ГОТОВО** (снять BLOCKED) |

### test_e2e_matryoshka.py

**CLI:** `[--only N] [--skip N] [--json] [--session ID] [--expect-workers N] [--min-steps N] [--runs-dir DIR]`
**exit:** `0` = все слои PASS; `1` = FAIL слоя; `2` = BLOCKED слой.
**JSON-отчёт:** в `.runs/e2e_matryoshka/`.
**Оборачивает 6 команд E2E-приёмки (не заменяет их).**

**Детерминированные чеки по слоям (из `PLAN_E2E_MATRYOSHKA.md`):**

| Слой | Чек (команда → результат) |
|------|---------------------------|
| **M0** | `echo $env:OPENCODE_HARNESS_ROOT` → portable; `Test-Path "$env:OPENCODE_HARNESS_ROOT\shared\orchestration-thread-process.md"` → True; `python -c "import json; c=json.load(open(r'config\path_resolution_map.json')); print('portable' in str(c))"` → True |
| **M1** | в E2E-сессии: `tool=harness_status` → route=code-implementation; `PROGRESS.md` содержит `ROUTE: code-implementation` |
| **M2** | `python scripts/ci/test_e2e_orchestration.py --session <id> --expect-workers >=3` → PASS: task×worker≥3, task×reviewer≥3, task×tester≥3, factory_ctl submit ≥3; `ls .runs/worker_m*.json` → есть |
| **M3** | `python scripts/code-factory/tribunal_trigger.py --state .runs/factory_state.json` → `tribunal_required: [module]` при 2+ раундах REWORK |
| **M4** | `Get-ChildItem .git/hooks` → pre-commit, post-commit (не только LFS); `git commit -m "test"` → `[w1] sleep_git`, `[w1] perfectionist` |
| **M5** | `python scripts/ci/test_e2e_orchestration.py --session <id> --check-rituals` → PASS: kanban_report в конце, memory add, todo completed == факт |
| **M6** | `python scripts/ci/test_e2e_orchestration.py --session <id> --check-continuation` → PASS: продолжение в той же сессии (новые parts) ИЛИ child-session с parent_id=<id> |

**Прогон:**
```
.venv\Scripts\python.exe scripts/ci/test_e2e_matryoshka.py --session <id> --expect-workers 3 --json
# → S0 PASS → S1 PASS → ... → S6 PASS → ✅ E2E READY (exit 0)
# → стоп на FAIL с номером слоя (exit 1); BLOCKED слой — exit 2
```

---

## 2. ЭКСПЕРИМЕНТЫ EXP-0..5

| ID | Тема | Статус | В критическом пути |
|----|------|--------|--------------------|
| **EXP-0** | subagent как primary (subagent не primary → нужен runner) | **ВЫПОЛНЕН** | подтверждает W3 |
| **EXP-1a** | extends-механизм (отсутствует) | **ВЫПОЛНЕН** | — |
| **EXP-1b** | merge плагинов (после B1-T2) — исходы A/B/C; подтверждает B2-T3 | **ПРОТОКОЛ — встроить в критический путь** (шаг B5-2) | B2-T3 |
| **EXP-2** | формат step-finish | **ВЫПОЛНЕН** (394 сессии по БД, парсер корректен, steps 60→120) | B4-T5/M6 |
| **EXP-3** | writer-core на portable venv | **ПРОТОКОЛ — встроить в критический путь** (шаг B5-2, до W11) | W11 |
| **EXP-4** | harness_run route | **ПРОТОКОЛ — встроить в критический путь** (шаг B5-2, до W5) | W5 |
| **EXP-5** | MCP на portable venv (самостоятельность portable) | **ПРОТОКОЛ — встроить в критический путь** (шаг B5-2, до W11) | W11-T6 |

> **EXP-1b/3/4/5 — протоколы** (спеки готовы, исполнение — на кодерe в Транше A, шаг A8 / B5-2). EXP-0/1a/2 — выполнены (статусы ВЫПОЛНЕН).

### Протоколы для исполнения

**EXP-1b (merge плагинов):** после B1-T2 прогнать слияние глобального + проектного `opencode.json`, проверить склейку plugin-массивов. Исходы A (глобал приоритет) / B (проект приоритет) / C (оба). Результат фиксируется в `config/CONFIG_MERGE.md` (B2-T3).

**EXP-3 (writer-core на portable venv):**
```
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, r'scripts\writer-core'); import <модуль writer-core>; print('WRITER_CORE_OK')"
# → WRITER_CORE_OK (рантайм writer-core работает на portable venv)
```

**EXP-4 (harness_run route):**
```
# E2E-сессия: tool=harness_run (route=code-implementation) → bundle=[tools]
# .venv\Scripts\python.exe scripts/router/resolve_route.py --task "..."  → маршрут резолвится
```

**EXP-5 (MCP на portable venv):** переключить 4 mcp-сервера `.opencode/opencode.json` на `.venv\Scripts\python.exe` (W11-T6) и проверить, что все подняты:
```
# в логе opencode: mcp coder_router/academic_search/doc_extract/searxng_search — connected (portable python)
```

---

## 3. E2E-ПРИЁМКА (6 команд + шаг 7)

**Источник:** `PLAN_E2E_MATRYOSHKA.md`. Команды — детерминированные, без LLM. Оборачиваются в `test_e2e_matryoshka.py`, но **не заменяются** им.

| # | Команда | Ожидаемый результат |
|---|---------|---------------------|
| **1** | `Test-Path E:\opencode_harness_portable\HARNESS_ROOT`; `Test-Path ~\.config\opencode\shared` (junction) | True; junction существует |
| **2** | `Test-Path shared\route-preflight.md`; `Test-Path shared\code-factory-process.md`; `Test-Path shared\orchestration-thread-process.md` | True (все 3 капсулы) |
| **3** | `python scripts/ci/test_e2e_orchestration.py --session <id> --expect-workers 3` | PASS (M2) |
| **4** | `python scripts/code-factory/tribunal_trigger.py --state .runs/factory_state.json` | `tribunal_required: [...]` корректно |
| **5** | `git config --get core.hooksPath`; `ls hooks/` | `hooks`; `pre-commit post-commit pre-push hook_utils.sh coder-dom-verify.sh` (M4) |
| **6** | `python scripts/ci/test_e2e_orchestration.py --session <id> --check-rituals` | PASS (M5) |
| **7** | **API-проверка (W11-T5):** `start serve (порт 4099) → run --attach smoke → HTTP 200/401-auth + session виден в shared БД` | serve жив, сессия в общей БД |

**Приёмка завершена, когда:** все 7 шагов PASS + `test_e2e_matryoshka.py` → `E2E READY` (exit 0).

---

## 4. КРИТЕРИИ ГОТОВНОСТИ ФАБРИКИ (итоговая проверка «работающая фабрика агентов»)

> Выполнять ПОСЛЕ Транша C (B5 + матрёшка + E2E). Все 12 — команды, без LLM.

| # | Критерий | Проверка |
|---|----------|----------|
| 1 | **Ядро на portable:** `opencode.json` без канон-ссылок; venv whitelist установлен | grep `doc_Opencode_agern` в `.opencode/opencode.json` → пусто; `pip show pymorphy3 pypdf` → есть |
| 2 | **Контуры равнозначны (W11):** CLI shim + API serve + GUI Desktop используют ту же БД | `opencode.cmd --version` → не 404; serve → 401; Desktop → та же opencode.db |
| 3 | **Фабрика принуждает:** диспатч через task обязателен, solo штрафуется | `test_e2e_orchestration.py --expect-workers 3` → PASS; SOLO_MODE виден в отчёте |
| 4 | **Роутер в промптах (M1):** `harness_run`/`harness_status`/`coder_run` доступны | системный промпт code-orchestrator содержит все 3 тула |
| 5 | **Хуки активны (M4/W1):** pre-commit/post-commit/pre-push, `core.hooksPath=hooks` | `git config --get core.hooksPath` → hooks; коммит → `[w1]` в выводе |
| 6 | **Мета-цикл жив (W7):** `meta_daemon --once` работает, HP/veto, L2→L3 | JSON `{"sleep": false, "hp": N}`; `idle_tasks --check` → кандидаты |
| 7 | **Canon-поиск (W8):** FTS5 по docs/canon | `canon_search --query "хуки"` → результаты; `(Get-ChildItem docs\canon -File).Count` → 45 |
| 8 | **Память (W6/W10):** memory_router работает, уроки в L2/L3 | `switch` подтягивает namespace; `.l2_memory/<agent>.json` создаётся |
| 9 | **Сон гитирован (W13):** ночной прогон `simulated:false`, конфликтные ветки keep | `check_sleep_after.py` → 10/10 PASS |
| 10 | **CI зелёный на portable (B5):** `.github/workflows/ci.yml` + тестовые наборы | `pytest` + `compile_agents --check` + `compile_runtime.py --check` + 7 гейтов → PASS |
| 11 | **Канон легализован (B1-T5):** `_LEGACY_ARCHIVE` reparse point | `Test-Path E:\opencode_harness\_LEGACY_ARCHIVE` → True |
| 12 | **Рантайм вне git (B3-T4/W1):** `.runs/`, `.meta_state/`, `.kanban.db` не трекаются | `git status --porcelain | grep -E "\.runs|\.kanban"` → пусто |

**Итоговая формула готовности:**
```
E2E READY (test_e2e_matryoshka.py, exit 0)
+ 12/12 критериев PASS
+ EXP-1b/3/4/5 выполнены
= ФАБРИКА АГЕНТОВ РАБОТАЕТ
```

---

## 5. Привязка приёмки к критическому пути

| Транш/шаг | Приёмка |
|-----------|---------|
| Транш A (A1-A9) | EXP-1b/3/4/5 (протоколы); M0-a чек |
| Транш B (B1-B7) | W1..W13 DoD; матрёшка M1-M4 |
| Транш C (C1-C5) | B5 8 шагов + E2E 6 команд + шаг 7; матрёшка M5-M6; 12 критериев |

**Финальный прогон (после легализации):** `test_e2e_matryoshka.py --json` + 6 команд E2E + 12 критериев → все PASS → фабрика передана в эксплуатацию.