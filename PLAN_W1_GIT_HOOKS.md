# W1 — Git-хуки и автоматические циклы (E2E-03, матрёшка Слой 4)

**Статус:** СПЕЦИФИКАЦИЯ ДЛЯ КОДЕРА (не писать код по этой ветке до одобрения).
**Ветка для реализации:** `feature/e2e-s4-hooks` (база — `feature/m11-daemon-integration`, HEAD `b91f39d`).
**Окружение:** win32, Git-Bash + PowerShell. Python: `.venv\Scripts\python.exe` (существует, проверено).

Все факты ниже проверены чтением реальных объектов git (`git show`) на 2026-10-04.

---

## Секция 1: Анализ артефактов из веток m5/m6

### 1.1 `scripts/tools/git_session_sync.py` (ветка `feature/m5-git-session-sync`, коммит 1601a21)

**Что делает (по коду, 354 строки):**
- **`sync`** — читает `ses_*.json` из каталога сессий opencode (по умолчанию `~/.local/share/opencode/storage/session_diff`, проверено: **существует** на этой машине), берёт только файлы, изменённые за последние `--since-minutes` (по умолчанию 60), извлекает ТЕКСТОВЫЕ parts (type=="text") новых сообщений role=assistant (дедуп через индекс `.runs/session_sync_index.json`, ключ `{session_id: last_msg_id}`), пишет дельту в `.runs/session_deltas/<session_id>_<ts>.txt` (append-only, utf-8) и **делает git add+commit** на ветке `--branch` (по умолчанию `main`; создаёт ветку при отсутствии — на самом деле делает `checkout -b` от текущего HEAD!).
- **`audit` / `--audit`** — детерминированная проверка файла дельты на маркеры несоответствия: `TODO/FIXME/XXX/TEMP/костыль/заглушка/не работает/не уверен/вероятно/скорее всего` (case-insensitive, severity info..critical). `--audit` при findings>0 → exit 1.
- `--no-commit` — только записать дельты, без git.

**CLI (аргументы):**
```
python git_session_sync.py sync [--session-dir DIR] [--since-minutes N] [--branch main] [--no-commit] [--audit]
python git_session_sync.py audit --file PATH
```

**Зависимости:** только stdlib (`argparse, json, re, subprocess, pathlib, datetime, time, sys`). Модуля `baseline_tracker`, `perfectionist` и прочих НЕ требует. Импорт из любой точки дерева: `REPO_ROOT = Path(__file__).resolve().parents[2]` — корректно при расположении `scripts/tools/`.

**Windows-совместимость:** ДА. Никаких bash/posix-зависимостей, git вызывается через `subprocess.run(["git", ...])` (Git for Windows в PATH). Пути через `pathlib`, `as_posix()` для `git add --`. **Два бага для интеграции:**
1. `commit_delta` вызывает `_ensure_branch(branch)` → `git checkout -b main`, если ветки `main` нет (в portable main ЕСТЬ, но checkout на неё при каллибровке на другой ветке — побочный эффект). В хуке всегда передавать `--no-commit` → `_ensure_branch` не вызывается вовсе (файл просто пишется). Полный `sync` с коммитом — ТОЛЬКО в ночном W7, и там передавать `--branch` осознанно.
2. `DEFAULT_SESSION_DIR` захардкожен на `Path.home() / ".local" / "share" / "opencode" / "storage" / "session_diff"` — на win32 это `C:\Users\<user>\.local\share\...` (проверено: каталог существует, т.к. opencode на этой машине использует XDG-совместимый путь). На Windows без Git-Bash HOME=профиль — путь валиден. При желании хук передаёт `--session-dir` явно (см. Секция 3).

**Вердикт:** **МЕРЖИТЬ КАК ЕСТЬ**, НЕ редактировать. Правки кода не требуются; поведение в хуках настраивается аргументами CLI (`--no-commit`, `--since-minutes`). Ограничение ветки: после merge в post-commit хук вызывается ТОЛЬКО с `--no-commit` (никогда не делает checkout/commit в хуке — это запрещено: рекурсивный триггер post-commit).

### 1.2 `scripts/tools/sleep_git.py` (ветка `feature/m6-sleep-git`, коммит 5697339)

**Что делает (по коду, 415 строк):** детерминированная git-обёртка цикла сна M6:
1. `snapshot` — легковесный тег `baseline/<task_id>/<ts>` на текущем HEAD (ничего не коммитит).
2. `run --task T --branches fix/A,fix/B [--exec "cmd"] [--target main] [--keep-failed] [--dry-run]` — проверяет чистоту рабочей копии (`_ensure_clean`, игнорирует `.runs/sleep_state` и `.runs/sleep_markers`), snapshot → создаёт суб-ветки `fix/*` от baseline-коммита с пустым файлом-маркером `.runs/sleep_markers/<task>/<rule>` (маркер-коммит `sleep/<task>/<rule>`) → `execute_branch` через колбэк `--exec` (shell-команда; ненулевой rc → failed, failed-ветка НЕ удаляется) → последовательный `merge --no-ff --no-edit` ok-веток в `--target` (конфликт → `merge --abort`, статус conflict, продолжение) → `restore` (checkout baseline-тега + `git branch -D` своих sleep-веток по маркеру, `keep_failed` сохраняет failed) → JSON-отчёт `report()`.
3. `restore --task T [--keep-failed] [--dry-run]` — возврат к baseline + очистка (идемпотентный).

