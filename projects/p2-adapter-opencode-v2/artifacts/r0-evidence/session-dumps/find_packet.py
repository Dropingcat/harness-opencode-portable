# -*- coding: utf-8 -*-
import sqlite3, os, json, datetime
db = os.environ.get("OPENCODE_SESSION_DB", r"C:\Users\Arhys\.local\share\opencode\opencode.db")
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
out = []

needles = ["Пакет", "пакет", "документац", "кодер", "CODERS", "исполнительн", "handoff", "доставочн", "шаблон"]

def has_needle(s):
    for n in needles:
        if n.lower() in s.lower():
            return n
    return None

# 1) titles in both tables
for tbl in ("session_v2", "session"):
    cur.execute(f"SELECT id, slug, title, agent, parent_id, directory, time_created FROM {tbl}")
    for r in cur.fetchall():
        t = str(r["title"] or "")
        n = has_needle(t)
        if n:
            tc = datetime.datetime.fromtimestamp(r["time_created"]/1000).strftime("%m-%d %H:%M")
            out.append(f"[TITLE|{tbl}|{n}][{tc}] {r['id']} slug={r['slug']} agent={r['agent']} parent={r['parent_id']} dir={r['directory']}")
            out.append("    " + t)

# 2) subagent descriptions in synthetic messages
cur.execute("SELECT session_id, seq, time_created, data FROM session_message WHERE type='synthetic'")
cnt = 0
for r in cur.fetchall():
    try:
        j = json.loads(r["data"]) if isinstance(r["data"], str) else (r["data"] or {})
    except Exception:
        continue
    txt = str(j.get("text") or "")
    n = has_needle(txt)
    if n and "<subagent" in txt:
        cnt += 1
        tc = datetime.datetime.fromtimestamp(r["time_created"]/1000).strftime("%m-%d %H:%M")
        # extract description attr
        import re
        m = re.search(r'description="([^"]*)"', txt)
        desc = m.group(1) if m else txt[:120]
        out.append(f"[SUBAGENT|{n}][{tc}] session={r['session_id']} seq={r['seq']}")
        out.append("    desc: " + desc)
out.append(f"summary: subagent-description hits={cnt}")
open(r"C:\Temp\opencode\packet_found.txt", "w", encoding="utf-8").write("\n".join(out))
print("done subagent hits:", cnt)
conn.close()