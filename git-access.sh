#!/usr/bin/env bash
# git-access.sh — скрипт доступа к репозиторию GitHub (приватный)
# Использование:
#   1) Передайте ключи одним из способов:
#        export GH_TOKEN="ghp_... или github_pat_..."     # токен HTTPS
#        или поместите приватный SSH-ключ в ~/.ssh/id_ed25519
#   2) ./git-access.sh setup      — настроить удалённый origin и credential helper
#      ./git-access.sh pull       — забрать изменения из main
#      ./git-access.sh push       — отправить изменения
#      ./git-access.sh status     — показать состояние
set -euo pipefail

REPO_URL_HTTPS="https://github.com/Dropingcat/harness-opencode-portable.git"
BRANCH="${BRANCH:-main}"
WORK_DIR="${WORK_DIR:-/workspace}"

die() { echo "ОШИБКА: $*" >&2; exit 1; }

remote_url() {
  if [[ -n "${GH_TOKEN:-}" ]]; then
    # Токен внедряется только в локальный remote, не сохраняется в файлах репо
    echo "https://x-access-token:${GH_TOKEN}@github.com/Dropingcat/harness-opencode-portable.git"
  elif ssh -T git@github.com -o BatchMode=yes -o ConnectTimeout=5 2>&1 | grep -q "successfully authenticated"; then
    echo "git@github.com:Dropingcat/harness-opencode-portable.git"
  else
    die "Нет доступа: задайте GH_TOKEN или настроьте SSH-ключ (~/.ssh/id_ed25519)"
  fi
}

cmd_setup() {
  cd "$WORK_DIR"
  local url; url="$(remote_url)"
  git remote remove origin 2>/dev/null || true
  git remote add origin "$url"
  git config credential.helper 'store --file ~/.git-credentials'
  if [[ -n "${GH_TOKEN:-}" ]]; then
    printf 'https://x-access-token:%s@github.com\n' "$GH_TOKEN" > ~/.git-credentials
    chmod 600 ~/.git-credentials
    echo "HTTPS-доступ настроен через GH_TOKEN."
  else
    echo "SSH-доступ проверен и настроен."
  fi
  git ls-remote --heads origin | sed 's/^/  branch: /'
}

cmd_pull() {
  cd "$WORK_DIR"
  git pull origin "$BRANCH"
}

cmd_push() {
  cd "$WORK_DIR"
  git push -u origin HEAD:"$BRANCH"
}

cmd_status() {
  cd "$WORK_DIR"
  git remote -v | sed 's#//[^@]*@#//***@#'   # маскируем токен в выводе
  git status -sb
}

case "${1:-}" in
  setup)  cmd_setup ;;
  pull)   cmd_pull ;;
  push)   cmd_push ;;
  status) cmd_status ;;
  *) echo "Использование: $0 {setup|pull|push|status}"; exit 1 ;;
esac