**CLI (аргументы):**
```
python sleep_git.py [--repo DIR] [--dry-run] snapshot --task ID
python sleep_git.py [--repo DIR] [--dry-run] run --task ID --branches fix/A,fix/B [--exec CMD] [--target main] [--keep-failed]
python sleep_git.py [--repo DIR] [--dry-run] restore --task ID [--keep-failed]
```

**Dry-run режим:** `--dry-run` — мутирующие git-команды (`tag`, `checkout -b`, `add`, `commit`, `merge`, `branch -D`) **печатаются и не выполняются**; read-only (`rev-parse`, `ls-tree`, `tag --list`, `status --porcelain`) выполняются по-настоящему. Именно этот режим нужен для pre-commit.

**Зависимости:** только stdlib. `REPO_ROOT = Path(__file__).resolve().parents[2]` — корректно.

**Windows-совместимость:** ДА. Чистый `subprocess.run(["git", "-C", ...])`. `shell=True` только в `_run_exec` (для `--exec`, в хуке не используется). Нюанс `_ensure_clean`: для реального `run` рабочая копия должна быть чистой (кроме `.runs/sleep_*`) — поэтому в хуке только `--dry-run`.

**Вердикт:** **МЕРЖИТЬ КАК ЕСТЬ.** Правки не требуются. В pre-commit вызывается ТОЛЬКО `snapshot` в dry-run или `run --dry-run` без `--exec` (см. Секция 3: выбран `run --dry-run --task w1-sleepcheck --branches` с noop-исполнителем — валидирует полный цикл, не трогая git; фактически же из-за авто-нетворк-безопасности используем только `snapshot --dry-run`, см. 3.1).

### 1.3 Сводный вердикт
| Файл | Вердикт | Что нужно для интеграции |
|---|---|---|
| `scripts/tools/git_session_sync.py` | Мержить как есть | В хуках — только `--no-commit`; полный sync с коммитом — в W7 с явным `--branch` |
| `scripts/tools/sleep_git.py` | Мержить как есть | В pre-commit — только `--dry-run`; полный цикл — в W7 через `sleep_integration.py cycle` |

---

## Секция 2: Порядок merge веток m5/m6

### 2.1 Топология (проверено)
- `develop` = `master` = `0bc7047` (общий предок).
- ВСЕ feature-ветки meta (m5..m11, td174-177, meta-portable) ответвились от общего коммита `4709b57` (merge-base с m11 для m5/m6 = `4709b57`), который УЖЕ в истории HEAD (`4709b57` входит в `git log 0bc7047..HEAD`).
- **Следствие: merge m5 и m6 в HEAD — fast-forward-совместимые, конфликтов по дереву НЕ будет.** m5/m6 добавляют 2 новых файла (`scripts/tools/*.py`), которых нет нигде в HEAD. `.gitignore` в m5/m6 не менялся (diff пуст — проверено).
- Единственный риск: файлы `.runs/worker_m5.json`, `.runs/worker_m6.json` (служебные маркеры веток) — их НЕ переносить (см. ниже).

### 2.2 Точные команды
```bash
# 0. Гарантия чистого старта (в рабочем дереве есть untracked-мусор — он не мешает merge)
#    НО: сначала закоммитить/застыдить намеренные правки, если они есть (см. риски).
git status --porcelain          # просмотреть; .runs/*, .kanban.db и т.п. — untracked, мешать не будут

# 1. Создать рабочую ветку W1 от текущего HEAD (feature/m11-daemon-integration)
git checkout -b feature/e2e-s4-hooks

# 2. Перенести sleep_git.py и git_session_sync.py БЕЗ служебных .runs/worker_m*.json
git checkout feature/m6-sleep-git -- scripts/tools/sleep_git.py
git checkout feature/m5-git-session-sync -- scripts/tools/git_session_sync.py

# 3. Проверка содержимого
git status --porcelain          # должно быть: A scripts/tools/git_session_sync.py, A scripts/tools/sleep_git.py
git diff --cached --stat        # 2 файла, 354+415 строк

# 4. Коммит переноса
git add scripts/tools/sleep_git.py scripts/tools/git_session_sync.py
git commit -m "feat(w1): перенос sleep_git.py (M6) и git_session_sync.py (M5) в основную ветку (E2E-03 Слой 4)"

# 5. Если по какой-то причине нужен настоящий merge (НЕ рекомендуется здесь):
#    git merge --no-ff feature/m6-sleep-git     # конфликтов нет; .runs/worker_m6.json попадёт в индекс — удалить:
#    git rm --cached .runs/worker_m6.json
```
**Почему не `git merge`:** обе ветки добавляют только свои `scripts/tools/*.py` + служебные `.runs/worker_m*.json`. Перенос через `git checkout <branch> -- <path>` даёт те же блобы и НЕ тащит мусор в историю. Прямой `merge` тоже допустим (fast-forward-совместим), но тогда удалять `.runs/worker_m*.json` из индекса.

