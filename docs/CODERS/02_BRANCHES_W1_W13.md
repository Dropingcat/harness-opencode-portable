# ВЕТКИ W1–W13: АВТОМАТИКА ФАБРИКИ — ПОЛНЫЕ СПЕЦИФИКАЦИИ

**Дата:** 2026-10-05
**Статус:** СПЕЦИФИКАЦИИ ГОТОВЫ (W1..W8 — по детальным планам; W9/W10/W11/W12/W13 — полные тексты ниже)
**CWD:** `E:\opencode_harness_portable`
**Python:** `.venv\Scripts\python.exe`

> Формат ветки: **ID — что — файлы — зависимости — проверка (команда→результат) — сложность/риск — статус.**
> Полные спеки W9/W10/W11/W12/W13 приведены целиком (они реконструированы из фактов аудита как единственный источник истины).

---

## 0. Разметка параллельности (КРИТИЧНО)

| Ветки | Можно параллельно? | Обоснование |
|-------|--------------------|-------------|
| **W1 ↔ W13** | **ДА, но W13 НЕ раньше M4** | W1 создаёт хуки + переносит `sleep_git.py`/`git_session_sync.py` (merge m5/m6). W13 расширяет `sleep_git.py` — но W13 запланирован ПОСЛЕ M4 (матрёшка Слой 4 ставит хуки). После M4 — W13 может работать параллельно с W1-обвязкой |
| **W12 ↔ W9** | **ДА (после импорта shared)** | W12 (аудит цепочек, NEW-1..7) и W9 (peer-координация) оба читают shared/ и агентов, но меняют разные файлы (W9 — новый `peer_coordinator.py` + `.runs/deliberation/`; W12 — промпты/env/удаление gk.report). Ветки не конфликтуют |
| **B2 ↔ W7** | **ДА** | B2 (sync_to_live.py, live-зеркало) и W7 (мета-цикл, `scripts/meta/`) затрагивают `scripts/`-каталог, но B2 работает с группами (scripts/ как группа), W7 — с `scripts/meta/` напрямую. Расхождение по файлам минимально; **не параллелить с B1-T3** (перенос meta — предусловие W7) |
| **W2/W3/W4/W5/W6** | **Строго последовательно** (в этом порядке) | W2 (оркестраторы) → W3 (runner) → W4 (аудит/трибунал, зависит от B4-T4) → W5 (роутер, зависит от EXP-4) → W6 (координаторы: agent_loop + sync_to_live + memory_router) |
| **W7 → W8** | **Строго последовательно** | W8 (canon_search) нужен W10-T4 (canon_fragment) и W12; W7 не зависит от W8, но идёт раньше по критическому пути |
| **W9-T4** | BLOCKED | Зависит от Слоя 2 матрёшки (E2E-01) — каркас W9-T1..T3 ставить, T4 — после M2 |
| **W10** | **В самый конец** | POST-миграция, ПОСЛЕ W8 (нужен canon_search). Не параллелить ни с чем |

**Общий порядок:** W1 → W2 → W3 → W4 → W5 → W6 → W9 → W7 → W8 → (M0-M6 матрёшка) → W13 → W10. W11 — параллельно-после B3-T2 (Транш A). W12 — после импорта shared (B1-T4/B2-T4).

---

# W1 — GIT-ХУКИ (E2E-03, матрёшка Слой 4)

**Статус:** СПЕЦИФИКАЦИЯ ДЛЯ КОДЕРА (готово). Ветка: `feature/e2e-s4-hooks` (база `feature/m11-daemon-integration`).
**Полный детальный план:** `PLAN_W1_GIT_HOOKS.md` (корень portable). Ниже — сводка для исполнения.

**Что:**
1. **Merge m5/m6 как перенос файлов** (НЕ `git merge`): `git checkout feature/m6-sleep-git -- scripts/tools/sleep_git.py` + `git checkout feature/m5-git-session-sync -- scripts/tools/git_session_sync.py`. Без `.runs/worker_m*.json`. Конфликтов НЕТ (fast-forward-совместимо, проверено).
2. Создать 4 файла хуков: `hooks/pre-commit`, `hooks/post-commit`, `hooks/pre-push`, `hooks/hook_utils.sh` (полные тексты — PLAN_W1 §3.1-3.4).
3. `core.hooksPath` → `hooks` (НЕ `.git/hooks`).
4. `.gitignore` — добавить паттерны (PLAN_W1 §4.2; сводка в `01_BLOCKS_B1_B5.md` §B3-T4). Exception: `!.runs/worker_m11.json`.

