#!/usr/bin/env bash
# Общие утилиты хуков W1 (E2E-03, Слой 4). source из pre-commit/post-commit/pre-push.
# Кодировка UTF-8, LF. Запускается Git-Bash (win32).

# Каталог хуков (этот файл), корень репо, python.
# pwd -W: Git-Bash возвращает POSIX-путь (/e/...), который Python на win32 не
# понимает. pwd -W даёт Windows-путь (E:/...), валидный и для python, и для git.
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -W)"
REPO_ROOT="$(cd "$HOOKS_DIR/.." && pwd -W)"

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