### 2.3 Проверка после merge
```bash
# Файлы в HEAD:
git log --oneline --all -- scripts/tools/sleep_git.py
# → 5697339 + наш коммит (или только наш, если переносили файлом)
git log --oneline --all -- scripts/tools/git_session_sync.py
# → 1601a21 + наш коммит
git ls-tree HEAD scripts/tools/ | grep -E "sleep_git|git_session_sync"   # оба присутствуют

# Импорт/запуск (Python из venv):
.venv\Scripts\python.exe scripts/tools/sleep_git.py --dry-run snapshot --task w1-smoke
# → {"tag": "baseline/w1-smoke/<ts>", "commit": "b91f39d..."} — реальный rev-parse, tag не создаётся (dry-run)
.venv\Scripts\python.exe scripts/tools/git_session_sync.py sync --no-commit --since-minutes 999999
# → JSON: либо noop, либо массив результатов с committed:false (файлы дельт ПИШУТСЯ даже в --no-commit)
#   ВНИМАНИЕ: прогон sync --no-commit с since-minutes 999999 запишет ВСЕ дельты сессий в .runs/session_deltas/
#   — это ожидаемо (append-only) и попадёт под ignore из Секции 4.
```

---

## Секция 3: Спецификация хуков

### 3.0 Общие принципы
- **Способ установки:** `core.hooksPath` → `git config core.hooksPath hooks` (все 3 хука + существующий `coder-dom-verify.sh` уже лежат в трекаемом каталоге `hooks/`, они версионируются и переносятся между деревьями). НЕ использовать `.git/hooks` (не трекается, не переносится). При этом `.git/hooks/*.sample` остаются на месте — не мешают.
- **Python:** `.venv\Scripts\python.exe` — полный путь из корня репо: `"$REPO_ROOT/.venv/Scripts/python.exe"`. Bash-скрипты запускаются Git-Bash (shebang не нужен — вызываем через `bash hooks/pre-commit` из конфига, см. ниже). Для надёжности хук резолвит python: если `.venv` нет → `python`.
- **Таймауты:** каждый хук ограничен собственным таймаутом (утилита `run_with_timeout` ниже): pre-commit ≤ 30 c, post-commit ≤ 60 c, pre-push ≤ 120 c. При превышении — НЕ блокировать (warn + exit 0), полный цикл — в ночном W7.
- **Рекурсия:** post-commit никогда не коммитит (только `--no-commit` и warning-проверки). git_session_sync в полном режиме — только в W7.
- **Кодировка:** все скрипты — UTF-8, LF. Скрипты пишутся в `hooks/` и трекаются.
- **Файлы хуков (все — bash, вызываются Git-Bash):**
  - `hooks/pre-commit`
  - `hooks/post-commit`
  - `hooks/pre-push`
  - `hooks/hook_utils.sh` (общая утилита: root, python, таймаут, логгер, exit-коды)

### 3.1 `hooks/hook_utils.sh` — общие утилиты
```bash
#!/usr/bin/env bash
# Общие утилиты хуков W1 (E2E-03, Слой 4). source из pre-commit/post-commit/pre-push.
# Кодировка UTF-8, LF. Запускается Git-Bash (win32).

# Каталог хуков (этот файл), корень репо, python.
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HOOKS_DIR/.." && pwd)"

# Python: venv в приоритете, fallback на системный python.
if [ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
  PYTHON_BIN="$REPO_ROOT/.venv/Scripts/python.exe"
else
  PYTHON_BIN="python"
fi

# Выполнить команду с таймаутом (сек). Таймаут НЕ блокирует:
# возвращает 124 при превышении. Игнорируется в dry-run/CI-окружении.
run_with_timeout() {
  local timeout_sec="$1"; shift
  if [ -n "$W1_SKIP_HOOKS" ]; then return 0; fi
  if command -v timeout >/dev/null 2>&1; then
    timeout "$timeout_sec" "$@" 2>&1
  else
    # Git-Bash на win32 обычно НЕ имеет coreutils timeout — эмуляция через фон.
    "$@" 2>&1 &
    local pid=$!
    local n=0
    while kill -0 "$pid" 2>/dev/null; do
      n=$((n+1)); [ "$n" -ge "$((timeout_sec*10))" ] && { kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; echo "[w1] timeout ${timeout_sec}s exceeded (non-blocking)"; return 124; }
      sleep 0.1
    done
    wait "$pid"; return $?
  fi
}

# Логирование с единым префиксом.
log_hook() { echo "[w1] $*"; }
```

