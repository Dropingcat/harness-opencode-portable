#!/usr/bin/env bash
# gh_take_debt.sh — взять следующий тезис техдолга через запрос к GitHub API (REST) по GH_TOKEN.
# Использование:
#   ./scripts/tools/gh_take_debt.sh claim  "<title>" "<body-file>"   # создать issue, пометить, вернуть номер
#   ./scripts/tools/gh_take_debt.sh comment <issue-number> "<body-file>"
#   ./scripts/tools/gh_take_debt.sh close  <issue-number> "<comment-body-file>"
#   ./scripts/tools/gh_take_debt.sh list                             # открытые debt-issues
set -euo pipefail

API="https://api.github.com"
REPO="Dropingcat/harness-opencode-portable"
LABEL="tech-debt"
TOKEN="${GH_TOKEN:?GH_TOKEN не задан}"

mask() { sed "s/${TOKEN}/***TOKEN***/g"; }

api() { # api METHOD PATH [json-file]
  local method="$1" path="$2" body="${3:-}"
  local args=(-sS -X "$method" -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")
  [[ -n "$body" ]] && args+=(-d "@$body")
  curl "${args[@]}" "${API}${path}"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  claim)
    title="$1"; bodyfile="$2"
    payload=$(python3 -c '
import json,sys
print(json.dumps({"title": sys.argv[1], "body": open(sys.argv[2]).read(), "labels": [sys.argv[3]]}))' "$title" "$bodyfile" "$LABEL")
    echo "$payload" > /tmp/claim.json
    resp=$(api POST "/repos/$REPO/issues" /tmp/claim.json)
    num=$(echo "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("number",""))')
    if [[ -z "$num" ]]; then echo "$resp" | mask >&2; exit 1; fi
    echo "CLAIMED issue #$num"
    ;;
  comment)
    num="$1"; bodyfile="$2"
    payload=$(python3 -c 'import json,sys; print(json.dumps({"body": open(sys.argv[1]).read()}))' "$bodyfile")
    echo "$payload" > /tmp/comment.json
    api POST "/repos/$REPO/issues/$num/comments" /tmp/comment.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print("COMMENT_OK", d.get("html_url",""))'
    ;;
  close)
    num="$1"; bodyfile="$2"
    payload=$(python3 -c 'import json,sys; print(json.dumps({"body": open(sys.argv[1]).read(), "state":"closed"}))' "$bodyfile")
    echo "$payload" > /tmp/close.json
    api PATCH "/repos/$REPO/issues/$num" /tmp/close.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print("CLOSED", d.get("number"), d.get("state"))'
    ;;
  list)
    api GET "/repos/$REPO/issues?state=open&labels=$LABEL&per_page=20" | python3 -c '
import json,sys
for i in json.load(sys.stdin):
    print("#%s [%s] %s" % (i["number"], i["state"], i["title"]))'
    ;;
  *)
    echo "Использование: $0 {claim|comment|close|list} ..." >&2; exit 1;;
esac
