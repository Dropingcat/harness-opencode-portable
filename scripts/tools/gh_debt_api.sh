#!/usr/bin/env bash
# gh_debt_api.sh — общий GitHub API-клиент для операций с техдолгом по GH_TOKEN.
# Токен маскируется в любом выводе ошибок. Используется gh_debt_survey.sh и gh_take_debt.sh.
#
# Как библиотека:  source scripts/tools/gh_debt_api.sh   (задаёт gh_api, gh_mask, GH_REPO, GH_LABEL)
# Как CLI:         ./scripts/tools/gh_debt_api.sh GET "/repos/<repo>/..." [json-body-file]
set -euo pipefail

GH_API="https://api.github.com"
GH_REPO="${GH_REPO:-Dropingcat/harness-opencode-portable}"
GH_LABEL="${GH_LABEL:-tech-debt}"

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "ОШИБКА: переменная окружения GH_TOKEN не задана." >&2
  exit 2
fi

gh_mask() { sed "s/${GH_TOKEN}/***TOKEN***/g"; }

# gh_api METHOD PATH [json-file] — запрос к GitHub REST API, вывод JSON на stdout.
gh_api() {
  local method="$1" path="$2" body="${3:-}"
  local args=(-sS -X "$method" \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28")
  [[ -n "$body" ]] && args+=(-d "@$body")
  curl "${args[@]}" "${GH_API}${path}" | gh_mask
}

# Если файл запущен напрямую — работаем как простой CLI-обёртка над gh_api.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ $# -lt 2 ]]; then
    echo "Использование: $0 METHOD /path [json-body-file]" >&2
    echo "Пример:        $0 GET /repos/$GH_REPO/issues?state=open&labels=$GH_LABEL" >&2
    exit 1
  fi
  gh_api "$@"
fi
