# PLAN: Внедрение E2E-обвязки «матрешкой»

Дата: 2026-10-02
Контур: coder → code-factory → E2E (ses_f032c5656ffegUekYXBkUFPVtm)
Ветка-основа: `feature/m11-daemon-integration`

## Принцип «матрёшки»

Внедрение идёт слоями от ядра к оболочке. Каждый слой вложен в следующий:
нельзя проверять слой N, пока не пройден N-1. Проверка слоя N = детерминированный
E2E-сценарий, который прогоняет ВСЕ внутренние слои + проверяет новый внешний.
Так ошибка локализуется на границе ровно одного слоя.

```
┌─────────────────────────────────────────────┐  Слой 6  E2E-05 лимиты/продолжение
│ ┌─────────────────────────────────────────┐ │  Слой 5  E2E-07 ритуалы
│ │ ┌─────────────────────────────────────┐ │ │  Слой 4  E2E-03 циклы/хуки
│ │ │ ┌─────────────────────────────────┐ │ │ │  Слой 3  E2E-04 аудитор/трибунал
│ │ │ │ ┌─────────────────────────────┐ │ │ │ │  Слой 2  E2E-01 принуждение к фабрике
│ │ │ │ │ ┌─────────────────────────┐ │ │ │ │ │  Слой 1  E2E-02 роутер/плагин
│ │ │ │ │ │ ┌─────────────────────┐ │ │ │ │ │ │  Слой 0  E2E-06 источник конфигурации
│ │ │ │ │ │ │                     │ │ │ │ │ │ │
└─┴─┴─┴─┴─┴─┴─────────────────────┴─┴─┴─┴─┴─┴─┘
```

## Слои ↔ техдолги ↔ артефакты

| Слой | Техдолг | Артефакты внедрения | Файл-результат |
|---|---|---|---|
| 0 | E2E-06 | единый источник конфигурации | `docs/DIAGNOSTICS_E2E.md`, `deploy/bootstrap.ps1` |
| 1 | E2E-02 | роутер в системном промпте + route preflight | `.opencode/agent/code-orchestrator.md`, `shared/route-preflight.md` |
| 2 | E2E-01 | обязательный диспатч через task + factory_ctl | `scripts/ci/test_e2e_orchestration.py` |
| 3 | E2E-04 | трибунал/аудитор при конфликтах | `scripts/code-factory/tribunal_trigger.py` |
| 4 | E2E-03 | git-хуки + sleep-циклы в рабочем проекте | `hooks/pre-commit`, `hooks/post-commit` |
| 5 | E2E-07 | доведение ритуалов старта/закрытия | `shared/orchestration-thread-process.md` |
| 6 | E2E-05 | волны/авто-продолжение без обрыва | `scripts/tools/agent_loop.py`, `steps` в agent |

---

## Слой 0 — E2E-06: единый источник конфигурации (ЯДРО)

**Проблема:** сессия запущена вне harness-дерева, `OPENCODE_HARNESS_ROOT` → канон, а
инструменты в portable; плагин только в `.opencode/opencode.json` portable.

**Архитектура:**
1. Ввести понятие **harness-якоря**: файл `E:\opencode_harness_portable\HARNESS_ROOT` (метка-якорь).
2. `deploy/bootstrap.ps1` — устанавливает глобальную регистрацию плагина:
   - дописывает `file:///E:/.../packages/opencode-harness-plugin/dist/index.js` в `~/.config/opencode/opencode.jsonc` (plugin);
   - создаёт junction `~/.config/opencode/shared` ↔ `E:\opencode_harness_portable\shared` (если отсутствует).
3. `OPENCODE_HARNESS_ROOT` выставляется в `Machine`/`User` env = `E:\opencode_harness_portable`.
4. Обновить `config/path_resolution_map.json` — зафиксировать portable как единственный источник.

**Проверка слоя 0 (детерминированная):**
```
echo $env:OPENCODE_HARNESS_ROOT          # → E:\opencode_harness_portable
Test-Path "$env:OPENCODE_HARNESS_ROOT\shared\orchestration-thread-process.md"  # → True
Test-Path "$env:USERPROFILE\.config\opencode\opencode.jsonc"  # содержит file:///.../harness-plugin/dist/index.js
python -c "import json; c=json.load(open(r'E:\opencode_harness_portable\config\path_resolution_map.json')); print('portable' in str(c))"  # → True
```
**Acceptance:** любой `opencode run` из любой папки загружает плагин и видит shared/scripts portable.

---

## Слой 1 — E2E-02: роутер цепляется на старте

