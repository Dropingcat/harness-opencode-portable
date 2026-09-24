#!/usr/bin/env bash
# gh_debt_survey.sh — запрос в GitHub API по GH_TOKEN: «ревизия» состояния техдолга в репо.
# Собирает: открытые debt-issues, последние закрытые, статусы PR, и сохраняет сводку в JSON.
# Использование: ./scripts/tools/gh_debt_survey.sh [out.json]
set -euo pipefail

API="https://api.github.com"
REPO="Dropingcat/harness-opencode-portable"
LABEL="tech-debt"
TOKEN="${GH_TOKEN:?GH_TOKEN не задан}"
OUT="${1:-/tmp/debt_survey.json}"

mask() { sed "s/${TOKEN}/***TOKEN***/g"; }

api() { # api PATH
  curl -sS -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
       -H "X-GitHub-Api-Version: 2022-11-28" "${API}$1"
}

api "/repos/$REPO/issues?state=open&labels=$LABEL&per_page=50"   > /tmp/_open.json
api "/repos/$REPO/issues?state=closed&labels=$LABEL&per_page=50" > /tmp/_closed.json
api "/repos/$REPO/pulls?state=all&per_page=30"                   > /tmp/_prs.json

python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1]
open_i  = json.load(open("/tmp/_open.json"))
closed_i = json.load(open("/tmp/_closed.json"))
prs     = json.load(open("/tmp/_prs.json"))
assert isinstance(open_i, list) and isinstance(closed_i, list), "API вернул ошибку вместо списка"
summary = {
    "repo": "Dropingcat/harness-opencode-portable",
    "open_debt_issues": [{"number": i["number"], "title": i["title"]} for i in open_i if "pull_request" not in i],
    "closed_debt_count": len([i for i in closed_i if "pull_request" not in i]),
    "recently_closed": [{"number": i["number"], "title": i["title"]} for i in closed_i if "pull_request" not in i][:10],
    "pulls": [{"number": p["number"], "state": p["state"], "merged": bool(p.get("merged_at")),
               "title": p["title"]} for p in prs],
}
json.dump(summary, open(out, "w"), ensure_ascii=False, indent=2)
print("SURVEY_SAVED", out)
print("OPEN_DEBT:", len(summary["open_debt_issues"]))
for i in summary["open_debt_issues"]:
    print("  #%s %s" % (i["number"], i["title"]))
print("CLOSED_DEBT_TOTAL:", summary["closed_debt_count"])
unmerged_open = [p for p in summary["pulls"] if p["state"] == "open"]
print("OPEN_PRS:", len(unmerged_open))
for p in unmerged_open:
    print("  PR #%s %s" % (p["number"], p["title"]))
PY
