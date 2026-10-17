# -*- coding: utf-8 -*-
import sqlite3, os, json, datetime, io, re
db = os.environ.get("OPENCODE_SESSION_DB", r"C:\Users\Arhys\.local\share\opencode\opencode.db")
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
out = []

# Distinctive phrases from the subagent contract (M0) that a dispatcher would embed
phrases = [
    "ПАКЕТ ИСПОЛНИТЕЛЬНОЙ ДОКУМЕНТАЦИИ",
    "АНАЛИТИК-СБОРЩИК",
    "кодеру осталось ТОЛЬКО КОДИТЬ",
    "Фабрика агентов должна заработать",
    "Документации для кодеров",
    "Пакет исполнительной",
    "документации для кодеров",
    "ef2f6384",
]

def text_of_data(d):
    """flatten all strings in the message data json"""
    parts = []
    if isinstance(d, str):
        parts.append(d)
        return " ".join(parts)
    def walk(o):
        if isinstance(o, str):
            parts.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(d)
    return " ".join(parts)

# 1) scan session_message data for phrases
cur.execute("SELECT session_id, seq, type, time_created, data FROM session_message ORDER BY time_created")
rows = cur.fetchall()
out.append("== session_message hits ==")
hits_seen = {}
for r in rows:
    try:
        j = json.loads(r["data"]) if isinstance(r["data"], str) else (r["data"] or {})
    except Exception:
        continue
    blob = text_of_data(j)
    low = blob
    found = [p for p in phrases if p.lower() in low.lower()]
    if found:
        sid = r["session_id"]
        tc = datetime.datetime.fromtimestamp(r["time_created"]/1000).strftime("%m-%d %H:%M:%S")
        key = (sid, r["seq"])
        if key in hits_seen:
            continue
        hits_seen[key] = True
        snippet = ""
        for p in found:
            idx = low.lower().find(p.lower())
            if idx >= 0:
                snippet = low[max(0,idx-80):idx+len(p)+120].replace("\n"," ")
                break
        out.append(f"[{tc}] {sid} type={r['type']} seq={r['seq']} phrases={found}")
        out.append("    ..." + snippet)
out.append(f"total message hits: {len(hits_seen)}")

# 2) sessions created on 10-05, full list
out.append("\n== sessions created 10-05 ==")
cur.execute("SELECT id, slug, title, agent, parent_id, directory, time_created FROM session_v2 WHERE time_created >= 1791180000000 AND time_created < 1791266400000 ORDER BY time_created")
for r in cur.fetchall():
    tc = datetime.datetime.fromtimestamp(r["time_created"]/1000).strftime("%m-%d %H:%M:%S")
    out.append(f"[{tc}] {r['id']} slug={r['slug']} agent={r['agent']} parent={r['parent_id']} dir={r['directory']}")
    out.append("    " + str(r["title"] or ""))

# 3) parents of the 10-05 code-auditor subagents
out.append("\n== parents of 10-05 subagents (silent-planet/proud-otter/sunny-falcon) ==")
for sub in ["ses_ef2c3988dffelNRWHRsk8dAQX2","ses_ef2a44509ffeTHlOiXIoAD1zDz","ses_ef2840ea0ffenr7utQENXmoqN8"]:
    cur.execute("SELECT id, slug, title, agent, parent_id, directory, time_created, time_updated FROM session_v2 WHERE id=?", (sub,))
    r = cur.fetchone()
    if r:
        d = dict(r)
        out.append(f"SUB {sub}: parent={d['parent_id']} agent={d['agent']} title={d['title']}")
        if d["parent_id"]:
            cur.execute("SELECT id, slug, title, agent, directory, time_created FROM session_v2 WHERE id=?", (d["parent_id"],))
            p = cur.fetchone()
            if p:
                pc = datetime.datetime.fromtimestamp(p["time_created"]/1000).strftime("%m-%d %H:%M:%S")
                out.append(f"   PARENT {p['id']} slug={p['slug']} agent={p['agent']} created={pc} dir={p['directory']} title={p['title']}")
conn.close()
outp = r"C:\Temp\opencode\parent_search.txt"
with io.open(outp, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done, message hits:", len(hits_seen))