**Архитектура:**
1. `.opencode/agent/code-orchestrator.md` → «Что у тебя есть» добавить:
   `harness_run`, `harness_status`, `coder_router_coder_run`.
2. Ритуал старта → добавить обязательный шаг **route preflight**:
   `harness_status` → если route не определён → `harness_run` (route=code-implementation) → записать route/bundle в PROGRESS.md.
3. Создать `shared/route-preflight.md` — мини-капсула: 3 команды, вывод, что писать в PROGRESS.

**Проверка слоя 1:**
```
# в E2E-сессии (первые 2 шага):
tool=harness_status  →  route=code-implementation, bundle=[tools]
# в логе: "route resolved" для session.id
PROGRESS.md содержит строку "ROUTE: code-implementation"
```
**Acceptance:** ни одна E2E-сессия не начинает правки кода до записи ROUTE в PROGRESS.

---

## Слой 2 — E2E-01: принуждение к фабрике (диспатч обязателен)

**Архитектура:**
1. `code-orchestrator.md`: раздел «Диспатч воркеров» — из рекомендательного в **обязательный**:
   «Каждый модуль = task(coder-worker) + task(code-reviewer) + task(code-tester). SOLO допустим
   только с флагом SOLO_MODE в отчёте и авто-штрафом в character_sheet».
2. Все сабмиты идут через `factory_ctl submit` (не в обход).
3. Новый `scripts/ci/test_e2e_orchestration.py` — статический аудит сессии:
   - читает `opencode.db` (таблица `part`, поле `data.tool`);
   - проверяет: в сессии есть `task`-вызовы на каждый заявленный модуль, есть `factory_ctl submit`;
   - возвращает PASS/FAIL + список модулей без делегирования.

**Проверка слоя 2:**
```
python scripts/ci/test_e2e_orchestration.py --session <id> --expect-workers >=3
# PASS: task×worker≥3, task×reviewer≥3, task×tester≥3, factory_ctl submit ≥3
# FAIL: перечислены модули, сделанные в SOLO_MODE
ls .runs/worker_m*.json   # есть файлы делегирования
```
**Acceptance:** сессия без `task` на модуль помечается FAILED; SOLO_MODE виден в отчёте.

---

## Слой 3 — E2E-04: аудитор/трибунал активируется

**Архитектура:**
1. `scripts/code-factory/tribunal_trigger.py` — детерминированный триггер:
   - вход: `factory_state.json` + `review_fail_count` + `iteration_count`;
   - выход: `tribunal_required: [module,...]` — выводится как команда, а не рекомендация.
2. `code-orchestrator.md`: при непустом `tribunal_required` — немедленный `task(code-auditor)`
   с метаданными процесса (вердикты ревьюеров, ответы воркеров, метрики), НЕ код.
3. Проверка, что `code-auditor` присутствует в `subagent_type` списке (агент `code-auditor`).

**Проверка слоя 3:**
```
# в E2E-сессии при 2+ раундах REWORK:
tool=task subagent_type=code-auditor  (в частях сессии)
# auditor возвращает verdict APPROVE/REJECT/INVALID_INPUT
python scripts/code-factory/tribunal_trigger.py --state .runs/factory_state.json
# → tribunal_required: [module] или []
```
**Acceptance:** конфликт воркер↔ревьюер 2+ раунда всегда завершается вызовом аудитора.

---

## Слой 4 — E2E-03: глобальные циклы и git-хуки

**Архитектура:**
1. Установить активные хуки в рабочий проект (каллибровка):
   - `hooks/pre-commit` → `sleep_git.py` (M6) + `perfectionist.py` (M10 completion_hook);
   - `hooks/post-commit` → `git_session_sync.py` (M5) sync + audit.
   - Источник хуков: ветки `feature/m5-git-session-sync`, `feature/m6-sleep-git` (файлы есть там,
     но отсутствуют в `feature/m11-daemon-integration`) — сначала merge этих веток в основную.
2. `fraction_lib` начинает отслеживаться git (сейчас `?? ./`) — решается в Слое 0/6 (bootstrap).
3. `scripts/tools/agent_loop.py` встраивает вызов `sleep_integration.py cycle` между волнами.

**Проверка слоя 4:**
```
Get-ChildItem .git/hooks | где Name -notmatch ".sample"
# → pre-commit, post-commit (НЕ только LFS)
git add -A; git commit -m "test"  →  в выводе "sleep_git: ...", "perfectionist: TODO->completeness"
# в логе opencode: hook post-commit executed
```
**Acceptance:** каждый коммит воркера проходит sleep_git + perfectionist + session_sync.

---

## Слой 5 — E2E-07: доведение ритуалов

