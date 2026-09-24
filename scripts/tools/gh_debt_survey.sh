#!/usr/bin/env bash
# gh_debt_survey.sh — запросы в GitHub API по GH_TOKEN: ревизия техдолга + операции с debt-issues.
# Использование:
#   ./scripts/tools/gh_debt_survey.sh survey [out.json]                     # сводка: открытые/закрытые issues, PR (по умолчанию stdout)
#   ./scripts/tools/gh_debt_survey.sh claim "<title>" "<body-file>"         # создать debt-issue, вернуть номер
#   ./scripts/tools/gh_debt_survey.sh comment <issue-number> "<body-file>"  # комментарий к issue
#   ./scripts/tools/gh_debt_survey.sh close <issue-number> "<body-file>"    # закрыть issue с финальным комментарием
#   ./scripts/tools/gh_debt_survey.sh list                                  # открытые debt-issues
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=gh_debt_api.sh
source "$DIR/gh_debt_api.sh"

die() { echo "ОШИБКА: $*" >&2; exit 1; }
# need_args N "$@" — проверить число аргументов ПОДКОМАНДЫ (без set -u ловушек)
need_args() {
  local n="$1"; shift
  (( $# >= n )) || die "недостаточно аргументов для подкоманды '$CMD' (ожидалось >=$n, получено $#). См. использование в шапке скрипта."
}
is_int() { [[ "$1" =~ ^[0-9]+$ ]] || die "требуется номер issue (целое), получено: '$1'"; }
check_bodyfile() { [[ -f "$1" ]] || die "файл тела не найден: '$1'"; }

CMD="${1:-}"; shift || true
case "$CMD" in
  survey)
    OUT="${1:-}"
    api_get() { gh_api GET "$1"; }
    api_get "/repos/$GH_REPO/issues?state=open&labels=$GH_LABEL&per_page=50"   > /tmp/_open.json
    api_get "/repos/$GH_REPO/issues?state=closed&labels=$GH_LABEL&per_page=50" > /tmp/_closed.json
    api_get "/repos/$GH_REPO/pulls?state=all&per_page=30"                      > /tmp/_prs.json
    python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1] or None
open_i   = json.load(open("/tmp/_open.json"))
closed_i = json.load(open("/tmp/_closed.json"))
prs      = json.load(open("/tmp/_prs.json"))
assert isinstance(open_i, list) and isinstance(closed_i, list), "API вернул ошибку вместо списка"
summary = {
    "repo": __import__("os").environ.get("GH_REPO", "Dropingcat/harness-opencode-portable"),
    "open_debt_issues": [{"number": i["number"], "title": i["title"]} for i in open_i if "pull_request" not in i],
    "closed_debt_count": len([i for i in closed_i if "pull_request" not in i]),
    "recently_closed": [{"number": i["number"], "title": i["title"]} for i in closed_i if "pull_request" not in i][:10],
    "pulls": [{"number": p["number"], "state": p["state"], "merged": bool(p.get("merged_at")),
               "title": p["title"]} for p in prs],
}
if out:
    json.dump(summary, open(out, "w"), ensure_ascii=False, indent=2)
    print("SURVEY_SAVED", out)
else:
    print(json.dumps(summary, ensure_ascii=False, indent=2))
print("OPEN_DEBT:", len(summary["open_debt_issues"]))
for i in summary["open_debt_issues"]:
    print("  #%s %s" % (i["number"], i["title"]))
print("CLOSED_DEBT_TOTAL:", summary["closed_debt_count"])
open_prs = [p for p in summary["pulls"] if p["state"] == "open"]
print("OPEN_PRS:", len(open_prs))
for p in open_prs:
    print("  PR #%s %s" % (p["number"], p["title"]))
PY
    ;;
  claim)
    need_args 2 "$@"
    title="$1"; bodyfile="$2"; check_bodyfile "$bodyfile"
    payload=$(python3 -c 'import json,sys
print(json.dumps({"title": sys.argv[1], "body": open(sys.argv[2]).read(), "labels": [sys.argv[3]]}))' "$title" "$bodyfile" "$GH_LABEL")
    tmp=$(mktemp); echo "$payload" > "$tmp"
    resp=$(gh_api POST "/repos/$GH_REPO/issues" "$tmp"); rm -f "$tmp"
    num=$(echo "$resp" | python3 -c 'import json,sys
try: d=json.load(sys.stdin); print(d.get("number",""))
except Exception: print("")')
    [[ -n "$num" ]] || { echo "$resp" >&2; die "не удалось создать issue (см. ответ API выше)"; }
    echo "CLAIMED issue #$num"
    ;;
  comment)
    need_args 2 "$@"
    num="$1"; bodyfile="$2"; is_int "$num"; check_bodyfile "$bodyfile"
    tmp=$(mktemp); python3 -c 'import json,sys; print(json.dumps({"body": open(sys.argv[1]).read()}))' "$bodyfile" > "$tmp"
    resp=$(gh_api POST "/repos/$GH_REPO/issues/$num/comments" "$tmp"); rm -f "$tmp"
    echo "$resp" | python3 -c 'import json,sys
d=json.load(sys.stdin)
if "html_url" in d: print("COMMENT_OK", d["html_url"])
else: sys.exit("ОШИБКА API: " + json.dumps(d))'
    ;;
  close)
    need_args 2 "$@"
    num="$1"; bodyfile="$2"; is_int "$num"; check_bodyfile "$bodyfile"
    tmp=$(mktemp); python3 -c 'import json,sys; print(json.dumps({"body": open(sys.argv[1]).read(), "state": "closed"}))' "$bodyfile" > "$tmp"
    resp=$(gh_api PATCH "/repos/$GH_REPO/issues/$num" "$tmp"); rm -f "$tmp"
    echo "$resp" | python3 -c 'import json,sys
d=json.load(sys.stdin)
if d.get("state") == "closed": print("CLOSED", d.get("number"), d.get("state"))
else: sys.exit("ОШИБКА API: " + json.dumps(d))'
    ;;
  list)
    gh_api GET "/repos/$GH_REPO/issues?state=open&labels=$GH_LABEL&per_page=50" | python3 -c '
import json,sys
data = json.load(sys.stdin)
if isinstance(data, dict): sys.exit("ОШИБКА API: " + json.dumps(data))
items = [i for i in data if "pull_request" not in i]
if not items: print("NO_OPEN_DEBT_ISSUES")
for i in items:
    print("#%s [%s] %s" % (i["number"], i["state"], i["title"]))'
    ;;
  ""|-h|--help|help)
    grep '^# ' "$0" | sed 's/^# //' | grep -v 'shellcheck'
    exit $([[ -z "$CMD" ]] && echo 1 || echo 0)
    ;;
  *)
    die "неизвестная подкоманда '$CMD'. Доступные: survey|claim|comment|close|list"
    ;;
esac