### 3.2 `hooks/pre-commit` — perfectionist completion_hook (быстрый) + sleep_git --dry-run
**Когда срабатывает:** перед каждым `git commit`.
**Поведение:** НЕ блокирует при таймауте; блокирует только если perfectionist не смог отработать (синтаксис/import) — нет: **никогда не блокирует коммит** (предупреждение). Единственный жёсткий fail-критерий — невозможность запустить python (машина сломана) → warning, не блок.

```bash
#!/usr/bin/env bash
# W1 pre-commit (E2E-03, Слой 4): perfectionist completion_hook + sleep_git --dry-run.
# Быстрые детерминированные проверки. НЕ блокирует коммит (warning-only),
# полный sleep-цикл — в ночном W7.
# Выход: 0 всегда (кроме явного W1_SKIP_HOOKS не влияет — см. utils).
source "$(dirname "${BASH_SOURCE[0]}")/hook_utils.sh"

log_hook "pre-commit: perfectionist completion_hook (быстрый)"
# commit message (или заглушка) — артефакт для перфекциониста.
MSG_FILE="${1:-}"
ARTIFACT="commit"
if [ -n "$MSG_FILE" ] && [ -f "$MSG_FILE" ]; then
  ARTIFACT="$(cat "$MSG_FILE")"
fi
run_with_timeout 15 "$PYTHON_BIN" -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path(r'$REPO_ROOT') / 'scripts' / 'meta'))
from perfectionist import PerfectionistSkill
art = sys.argv[1] if len(sys.argv) > 1 else 'commit'
rep = PerfectionistSkill().completion_hook(art)
print(f'[w1] perfectionist verdict={rep.verdict} weaknesses={len(rep.weaknesses)}')
" "$ARTIFACT" || log_hook "perfectionist skipped/failed (non-blocking)"

log_hook "pre-commit: sleep_git --dry-run (валидация цикла без мутаций)"
# snapshot в dry-run: read-only rev-parse выполняется, tag НЕ создаётся.
run_with_timeout 15 "$PYTHON_BIN" "$REPO_ROOT/scripts/tools/sleep_git.py" --dry-run snapshot --task w1-precommit \
  || log_hook "sleep_git --dry-run failed (non-blocking)"

exit 0
```
**Что делает:** (1) гонит `PerfectionistSkill().completion_hook(commit_msg)` — детерминированные эвристики (TODO→completeness, отсутствие цифр, «и т.д.» и пр.), печатает вердикт, (2) `sleep_git.py --dry-run snapshot` — проверяет, что цикл сна валиден (rev-parse HEAD выполняется реально), тег не создаётся. Всё — warning.
**Зависимости:** `.venv\Scripts\python.exe`, `scripts/meta/perfectionist.py`, `scripts/meta/skill_master.py` (импортируется perfectionist'ом!), `scripts/tools/sleep_git.py`. **ВНИМАНИЕ (факт):** текущий `scripts/meta/perfectionist.py` в HEAD импортирует `from skill_master import SkillMaster`, а `skill_master.py` в HEAD отсутствует (канонский комплект переносится веткой B1-T3). **До B1-T3 pre-commit печатает `[w1] perfectionist skipped/failed (non-blocking)` и не падает** — это ЗАПЛАНИРОВАНО (см. риски). Канонская версия perfectionist (с `completion_hook`, строки 86-108) придёт вместе с B1-T3 и автоматически включится.

### 3.3 `hooks/post-commit` — compile_agents --check (warning) + health_check + git_session_sync --no-commit
**Когда срабатывает:** после каждого успешного `git commit`.
**Поведение:** НИКОГДА не блокирует (post-commit не может блокировать коммит), не коммитит сам. Три проверки подряд, каждая с таймаутом.

```bash
#!/usr/bin/env bash
# W1 post-commit (E2E-03, Слой 4): compile_agents --check + health_check + git_session_sync --no-commit.
# Warning-only (post-commit не может блокировать). НИКОГДА не коммитит и не делает checkout.
source "$(dirname "${BASH_SOURCE[0]}")/hook_utils.sh"

log_hook "post-commit: compile_agents --check (warning)"
if ! run_with_timeout 30 "$PYTHON_BIN" "$REPO_ROOT/scripts/agent_gen/compile_agents.py" --check 2>&1; then
  log_hook "WARN: .opencode/agent/ рассинхронизирован (26/26 DIFF). Запусти: $PYTHON_BIN $REPO_ROOT/scripts/agent_gen/compile_agents.py"
fi

log_hook "post-commit: health_check (warning)"
run_with_timeout 30 "$PYTHON_BIN" "$REPO_ROOT/scripts/health_check.py" 2>&1 \
  || log_hook "WARN: health_check UNHEALTHY"

log_hook "post-commit: git_session_sync --no-commit (только запись дельт)"
# --no-commit: файлы .runs/session_deltas/*.txt пишутся, git add/commit НЕ выполняются (нет рекурсии).
run_with_timeout 30 "$PYTHON_BIN" "$REPO_ROOT/scripts/tools/git_session_sync.py" sync \
  --no-commit --since-minutes 120 2>&1 \
  || log_hook "WARN: git_session_sync failed (non-blocking)"

exit 0
```
**Что делает:** (1) проверяет актуальность сгенерированных агентов (`.opencode/agent/`) — при DIFF печатает инструкцию регенерации, (2) прогоняет health_check (обёртка над канонским `doctor.py`, проверено: файлы `scripts/health_check.py` и `packages/opencode-harness-plugin/core/doctor.py` существуют), (3) подхватывает свежие дельты сессий (последние 120 минут) в `.runs/session_deltas/` БЕЗ git-операций.
**Зависимости:** `scripts/agent_gen/compile_agents.py` (+ `runtime/registry.py`, существует), `scripts/health_check.py`, `scripts/tools/git_session_sync.py`, `.venv\Scripts\python.exe`.

### 3.4 `hooks/pre-push` — compile_agents --check (БЛОК) + coder-dom-verify.sh
**Когда срабатывает:** перед `git push` (в т.ч. авто-пуш агентов/воркеров).
**Поведение:** единственный БЛОКИРУЮЩИЙ хук. Fail (exit≠0) → push отклоняется. Оба гейта обязательны.

```bash
#!/usr/bin/env bash
# W1 pre-push (E2E-03, Слой 4): compile_agents --check (БЛОК) + coder-dom-verify.sh (БЛОК).
# Единственный блокирующий хук. При fail — push отклоняется с инструкцией.
source "$(dirname "${BASH_SOURCE[0]}")/hook_utils.sh"

log_hook "pre-push: compile_agents --check (BLOCKING)"
if ! run_with_timeout 60 "$PYTHON_BIN" "$REPO_ROOT/scripts/agent_gen/compile_agents.py" --check 2>&1; then
  log_hook "FAIL: .opencode/agent/ рассинхронизирован. Регенерация:"
  log_hook "  $PYTHON_BIN $REPO_ROOT/scripts/agent_gen/compile_agents.py"
  log_hook "  git add .opencode/agent && git commit"
  exit 1
fi

log_hook "pre-push: coder-dom-verify (BLOCKING)"
if ! run_with_timeout 60 bash "$REPO_ROOT/hooks/coder-dom-verify.sh" 2>&1; then
  log_hook "FAIL: coder_dom.yaml устарел. Исправь: python scripts/glossary/coder_dom_build.py --root $REPO_ROOT"
  exit 1
fi

log_hook "pre-push: OK"
exit 0
```
**Что делает:** жёсткие гейты перед push: агентный реестр синхронизирован с источниками и DOM-глоссарий в актуальном состоянии (`hooks/coder-dom-verify.sh` уже существует и сам вызывает `verify_coder_dom.py` + `coder_dom_stub_gate.py`; оба файла существуют — проверено).
**Зависимости:** те же + `scripts/glossary/verify_coder_dom.py`, `scripts/glossary/coder_dom_stub_gate.py` (существуют).

### 3.5 Установка (одноразовая, в коде/инструкции для кодера)
```bash
# core.hooksPath — все хуки из трекаемого каталога hooks/, версионируются.
git config core.hooksPath hooks
# Проверка:
git config --get core.hooksPath          # → hooks
# .git/hooks не трогаем (там *.sample — пусть лежат).
# Проверка срабатывания (после установки):
git commit --allow-empty -m "w1 hook smoke test" 2>&1 | grep -E "\[w1\]"
# → [w1] pre-commit: perfectionist completion_hook (быстрый)
# → [w1] pre-commit: sleep_git --dry-run (валидация цикла без мутаций)
# → [w1] post-commit: ...
# ВАЖНО: пустой коммит вызовет post-commit с compile_agents --check — при текущем
# рассинхроне .opencode/agent печатает WARN (не блокирует). Ожидаемо.
# Отключение без удаления файлов:
git config --unset core.hooksPath
```
**Пропуск хуков на время работы воркеров:** переменная `W1_SKIP_HOOKS=1` (учитывается в `run_with_timeout`) — для CI/ночного прогона, где полный цикл идёт через W7.

---

## Секция 4: Правка `.gitignore`

### 4.1 Текущее состояние (факт)
- `.gitignore` (95 строк) НЕ содержит ни одного рантайм-паттерна: `.runs/`, `.meta_state/`, `.tmp_l2.json`, `.l2_memory/`, `.kanban.db`, `agents-data/`.
- Подтверждено: `git check-ignore -v .runs/progress/x.json .kanban.db` → **rc=1** (НЕ игнорируются). `.runs/` в рабочем дереве полон untracked-мусора (`git status --porcelain` показывает `.runs/progress/`, `.runs/verification/`, `.runs/reviewer_m2.json`, `.kanban.db` и др.).
- В треке только `.runs/worker_m11.json` — его сохранить в индексе.

### 4.2 Точные добавляемые паттерны (в конец файла, после секции TypeScript)
```
# --- W1: runtime state (E2E-03) — не версионировать рабочие артефакты ---
.runs/session_sync_index.json
.runs/session_deltas/
.runs/sleep_state/
.runs/sleep_markers/
.runs/progress/
.runs/verification/
.runs/*.json
!.runs/worker_m11.json
.meta_state/
.tmp_l2.json
.l2_memory/
.kanban.db
.kanban.db-*
agents-data/**/*
.runs/deliberation/
```

### 4.3 Обоснование каждого
| Паттерн | Зачем |
|---|---|
| `.runs/session_sync_index.json` | индекс обработанных сессий (M5) — служебный, курсор |
| `.runs/session_deltas/` | append-only дельты сессий (M5) — сырые тексты, мусор для истории |
| `.runs/sleep_state/` | состояние цикла сна (M6) — перезаписывается каждый run |
| `.runs/sleep_markers/` | файлы-маркеры sleep-веток (M6) — пустые, чисто служебные |
| `.runs/progress/` | файлы прогресса baseline_tracker (M7) — рантайм |
| `.runs/verification/` | результаты верификации (проверки sources_test*.json в рабочем дереве) — рантайм |
| `.runs/*.json` | прочие рабочие JSON (reviewer_m2, worker_canon_fetch, worker_m2 и т.д.) — рантайм; НЕ трогает историю |
| `!.runs/worker_m11.json` | exception: уже в индексе (единственный осознанный в треке), не разыгноривать |
| `.meta_state/` | состояние meta-демона (sleep_integration.DEFAULT_STATE_DIR = `.meta_state`) — рантайм |
| `.tmp_l2.json` | временный L2-файл (supervisor, TD-174) |
| `.l2_memory/` | L2-память (TD-174/175) |
| `.kanban.db`, `.kanban.db-*` | SQLite kanban (включая журнал WAL `-wal`/`-shm`, покрываются `-*`) |
| `agents-data/**/*` | пользовательские данные агентов (каталог не существует сейчас, но планируется; правило на будущее) |
| `.runs/deliberation/` | (так в ТЗ, sic) — каталог deliberation-артефактов; защита на будущее |

### 4.4 Проверка
```bash
# 1. Рантайм-файлы больше не видны:
git status --porcelain | grep -E "\.runs|\.kanban|\.meta_state|\.tmp_l2|\.l2_memory|deliberation"
# → (пусто)

# 2. Исключение работает:
git status --porcelain | grep "worker_m11"      # → M .runs/worker_m11.json (если изменён) ИЛИ пусто
git ls-files .runs/worker_m11.json              # → .runs/worker_m11.json (в индексе)

# 3. check-ignore:
git check-ignore -v .runs/progress/x.json .kanban.db .meta_state/x.json .l2_memory/x.json .tmp_l2.json
# → .gitignore:<номер>:<паттерн>  для каждого (rc=0)

# 4. Ничего лишнего не заигнорено (текущие трекаемые файлы не скрыты):
git status --porcelain | grep "^!!"             # только __pycache__, node_modules, .venv (как раньше)
```

---

## Секция 5: Интеграция с W7 (ночной прогон) и матрёшкой Слой 4

### 5.1 Полный sleep-цикл — ТОЛЬКО в W7, не в хуках
- Хуки вызывают sleep_git только с `--dry-run`, git_session_sync — только с `--no-commit`.
- Полный цикл сна выполняет **`sleep_integration.py cycle`** (уже в HEAD, `scripts/meta/sleep_integration.py`). Он lazy-подхватывает модули M5-M10 из `scripts/tools/` и `scripts/orchestration/`:
  - `M6` → `sleep_git.SleepGit(repo_root=..., dry_run=False)` — РЕАЛЬНЫЙ git (snapshot → суб-ветки → merge → restore),
  - `M5` → `git_session_sync` (commit дельт, `no_git=False` по умолчанию в CLI `cycle`),
  - `M7` → `baseline_tracker`, `M9` → `hp_regulator`, `M10` → `sleep_enhancers`, `M8` → `monte_carlo_sleep` (по `--monte-carlo`).
- **Критично для W7:** если модули M5-M10 не найдены в `scripts/tools/`, `_load_module` вернёт None и цикл пройдёт на `_Fallback*`-имитациях (всё в памяти, реальный git НЕ вызывается, в отчёте `"simulated": true`). **Именно поэтому merge m5/m6 (Секция 2) — ПРЕДУСЛОВИЕ W7**: без `sleep_git.py`/`git_session_sync.py` в HEAD ночной прогон молча окажется симуляцией.
- **Пример команды ночного прогона (W7, вне хуков, на чистой рабочей копии):**
```bash
# Полный цикл сна с реальным git (M5-M10), без M8:
.venv\Scripts\python.exe scripts/meta/sleep_integration.py cycle \
  --task nightly-<date> --branches fix/nightly-A,fix/nightly-B \
  --hp 80 --session-dir "C:\Users\<user>\.local\share\opencode\storage\session_diff" \
  --since-minutes 720
# → JSON-отчёт: branches[], merged[], hp_after, sleep_success, perfectionist_findings,
#   session_sync {new_deltas, results:[{committed:true,...}]}, simulated:false
# ВАЖНО: sleep_integration вызывает merge в ветку "main" (target жёстко "main" в run_sleep_cycle).
# Перед ночным прогоном: git stash/commit рабочих правок (M6 требует чистой копии),
# иначе _ensure_clean поднимет GitSleepError.
```

### 5.2 Проверки матрёшки Слой 4 (детерминированный чек)
| # | Команда | Ожидаемый результат |
|---|---|---|
| 1 | `git config --get core.hooksPath` | `hooks` |
| 2 | `ls hooks/` | `pre-commit post-commit pre-push hook_utils.sh coder-dom-verify.sh` |
| 3 | `git commit --allow-empty -m "w1 smoke"` | в выводе `[w1] pre-commit: perfectionist...`, `[w1] post-commit: ...`; exit 0 |
| 4 | `git push` (на ветку с рассинхроном агентов) | отклонён, `[w1] FAIL: .opencode/agent/ рассинхронизирован` |
| 5 | `git status --porcelain \| grep -E "\.runs|\.kanban"` | пусто (Секция 4) |
| 6 | `.venv\Scripts\python.exe scripts/tools/sleep_git.py --dry-run snapshot --task chk` | JSON `{"tag": "baseline/chk/<ts>", ...}`, тег НЕ создан: `git tag --list "baseline/chk/*"` → пусто |
| 7 | `.venv\Scripts\python.exe scripts/tools/git_session_sync.py sync --no-commit --since-minutes 1` | `{"status": "noop", ...}` или committed:false; `git log -1` не меняется |
| 8 | `git log --oneline --all -- scripts/tools/sleep_git.py` | содержит 5697339 (файл в истории HEAD) |
| 9 | `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'scripts/tools'); import sleep_git, git_session_sync"` | exit 0 (оба импортируются без ошибок) |
| 10 | `git check-ignore -v .runs/progress/x.json .kanban.db` | rc=0, выведен паттерн из .gitignore |

---

## Секция 6: Критерии готовности (фальсифицируемые) + риски/роллбэк

### 6.1 Критерии готовности (все — проверяемы командой)
1. `git log --oneline --all -- scripts/tools/sleep_git.py` → коммит `5697339` (или наш перенос) в истории; `git ls-tree HEAD scripts/tools/` содержит оба файла.
2. `.venv\Scripts\python.exe scripts/tools/sleep_git.py --dry-run snapshot --task w1-ok` → JSON с реальным `commit` (rev-parse), exit 0; `git tag --list "baseline/w1-ok/*"` → пусто.
3. `.venv\Scripts\python.exe scripts/tools/git_session_sync.py sync --no-commit --since-minutes 1` → exit 0, stdout содержит `"status": "noop"` либо `"committed": false`; `git log -1` не изменился.
4. `git config --get core.hooksPath` → `hooks`; `ls hooks/` содержит `pre-commit post-commit pre-push hook_utils.sh coder-dom-verify.sh`.
5. `git commit --allow-empty -m "w1 smoke"` → exit 0; stdout содержит `[w1] pre-commit: perfectionist completion_hook` и `[w1] post-commit: compile_agents --check`.
6. `git commit --allow-empty --no-verify -m "w1 noverify"` → в stdout НЕТ `[w1]` (хуки пропущены) — подтверждает, что хуки вызываются git'ом, а не эхом.
7. `git status --porcelain` после commit → `.runs/progress/`, `.runs/verification/`, `.kanban.db`, `.tmp_l2.json` отсутствуют (Секция 4).
8. `git check-ignore -v .runs/progress/x.json .kanban.db .meta_state/x.json .l2_memory/x.json .tmp_l2.json` → rc=0 для каждого.
9. `git ls-files .runs/` → `.runs/worker_m11.json` (не разыгнорен).
10. `.venv\Scripts\python.exe scripts/agent_gen/compile_agents.py --check` в post-commit-выводе при текущем рассинхроне печатает `[w1] WARN: .opencode/agent/ рассинхронизирован` и НЕ роняет коммит.
11. `bash hooks/pre-push` вручную при рассинхроне агентов → exit≠0 с `[w1] FAIL: .opencode/agent/ рассинхронизирован`; после `compile_agents.py` + `git add .opencode/agent` → exit 0.
12. `git push` на ветку `feature/e2e-s4-hooks` (после п.11) → проходит (pre-push OK).
13. `git status --porcelain` в начале работы показывал `.runs/...` как `??` — после Секции 4 — нет (обратное доказательство актуальности).

### 6.2 Риски
| # | Риск | Вероятность | Влияние | Митигация | Роллбэк |
|---|---|---|---|---|---|
| 1 | `perfectionist.py` в HEAD импортирует отсутствующий `skill_master` → pre-commit печатает skipped/failed | Высокая (факт: skill_master нет в HEAD) | Низкое (warning-only, коммит не блокируется) | pre-commit НЕ блокирует; канонский `scripts/meta/` придёт с B1-T3 и включит перфекциониста автоматически | `git config --unset core.hooksPath` |
| 2 | `git_session_sync sync` без `--no-commit` сделает `checkout -b main` и создаст лишние коммиты/рекурсию post-commit | Средняя (ошибка кодера при правке хука) | Высокое (грязная история, рекурсия) | В спецификации post-commit жёстко `--no-commit`; W7 передаёт явный `--branch`; кодревью строки вызова | `git log -5`; `git reset --hard HEAD~1` (если лишний коммит уже создан); `git checkout <прежняя ветка>` |
| 3 | `run_with_timeout` без coreutils `timeout` на win32 — эмуляция через фон | Высокая (Git-Bash часто без timeout) | Низкое (функция эмуляции есть в hook_utils) | уже реализовано; проверка: `bash hooks/pre-commit` вручную | — |
| 4 | Merge m5/m6: `.runs/worker_m5.json`, `.runs/worker_m6.json` попадут в индекс | Средняя (только если пойти путём `git merge`) | Низкое (мусор в истории) | В спецификации — перенос файлов `git checkout <br> -- path`, без merge | `git rm --cached .runs/worker_m*.json; git commit` |
| 5 | `sync --no-commit --since-minutes 120` в post-commit запишет много файлов в `.runs/session_deltas/` при первой установке | Средняя | Низкое (append-only тексты; уже под ignore Секции 4) | окно 120 мин; дельты под `.gitignore` | `Remove-Item .runs\session_deltas -Recurse` |
| 6 | pre-push блокирует push при рассинхроне `.opencode/agent` (26/26 DIFF — текущее состояние) | Высокая (сейчас рассинхрон есть) | Среднее (push отклоняется до регенерации) | Это by-design (B4-T7 перегенерирует агентов); инструкция в выводе хука | `git push --no-verify` (разово) или `git config --unset core.hooksPath` |
| 7 | HEAD `feature/m11-daemon-integration` — рабочая, не слитая ветка; перенос файлов через `git checkout <br> -- path` не создаёт merge-коммит в историю (файлы просто в дереве) | Средняя (потеря связи коммит↔файл при будущих merge) | Низкое (файлы корректны, лог `--all` всё равно находит оригинал) | задокументировано в коммит-сообщении переноса | — |
| 8 | `sleep_integration.py cycle` в ночном W7 merge'ит в жёстко заданную ветку `main` | Средняя (если в W7 ветка другая) | Среднее (неожиданный target) | W7 передаёт `--branch` только в git_session_sync; M6 target в run_sleep_cycle зашит `"main"` — задокументировать в W7; при необходимости — фикс в W7, НЕ в W1 | роллбэк W7, не W1 |

**Главный роллбэк всего блока:** `git config --unset core.hooksPath` (хуки отключаются, файлы остаются), затем `git checkout feature/m11-daemon-integration -- scripts/tools/ .gitignore` для отката переноса, если нужен.

---

## Приложение: файлы, создаваемые/изменяемые кодером
| Действие | Файл |
|---|---|
| создать | `hooks/pre-commit`, `hooks/post-commit`, `hooks/pre-push`, `hooks/hook_utils.sh` |
| изменить | `.gitignore` (Секция 4.2) |
| перенести (без изменений) | `scripts/tools/sleep_git.py`, `scripts/tools/git_session_sync.py` |
| НЕ трогать | `scripts/meta/perfectionist.py` (правки — ветка B1-T3), `hooks/coder-dom-verify.sh`, `scripts/meta/sleep_integration.py` |
| финальные коммиты | 1) перенос m5/m6; 2) хуки+`.gitignore`; 3) (опц.) `.gitignore` отдельно, если нужно ревью-прозрачно |