**Архитектура:**
1. `shared/orchestration-thread-process.md` → чек-лист старта и закрытия разбить на **gate-пункты**:
   - Старт: капсула → project_context → «Где я» → character_sheet --min → ROUTE preflight (Слой 1).
   - Закрытие: kanban_report → memory add → контроль остатка нити → todo синхронизация.
2. В `code-orchestrator.md`: ритуалы из «рекомендуется» в «обязательно до/после».
3. `scripts/ci/test_e2e_orchestration.py` (расширить): проверяет наличие `kanban_report`, `memory add`
   в последних шагах сессии и консистентность todo (completed для сделанного).

**Проверка слоя 5:**
```
python scripts/ci/test_e2e_orchestration.py --session <id> --check-rituals
# PASS: kanban_report в конце, memory add, todo completed == факт
```
**Acceptance:** сессия, завершённая без kanban_report/memory add, помечается FAILED (ритуал).

---

## Слой 6 — E2E-05: волны без обрыва

**Архитектура:**
1. `agent_loop.py`: переписать механизм «Continue the frozen plan» — продолжение должно
   переоткрывать сессию (`opencode run --session <id>`) или создавать child-session, а не слать
   сообщение в уже завершённую.
2. `code-orchestrator.md`: `steps: 60` → `steps: 120` (или параметризовать через env).
3. Обрыв-гард: перед каждым шагом оркестратор знает остаток (`todowrite` + счётчик шагов);
   при остатке < 10 — закрывает волну (kanban_report + memory add + PROGRESS), затем авто-продолжение.

**Проверка слоя 6:**
```
# E2E-сессия > 60 шагов не должна заканчиваться текстом "лимит шагов достигнут"
# после лимита появляется продолжение в той же сессии (новые parts) ИЛИ child-session с parent_id=<id>
python scripts/ci/test_e2e_orchestration.py --session <id> --check-continuation
```
**Acceptance:** ни одна волна не обрывается посреди пункта без сохранения состояния.

---

## Порядок внедрения (git-ветки)

| Шаг | Действие | Ветка | Слои |
|---|---|---|---|
| 1 | Merge `feature/m5-git-session-sync`, `feature/m6-sleep-git` в основную (нужны Слою 4) | `feature/m11-daemon-integration` | 0 (подготовка) |
| 2 | Слой 0 (bootstrap, path_resolution, env) | `feature/e2e-s0-config` | 0 |
| 3 | Слой 1 (роутер в промпте, route-preflight.md) | `feature/e2e-s1-router` | 1 |
| 4 | Слой 2 (обязательный диспатч + test_e2e_orchestration.py) | `feature/e2e-s2-factory` | 2 |
| 5 | Слой 3 (tribunal_trigger.py) | `feature/e2e-s3-tribunal` | 3 |
| 6 | Слой 4 (хуки в каллибровке) | `feature/e2e-s4-hooks` | 4 |
| 7 | Слой 5 (ритуалы gate) | `feature/e2e-s5-rituals` | 5 |
| 8 | Слой 6 (agent_loop продолжение, steps) | `feature/e2e-s6-waves` | 6 |

**Правило слияния:** слой N мержится только после PASS проверки слоя N-1 (детерминированный чек).
Никакой «все сразу» — это и есть матрёшка.

---

## Матрица проверки (единый прогон «матрешка»)

Скрипт-обёртка `scripts/ci/test_e2e_matryoshka.py` выполняет проверки слоёв 0→6 по цепочке,
останавливается на первом FAIL и печатает номер слоя:

```
S0 PASS → S1 PASS → S2 PASS → S3 PASS → S4 PASS → S5 PASS → S6 PASS  →  ✅ E2E READY
S0 PASS → S1 FAIL (роутер не вызван)                                 →  ⛔ стоп на слое 1
```

Каждая проверка — короткая детерминированная команда (см. выше), не требующая LLM.

---

## Риски

| Риск | Слой | Митигация |
|---|---|---|
| Junction/plugin не подхватится в новом opencode | 0 | Проверка Test-Path + перезапуск процесса |
| `harness_run` не в списке тулов у агента | 1 | Плагин регистрирует tool; иначе — MCP coder_router |
| SOLO-режим останется захардкоженным поведением модели | 2 | Авто-штраф в character_sheet + FAIL от test_e2e |
| Аудитор вернёт INVALID_INPUT (передали код) | 3 | Строгий контракт: только метаданные процесса |
| Хуки блокируют коммит (цикл) | 4 | Dry-run флаг + tail-log хуков |
| Лимит шагов не решается только steps | 6 | Волновое планирование, а не просто увеличение |