**Поведение хуков:**
| Хук | Проверки | Блокирует? |
|-----|----------|-----------|
| **pre-commit** | perfectionist `completion_hook` (warning-only) + sleep_git `--dry-run snapshot` | НИКОГДА (exit 0) |
| **post-commit** | compile_agents `--check` WARN + health_check + git_session_sync `--no-commit` | НИКОГДА (exit 0) |
| **pre-push** | compile_agents `--check` БЛОК + coder-dom-verify.sh БЛОК | **ДА** (exit 1 при fail) |

**Проверка (команда → результат):**
```
git config --get core.hooksPath                      # → hooks
ls hooks/                                            # → pre-commit post-commit pre-push hook_utils.sh coder-dom-verify.sh
git commit --allow-empty -m "w1 smoke"               # → в выводе [w1] pre-commit:..., [w1] post-commit:...; exit 0
.venv\Scripts\python.exe scripts/tools/sleep_git.py --dry-run snapshot --task chk   # → {"tag": "baseline/chk/<ts>", ...}; тег НЕ создан
git log --oneline --all -- scripts/tools/sleep_git.py                                # → содержит 5697339
git check-ignore -v .runs/progress/x.json .kanban.db                                 # → rc=0, паттерн выведен
```

**Сложность/риск:** Средняя. Риск-12: `W1_SKIP_HOOKS=1` для CI. **До B1-T3** pre-commit печатает `[w1] perfectionist skipped/failed (non-blocking)` — запланировано.

**Роллбэк:** `git config --unset core.hooksPath`; для отката переноса — `git checkout feature/m11-daemon-integration -- scripts/tools/ .gitignore`.

**DoD (PLAN_W1 §6.1, все 13):** команды выше + `git commit --allow-empty --no-verify -m` → НЕТ `[w1]` в выводе (хуки реально вызываются git'ом); `git push` при рассинхроне агентов → отклонён.

---

# W2 — ОРКЕСТРАТОРЫ: РИТУАЛЫ СТАРТА/ЗАКРЫТИЯ (ГОТОВО)

**Что:** ритуалы старта/закрытия, `kanban_report`, `idle_tasks`, CWD-валидация (B3-T3, B4-T8).

**Файлы:** `scripts/orchestration/kanban_report.py`, `scripts/orchestration/idle_tasks.py`, `scripts/orchestration/character_sheet.py`, `scripts/orchestration/delegation_score.py`.

**Проверка:**
```
.venv\Scripts\python.exe scripts/orchestration/idle_tasks.py --check   # → кандидаты L2→L3, .tmp_l2.json создан
.venv\Scripts\python.exe scripts/orchestration/kanban_report.py        # → отчёт по .kanban.db
```

**Сложность:** Низкая. **Роллбэк:** `git revert` правок промптов.

---

# W3 — СУБАГЕНТЫ/RUNNER (ГОТОВО, подтверждает EXP-0)

**Что:** `gen_runners --check`; runner = единственная точка CLI (subagent не primary).

**Проверка:**
```
.venv\Scripts\python.exe scripts/agent_gen/gen_runners.py --check     # → PASS, runner-файлы в синхроне
```

**Сложность:** Низкая. Роллбэк: перегенерация `gen_runners.py`.

---

# W4 — АУДИТ/ТРИБУНАЛ (ГОТОВО)

**Что:** B4-T4 guard + `tribunal_trigger.py` (новый): читает `factory_state.json`, `review_fail_count`, `iteration_count` → `tribunal_required`. Тонкая CLI-обёртка над `_convergence_view`, НЕ дублирует редьюсер.

**Файл:** `scripts/code-factory/tribunal_trigger.py`.

**Проверка:**
```
.venv\Scripts\python.exe scripts/code-factory/tribunal_trigger.py --state .runs/factory_state.json
# → tribunal_required: [module,...] или []
```

**Сложность:** Низкая. Роллбэк: удалить файл, `git revert`.

---

# W5 — РОУТЕР (ГОТОВО, требует EXP-4)

**Что:** `harness_run` → bundle → route; `runtime_snapshot.json` — источник правды. `scripts/router/resolve_route.py`, `resolve_bundle.py`, `compile_runtime.py`.

**Имя тула:** `coder_run` (НЕ `coder_router_coder_run`; `mcp/coder_router_server.py:216`).

**Проверка:**
```
.venv\Scripts\python.exe scripts/router/compile_runtime.py --check     # → runtime_snapshot.json актуален
.venv\Scripts\python.exe scripts/router/resolve_route.py --task "найти источники"   # → task_class=search + hint + dashboard
```

**Сложность:** Средняя. Зависит от EXP-4. Роллбэк: `git revert` + перегенерация snapshot.

---

# W6 — КООРДИНАТОРЫ (ГОТОВО)

**Что:** `agent_loop` (B4-T5) + `sync_to_live` (B2-T1) + `memory_router` (TD-175). `scripts/memory/memory_bridge.py`, `scripts/memory/memory_router.py`, `scripts/tools/agent_loop.py`.

**Проверка:** см. B4-T5 (agent_loop), B2-T1 (sync_to_live). Memory-переключение: `switch research-orchestrator → source-fetcher` → только global + namespace + light-memory.

**Сложность:** Средняя. Роллбэк: `git revert` + fallback OPENCODE_BIN.

---

# W7 — МЕТА-ЦИКЛ (V1–V8, ночной прогон, L2→L3) (ГОТОВО)

**Статус:** СПЕЦИФИКАЦИЯ ДЛЯ КОДЕРА (исполнимые шаги). Ветка: W7.
**Полный детальный план:** `E:\Documents\Документы\doc_Opencode_agern-new\docs\PLAN_W7_B1T3_META_CYCLE_PORTING_2026-10-04.md` (489 строк). Сводка — `01_BLOCKS_B1_B5.md` §B1-T3.

**Что (после B1-T3):**
1. Прогон проверок 1-11 (см. `01_BLOCKS_B1_B5.md` §B1-T3 DoD).
2. Создать `scripts/meta/meta_nightly.cmd` + `meta_nightly_task.xml` (ночной прогон Task Scheduler 02:30):
   - `sleep_integration.py cycle` → `meta_daemon --once` → `run_audit_cycle.py` → `liveness`.
3. Вставить секцию «Meta-Cycle health (V-1)» в `agents/code-orchestrator.md` (точный текст — PLAN_W7 §4.1).
4. L2→L3: `idle_tasks.py --check` (кандидаты) → `MemoryCirculator.promote_to_l3()` (admissions ≥ 2) → `memory_bridge.py add`.

**Проверки (команда → результат):**
```
.venv\Scripts\python.exe -m compileall -q scripts\meta                       # → exit 0
.venv\Scripts\python.exe scripts/meta/meta_daemon.py --once --orchestrator code-orchestrator
# → JSON {"sleep": false/true, "hp": 0..100, "damage": int, "dropped": int}
.venv\Scripts\python.exe scripts/meta/sleep_integration.py cycle --task dry-run --branches "fix/A" --simulate --no-git
# → "simulated": true, "merged": ["fix/A"], exit 0
.venv\Scripts\python.exe scripts/meta/sleep_integration.py guard --events '[{"tool":"arxiv_search","repeat":3}]'
# → [{"id":"circle",...}], exit 1
.venv\Scripts\python.exe scripts/meta/sleep_integration.py liveness --state-dir .meta_state --orchestrator code-orchestrator
# → после meta_daemon --once: alive: true
cmd /c "E:\opencode_harness_portable\scripts\meta\meta_nightly.cmd"          # → лог в .meta_state\meta_nightly_*.log
```

**Сложность:** Средняя. **Риски:** демон-зомби (PID-файл, `taskkill /F /PID`), `_ensure_clean` (чистое дерево перед ночным прогоном), target merge жёстко `main`. **Роллбэк:** `git checkout -- scripts/meta` + удаление `.meta_state/*.json`.

---

# W8 — CANON-ПОИСК (POST-миграция, ГОТОВО)

**Что:** `canon_loader` + `canon_search` (B4-T10): SQLite FTS5, `docs/canon` (45 файлов: ch01..ch42 + appA/appB/appC — **НЕ 46**, см. P-MAJ-2), `.runs/canon_index/`, ch13=«хуки».

**Проверка:**
```
.venv\Scripts\python.exe scripts/tools/canon_loader.py --rebuild          # → FTS5-индекс построен
.venv\Scripts\python.exe scripts/tools/canon_search.py --query "хуки"     # → результаты из ch13
(Get-ChildItem docs\canon -File).Count                                    # → 45
```

**Сложность:** Средняя. **Роллбэк:** удалить `.runs/canon_index/`, пересобрать.

---

# W9 — PEER-КООРДИНАЦИЯ (ГОТОВО, T4 BLOCKED)

**Полная спецификация:**

**Назначение:** координация peer-агентов через deliberation (обсуждение споров) — детерминированный арбитраж конфликтов воркер/ревьюер без LLM-движка.

**Ветка:** `feature/w9-peer-coordinator` (база — `feature/m11-daemon-integration`).
**Файл:** `scripts/tools/peer_coordinator.py` + тест `tests/test_peer_coordinator.py`.

**Подзадачи:**
| ID | Что | DoD |
|----|-----|-----|
| **W9-T1** | `peer_coordinator.py` — команды `detect` / `zone` / `claim` / `check` | Каждая команда: CLI, JSON-выход, exit 0/1 |
| **W9-T2** | Каталог `.runs/deliberation/<task>/<agent>.claim.json` — стадии `claim → review → resolve/escalate` | Файлы стадий создаются/переходят по стадиям |
| **W9-T3** | Лимиты: `max_rounds=2`, `timeout=10`; эскалация: оркестратору → question → `AMBIGUOUS`; conflict НЕ блокирует finalize (дефолт `required:true` для участников) | При 2+ раундах → эскалация; finalize проходит при unresolved |
| **W9-T4** | **[BLOCKED]** Интеграция со Слоем 2 матрёшки (E2E-01: обязательный диспатч). Каркас ставить, полный цикл — после M2 | См. `03_ACCEPTANCE.md` §M2 |

**Факты:** arise/hiai — НЕ движки (только референс). `deliberation` (sic, так в ТЗ) — каталог артефактов.

**Проверка:**
```
.venv\Scripts\python.exe scripts/tools/peer_coordinator.py detect --task T       # → участники спора
.venv\Scripts\python.exe scripts/tools/peer_coordinator.py claim --task T --agent code-reviewer   # → claim.json создан
.venv\Scripts\python.exe scripts/tools/peer_coordinator.py check --task T        # → стадия resolve/escalate, rounds<=2
```

**Сложность:** Средняя (T1-T3), T4 — после M2. **Роллбэк:** удалить `.runs/deliberation/`, `git revert`.

---

# W10 — МОДУЛЬ САМООБУЧЕНИЯ (RUD-3) (СПЕЦИФИКАЦИЯ ГОТОВА, POST-миграция)

**Полная спецификация:**

**Назначение:** анализ завершённых блоков задач → принципы оптимальных сессий, навыки (полученные/НЕ полученные), паттерны скилов. **Детерминированно** (SQL+JSON, без LLM). **Read-only к источникам** (не мутирует БД/файлы сессий).

**Факты аудита (не обсуждаются):**
- `opencode.db` = **426 сессий** (проверено 04.10; счётчики пересчитать при старте — P-MAJ-3): portable 74, live 131, canon 4, other 217. 92 897 part.
- finish reasons: tool-calls 19155 / stop 940 / length 17 / error 1.
- Канон `.runs` = 29 json.
- Промоушен: `memory_l3_policy` (min_recurring 2), `SKILL_MIN_COUNT=3`, `add_skill.py` — официальный путь скилов.
- W10 НЕ дублирует: W7 (не прокачивает скилы, не пишет legacy), W8 (не строит FTS5), W9 (не участник deliberation).

**Ветка:** `feature/w10-self-learning` (база — после W8). **Приоритет:** POST-миграция.

**Формат урока (JSON):**
```json
{
  "lesson_id": "L-<seq>",
  "kind": "interaction_principle | skill_used | skill_missing | stuck_escape",
  "source_session": "<session_id>",
  "source_ref": "<part_id>",
  "task_type": "code | research | writer",
  "contour": "cli | api | gui",
  "pattern": "<паттерн, извлечённый из сессии>",
  "success_metric": "<метрика успеха>",
  "skill_candidate": {"name": "<skill>", "evidence_count": 0, "route": "code-implementation | research | writing", "capsule": "<capsule_text>"},
  "skill_missing": [],
  "canon_fragment": {"chapter": "<chNN>", "quote": "<текст>"},
  "lesson_text": "<текст урока>",
  "reason_codes": ["<code>"],
  "evidence_refs": ["<ref>"],
  "admissions": 0,
  "status": "candidate | promoted | rejected"
}
```

**Подзадачи:**
| ID | Что | Файлы | Сложность |
|----|-----|-------|-----------|
| **W10-T1** | `session_analyzer.py`: SQL-метрики — сессии по контуру, шаги part, finish reasons message, todo-ratio, tool-ошибки. Выход `sessions_metrics_<date>.json` в `.runs/selftrain/`. Классификация success/fail. | `scripts/self-learning/session_analyzer.py` + тест | M |
| **W10-T2** | `lesson_extractor.py`: правила — успешные vs провальные, кластеризация tool-пар БЕЗ ML, навыки использованные/неиспользованные, паттерн «застрял→что помогло». Выход `lessons_candidates_<date>.json`. | `scripts/self-learning/lesson_extractor.py` + тест | L |
| **W10-T3** | `skill_promoter.py`: гейты промоушена — `memory_l3_policy`: `evidence_refs`, `reason_codes`, `admissions >= 2` ИЛИ `evidence_count >= 3`. Генерация SKILL.md-шаблона. Вызов `add_skill.py --dry-run` (по умолчанию) / `--apply`. Выход `promoted_<date>.json` + `rejected_<date>.json`. | `scripts/self-learning/skill_promoter.py` + тест | L |
| **W10-T4** | `memory_integration.py`: уроки в L2 (`.l2_memory/<agent>.json` формат S5 + `.tmp_l2.json`), L3 через `memory_router add`, canon_fragment через W8 `canon_search`, тег `source=matryoshka`. | `scripts/self-learning/memory_integration.py` + тест | M |
| **W10-T5** | `legacy_bootstrap.py`: ОДНОКРАТНЫЙ прогон по канону (29 `.runs` json, `.kanban.db`, `.meta_state`, `.l2_memory`, старые сессии `opencode.db`). Выход `legacy_lessons_<date>.json`. Флаг `--applied` для идемпотентности. | `scripts/self-learning/legacy_bootstrap.py` + тест | L |

**Проверка (после каждого модуля):**
```
.venv\Scripts\python.exe scripts/self-learning/session_analyzer.py --db <opencode.db> --out .runs/selftrain
# → sessions_metrics_<date>.json, классификация success/fail
.venv\Scripts\python.exe scripts/self-learning/skill_promoter.py --candidates lessons_candidates_<date>.json --dry-run
# → promoted_<date>.json (только --dry-run вызов add_skill.py)
.venv\Scripts\python.exe scripts/self-learning/legacy_bootstrap.py --applied
# → legacy_lessons_<date>.json; повторный прогон — noop (идемпотентность)
```

**OQ (открытые вопросы, НЕ блокируют):**
- OQ-1: путь к БД (portable vs глобальная `~/.local/share/opencode/opencode.db`) — параметр `--db`.
- OQ-2: ревьюер кандидатов (человек/оркестратор) — NOT auto (тюнинг-предложения не применяются автоматически).
- OQ-3: tuning-предложения — только в отчёт, НЕ авто.
- OQ-4: `canon_index` путь — `.runs/canon_index/` (W8).
- OQ-5: deliberation для кандидатов — НЕ используется (W10 не участник deliberation).

**Роллбэк:** модули read-only; удалить `.runs/selftrain/`, откатить `--apply` через `add_skill.py --remove`.

---

# W11 — HARNESS КАК УНИВЕРСАЛЬНЫЙ АГЕНТ (RUD-2) (СПЕЦИФИКАЦИЯ ГОТОВА, HIGH)

**Полная спецификация:**

**Ключевые факты аудита (`docs/AUDIT_RUD2_UNIVERSAL_AGENT_2026-10-04.json`):**
- `opencode serve --port 4099` **РАБОТАЕТ** (headless HTTP, 401 basic-auth = жив) — это и есть API-контур. **REST-обёртка НЕ нужна** (fastapi/flask НЕТ в `.venv`, но uvicorn+starlette есть).
- **Имя пакета: `opencode-ai`, НЕ `opencode`** (`bunx opencode` → 404). Shim B3-T2 = вход CLI-контура → `bunx opencode-ai`.
- MCP: 4 сервера указывают на канонный python — EXP-5 критичен (переключение на portable `.venv`).
- Desktop (Electron) запущен, использует ТУ ЖЕ БД opencode.db (426 сессий).

**Ветка:** `feature/w11-universal-agent` (база — после B3-T2). **Приоритет:** HIGH.

**Подзадачи:**
| ID | Что | Файлы | Сложность | DoD |
|----|-----|-------|-----------|-----|
| **W11-T1** | Shim `opencode.cmd` → `bunx opencode-ai` (имя пакета — `opencode-ai`); PATH; принудительный CWD=portable (P-CRIT-1). | `opencode.cmd` (корень portable), `scripts/setup_env.ps1` (B3-T1) | S | запуск из любого CWD → работает, роутер видит portable |
| **W11-T2** | `mcp/harness_control_server.py` — MCP stdio-сервер: `run_agent` / `get_status` / `submit` (тот же паттерн, что coder_router). | `mcp/harness_control_server.py` + регистрация в `.opencode/opencode.json` | M | `get_status` → JSON статуса фабрики |
| **W11-T3** | `agent_loop --attach <url>` — API-контур поверх serve: подключение к работающему серверу. | `scripts/tools/agent_loop.py` (B4-T5) | M | `--attach http://127.0.0.1:4099` → продолжение сессии |
| **W11-T4** | serve-лаунчер: `OPENCODE_SERVER_PASSWORD`, порт 4099, lifecycle (spawn/kill). | `scripts/tools/serve_launcher.py` (новый) | M | старт serve → 401 на корне; kill → процесс закрыт |
| **W11-T5** | E2E-шаг 7: API-проверка. | `scripts/ci/test_e2e_matryoshka.py` (расширение) | S | `start serve → run --attach smoke → HTTP 200/401-auth + session виден в shared БД` |
| **W11-T6** | MCP python → portable `.venv` (входит в EXP-5). | `.opencode/opencode.json` (4 mcp command[0]) | S | 4 сервера подняты на portable python |

**Операции × контур (матрица):**
| Операция | CLI | API (serve) | GUI (Desktop) |
|----------|-----|-------------|---------------|
| запуск агента | `opencode run` / `agent_loop` | serve+SDK или MCP coder_router | чат |
| статус | `factory_ctl status` / `opencode session list` | MCP `get_status` (W11-T2) | список сессий |
| сабмит артефакта | `factory_ctl submit` | `factory_ctl` как библиотека / MCP `submit` | ФС/kanban |
| чтение | `opencode export` | serve API | просмотр |
| конфиг | `.opencode/opencode.json` | serve | project-scoped config |
| БД | `opencode db` (общая opencode.db) | serve (та же БД) | та же БД |

**open_questions (НЕ блокируют):**
- Desktop CWD: какую директорию использует Desktop? (сессии показывают и `C:/Users/Arhys/Desktop/...`, и portable) — проверить выбор проекта GUI.
- `OPENCODE_SERVER_PASSWORD`: управление паролем через контуры (env-контракт).
- serve lifecycle: Task Scheduler / plugin-managed / on-demand spawn.
- bunx vs локальный пакет: `bunx opencode-ai` (кэш) vs локальная установка.

**Проверка:**
```
opencode.cmd --version                                  # → версия opencode-ai (не 404)
.venv\Scripts\python.exe mcp/harness_control_server.py  # → MCP stdio готов
# serve:
#   (запуск)  → http://127.0.0.1:4099 → 401 (basic-auth)
#   agent_loop --attach http://127.0.0.1:4099 --session <id> → продолжение сессии
```

**Роллбэк:** удалить shim из PATH; `git revert`; serve-лаунчер — `taskkill /F /PID`.

---

# W12 — АУДИТ ИНТЕГРАЦИИ ЦЕПОЧЕК (RUD-5/6) (СПЕЦИФИКАЦИЯ ГОТОВА, HIGH)

**Полная спецификация:**

**Назначение:** закрыть пустые интеграции (инструменты есть, но не вызваны) — 80% закрываются после импорта shared.

**Реестр 18 пустых интеграций:**
| # | Пустая интеграция | Закрытие |
|---|-------------------|----------|
| 1 | 9 shared отсутствуют в portable | B1-T4 / B2-T4 |
| 2 | `scripts/writer/` только в каноне | B2-T4 |
| 3 | `doc_guard` → `session_guard` | B4-T2 |
| 4 | `unified_search` не существует | NEW-1 |
| 5 | `harness_run`/`coder_run` не в промптах | M1 (матрёшка) |
| 6 | `agent_loop` не вызывается | W6 / M6 |
| 7 | `meta_daemon` НЕТ в portable | B1-T3 / W7 |
| 8 | хуков нет | W1 / M4 |
| 9 | env `RESEARCH_*`/`WRITER_*` не заданы | NEW-6 / NEW-7 |
| 10 | `gk.report` устаревшая сигнатура (code-orch:116 / research-orch:137) | NEW-5 |
| 11 | `mcp/` не в sync-группах | B2-T1 (группа `mcp/`) |
| 12 | launchers не в sync-группах | B2-T1 |
| 13 | `scripts/jobs/job_ctl.py` не в структуре | B1 + W6 |
| 14 | `scripts/glossary/*` (DOM-гейты) не связаны с W1 | W1/pre-push |
| 15 | `config/feature_flags.json` / `anti_patterns_catalog.yaml` отсутствуют | B1/W7 |
| 16 | `agent_prompt_bindings.json` / `role_contracts/` (TD-I1/I3) | W12 |
| 17 | token-бюджет не задан | NEW (ниже) |
| 18 | Desktop-контур не учтён в легализации | B5 / B1-T5 |

**NEW-1..7 (новые подзадачи):**
| ID | Что | Файлы | DoD |
|----|-----|-------|-----|
| **NEW-1** | unified_search skill: единый поиск (canon + tool + docs) | `skills/opencode-current/unified-search/SKILL.md` | skill вызывается из промптов |
| **NEW-2** | memory L3 в writing-закрытии: писатель пишет в L3 на закрытии (сейчас НЕТ L3 у писателя) | `agents/writer-orchestrator.md`, `scripts/writer/closure` | L3-запись в закрытии |
| **NEW-3** | writer → tribunal-judge для факт-споров (у писателя нет трибунала) | `agents/writer-orchestrator.md`, `scripts/writer/tribunal_bridge.py` | факт-спор → аудитор |
| **NEW-4** | writer-редьюсер (state machine) — выделить как ПОДСИСТЕМУ (P-MAJ-5) | `scripts/writer/reducer.py` + state machine | состояния draft→review→resolve |
| **NEW-5** | убрать `gk.report` (устаревшая сигнатура) | `agents/code-orchestrator.md:116`, `agents/research-orchestrator.md:137` | grep gk.report → 0 |
| **NEW-6** | env-контракт research: `RESEARCH_RUNNER_SH`, `RESEARCH_RULES_PATH` и др. | `scripts/setup_env.ps1`, `docs/ENV_VARIABLES.md` → canon | env-переменные заданы |
| **NEW-7** | env-контракт writer: `WRITER_*` | `scripts/setup_env.ps1` | env-переменные заданы |

**Токен-бюджет (контракт лимитов, из token-consumption-analysis):**
```
max_tokens = 40000
cache hit > 10
LLM calls / claim < 0.7
compaction < 2
max_hops = 3, max_nodes = 15
```
→ перенести в `config/` (модуль `budget.py` уже есть в `scripts/researcher/`) и проверить в аудите.

**Расхождения циклов оркестратор vs писатель:**
| Аспект | Оркестратор | Писатель | Действие |
|--------|-------------|----------|----------|
| Ритуал старта | есть | есть (единый) | — |
| kanban | есть | есть (единый) | — |
| «Где я» | есть | есть (единый) | — |
| Память L3 | есть | **НЕТ** | NEW-2 |
| State machine | есть (редьюсер) | **НЕТ** | NEW-4 |
| Трибунал для факт-споров | есть | **НЕТ** | NEW-3 |

**Роли субагентов:** аудитор (процессный/архитектурный аудит, вердикт APPROVE/REJECT/INVALID_INPUT) vs ревьюер (кодовый ревью) vs планировщик (декомпозиция). Трибунал = аудитор с метаданными процесса (НЕ код).

**Проверка:**
```
# NEW-5:
grep -r "gk.report" .opencode/agent/            # → пусто
# NEW-6/7:
$env:RESEARCH_RUNNER_SH; $env:WRITER_*          # → заданы (после setup_env)
# бюджет:
.venv\Scripts\python.exe scripts/researcher/budget.py --check   # → лимиты соответствуют контракту
```

**Сложность:** Средняя (NEW-4 — подсистема). **Роллбэк:** `git revert` по каждой NEW; env — снять переменные.

---

# W13 — ГЛУБОКИЙ GIT-АУДИТ СНОВ (RUD-7) (СПЕЦИФИКАЦИЯ ГОТОВА, MEDIUM)

**Полная спецификация:**

**3 критические дыры `sleep_git.py`:**
1. Конфликтная ветка при restore **УДАЛЯЕТСЯ** (статус ok в executed, не failed → `branch -D`; изменения не влиты — **ПОТЕРЯ ДАННЫХ**).
2. Рефлексия отсутствует (нет диффов/изменений в отчёте, только статусы).
3. Ночной прогон W7 идёт с `--simulate` — сны НЕ гитированы.

**Метод детекции конфликтов:** `git merge-tree --write-tree <target> <branch>` (проверен на git 2.46, exit 1 = конфликт) — сухой pre-check БЕЗ рабочей копии.

**Ветка:** `feature/w13-deep-sleep-git` (база — после M4). **Приоритет:** MEDIUM.

**Формат отчёта сна (JSON):**
```json
{
  "task": "<task_id>",
  "baseline_tag": "baseline/<task>/<ts>",
  "timestamp": "<iso>",
  "simulated": false,
  "branches": [
    {"name": "fix/A", "status": "ok | failed | conflict | keep",
     "commits": ["<sha>"], "diffstat": {"files": 0, "insertions": 0, "deletions": 0},
     "changed_files": ["<path>"]}
  ],
  "conflicts": [
    {"branch": "fix/B", "target": "main", "files": ["<path>"], "reason": "merge-tree exit 1", "kept": true}
  ],
  "restored_to": "baseline/<task>/<ts>",
  "lessons": [{"branch": "fix/B", "lesson": "конфликт: <файлы>", "target": ".l2_memory"}]
}
```

**Подзадачи:**
| ID | Что | Файлы | Сложность | DoD |
|----|-----|-------|-----------|-----|
| **W13-T1** | Расширение `sleep_git.py`: диффы веток против baseline (`commits[]`, `diffstat`, `changed_files[]`); false_ready детекция (`git diff --quiet baseline..branch`); `merge-tree --write-tree` pre-check (exit 1 = конфликт); **keep конфликтных веток** (класс `conflict` в restore, НЕ удалять); отчёт с `changes/conflicts/lessons`; guard «сон только при чистом дереве» (P-CRIT-5). | `scripts/tools/sleep_git.py` | L | конфликтная ветка сохраняется; отчёт с диффами |
| **W13-T2** | `sleep_report_check.py`: json-schema отчёта сна (`baseline_tag`, `branches[].diffstat`, `conflicts[].files/reason`, `restored_to`). exit 1 при невалидном. | `scripts/tools/sleep_report_check.py` + schema | S | валидный → exit 0; невалидный → exit 1 |
| **W13-T3** | Интеграция с W7: убрать `--simulate` из `meta_nightly.cmd`; отчёты в `.runs/sleep_reports/`; уроки конфликтов → L2 (`memory_circulator`). | `scripts/meta/meta_nightly.cmd`, `.gitignore` (`.runs/sleep_reports/`) | M | ночной прогон с реальным git, `simulated:false` |
| **W13-T4** | `check_sleep_after.py`: 10 проверок чек-листа. | `scripts/tools/check_sleep_after.py` | S | все 10 PASS |

**10 проверок W13-T4 (`check_sleep_after.py`):**
1. baseline создан (тег `baseline/<task>/<ts>` существует).
2. Ветки только `failed`/`conflict`/`keep` (нет потерянных ok-веток).
3. sleep-коммиты влиты (merge в target прошёл).
4. Изменения не пусты (diffstat у влитых веток > 0).
5. Рабочая копия чистая (после restore).
6. Отчёт валиден (W13-T2 schema).
7. Конфликты задокументированы (в `conflicts[]`).
8. Инвариант потери данных: ни одна ветка с неслитыми изменениями НЕ удалена.
9. dry-run в хуке (pre-commit только `--dry-run`).
10. `simulated: false` (ночной прогон гитирует по-настоящему).

**Проверка:**
```
# конфликт-детекция:
.venv\Scripts\python.exe scripts/tools/sleep_git.py run --task demo --branches fix/A,fix/B --exec "cmd" --target main
# → в отчёте: branches[].diffstat, conflicts[] (если merge-tree exit 1), ветки keep
# валидация отчёта:
.venv\Scripts\python.exe scripts/tools/sleep_report_check.py --report .runs/sleep_reports/nightly.json   # → exit 0
# чек-лист:
.venv\Scripts\python.exe scripts/tools/check_sleep_after.py --report .runs/sleep_reports/nightly.json    # → 10/10 PASS
```

**OQ (открытые вопросы, НЕ блокируют):**
- O1: куда писать уроки конфликтов — `.l2_memory/` (memory_circulator).
- O2: чистота дерева — `_ensure_clean` перед `run` (уже есть); guard обязателен.
- O3: GC тегов `baseline/*` — периодическая чистка старых тегов (оставить политику на усмотрение, не блокирует).
- O4: `keep_failed` семантика — `keep_failed` сохраняет failed; конфликтные — ВСЕГДА keep (новый класс `conflict`).
- O5: `--keep-branches` — флаг для сохранения всех веток (диагностика).
- O6: судьба `simulated` — остаётся как отладочный режим, но НОЧНОЙ прогон обязан `simulated:false`.

**Роллбэк:** ветки сна восстанавливаются из `restored_to`; конфликтные ветки — `git checkout <branch>` вручную; `.runs/sleep_reports/` под `.gitignore`.

---

# СВОДНАЯ ТАБЛИЦА ВЕТОК

| Ветка | Что | Сложность | Приоритет | Зависит от | Статус |
|-------|-----|-----------|-----------|------------|--------|
| W1 | git-хуки | Средняя | — | B1-T3 | СПЕКИ ГОТОВЫ |
| W2 | оркестраторы | Низкая | — | B3-T3 | СПЕКИ ГОТОВЫ |
| W3 | runner | Низкая | — | EXP-0 | СПЕКИ ГОТОВЫ |
| W4 | трибунал-триггер | Низкая | — | B4-T4 | СПЕКИ ГОТОВЫ |
| W5 | роутер | Средняя | — | EXP-4 | СПЕКИ ГОТОВЫ |
| W6 | координаторы | Средняя | — | B4-T5 | СПЕКИ ГОТОВЫ |
| W7 | мета-цикл | Средняя | — | B1-T3 | СПЕКИ ГОТОВЫ |
| W8 | canon-поиск | Средняя | POST | B4-T10 | СПЕКИ ГОТОВЫ |
| W9 | peer-координация | Средняя | — | M2 (T4) | СПЕКИ ГОТОВЫ (T4 BLOCKED) |
| W10 | самообучение | M-L | POST | W8 | СПЕКИ ГОТОВЫ |
| W11 | универсальный агент | S-M | **HIGH** | B3-T2 | СПЕКИ ГОТОВЫ |
| W12 | аудит цепочек | Средняя | **HIGH** | B1-T4/B2-T4 | СПЕКИ ГОТОВЫ |
| W13 | git-аудит снов | L/S/M | MEDIUM | M4 | СПЕКИ ГОТОВЫ |