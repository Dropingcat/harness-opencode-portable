#!/usr/bin/env python3
"""session_analyzer.py — канонический анализатор opencode-сессий.

Заменяет десятки ad-hoc скриптов (dump_session.py, analyze_*.py, scan_*.py,
probe_*.py) в C:\\Temp\\opencode. Единая точка анализа JSON-файла сессии
(opencode storage/session_diff/ses_*.json):

    dump    — сессия -> читаемый транскрипт (txt)
    tools   — статистика инструментов (кол-во, ошибки, fail-states)
    writes  — файлы, которые писались/редактировались (хронология)
    text    — текстовые сообщения ассистента (по роли)
    errors  — сбойные вызовы инструментов (статус != completed)

Usage:
    python session_analyzer.py dump   <session.json> [-o out.txt]
    python session_analyzer.py tools  <session.json>
    python session_analyzer.py writes <session.json>
    python session_analyzer.py text   <session.json> [--role assistant]
    python session_analyzer.py errors <session.json> [--limit 40]
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _load(p) -> dict:
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    # Сессии бывают dict {info, messages} или чистый list of messages (session_diff)
    if isinstance(data, list):
        return {"messages": data}
    return data


def _tool(part: dict) -> tuple[str, dict]:
    """Возвращает (имя, state) из tool-части."""
    tool = part.get("tool")
    if isinstance(tool, str):
        return tool, part.get("state", {}) or {}
    if isinstance(tool, dict):
        return tool.get("name", "?"), tool.get("state", {}) or {}
    return "?", {}


def cmd_dump(args) -> int:
    d = _load(args.session)
    out_lines = []
    for idx, m in enumerate(d.get("messages", [])):
        info = m.get("info", {})
        role = info.get("role", "?")
        t = info.get("time", {}).get("created", 0)
        out_lines.append(f"=== msg[{idx}] role={role} created={t} ===")
        for part in m.get("parts", []):
            pt = part.get("type", "?")
            if pt == "text":
                out_lines.append("[TEXT] " + part.get("text", ""))
            elif pt == "tool":
                name, st = _tool(part)
                st = st if isinstance(st, dict) else {}
                inp = json.dumps(st.get("input", {}), ensure_ascii=False)
                out_lines.append(f"[TOOL] name={name} status={st.get('status')} input={inp[:500]}")
                outv = st.get("output", "")
                if outv:
                    out_lines.append("  [OUT] " + str(outv)[:500])
            elif pt == "reasoning":
                out_lines.append("[REASONING] " + str(part.get("text", ""))[:500])
            elif pt == "patch":
                out_lines.append("[PATCH] " + str(part.get("text", ""))[:200])
            elif pt == "file":
                out_lines.append("[FILE] " + str(part.get("file", {}))[:300])
            elif pt in ("step-start", "step-finish"):
                extra = {k: v for k, v in part.items() if k not in ("id", "sessionID", "messageID", "type")}
                out_lines.append(f"[{pt.upper()}] " + json.dumps(extra, ensure_ascii=False)[:300])
            else:
                out_lines.append(f"[{pt.upper()}] " + str(part)[:300])
    text = "\n\n".join(out_lines)
    if args.o:
        Path(args.o).write_text(text, encoding="utf-8")
        print(f"written: {args.o} ({len(out_lines)} строк)")
    else:
        sys.stdout.write(text + "\n")
    return 0


def cmd_tools(args) -> int:
    d = _load(args.session)
    counts = collections.Counter()
    fails = collections.Counter()
    states = collections.Counter()
    for m in d.get("messages", []):
        for part in m.get("parts", []):
            if part.get("type") != "tool":
                continue
            name, st = _tool(part)
            st = st if isinstance(st, dict) else {}
            counts[name] += 1
            status = st.get("status", "?")
            states[status] += 1
            if status != "completed":
                fails[name] += 1
    print("=== TOOL USAGE ===")
    for name, cnt in counts.most_common():
        print(f"{name:35s} total={cnt:5d} failed={fails.get(name, 0)}")
    print("\n=== STATUS DIST ===")
    for s, c in states.most_common():
        print(f"  {s}: {c}")
    return 0


def cmd_writes(args) -> int:
    d = _load(args.session)
    for m in d.get("messages", []):
        t = m.get("info", {}).get("time", {}).get("created", 0)
        for part in m.get("parts", []):
            if part.get("type") != "tool":
                continue
            name, st = _tool(part)
            st = st if isinstance(st, dict) else {}
            inp = st.get("input", {})
            if not isinstance(inp, dict):
                continue
            if name == "write":
                print(f"[{t}] WRITE  {inp.get('filePath', '?')}")
            elif name == "edit":
                print(f"[{t}] EDIT   {inp.get('filePath', '?')}")
            elif name == "patch":
                print(f"[{t}] PATCH  (inline)")
    return 0


def cmd_text(args) -> int:
    d = _load(args.session)
    for m in d.get("messages", []):
        if args.role and m.get("info", {}).get("role") != args.role:
            continue
        t = m.get("info", {}).get("time", {}).get("created", 0)
        for part in m.get("parts", []):
            if part.get("type") == "text":
                txt = part.get("text", "")
                if txt.strip():
                    print(f"--- [{t}] ---")
                    print(txt[: args.limit_chars])
                    print()
    return 0


def cmd_errors(args) -> int:
    d = _load(args.session)
    n = 0
    for m in d.get("messages", []):
        t = m.get("info", {}).get("time", {}).get("created", 0)
        for part in m.get("parts", []):
            if part.get("type") != "tool":
                continue
            name, st = _tool(part)
            st = st if isinstance(st, dict) else {}
            if st.get("status") == "error":
                inp = json.dumps(st.get("input", {}), ensure_ascii=False)
                out = str(st.get("output", ""))
                print(f"[{t}] {name} ERROR")
                print(f"   IN:  {inp[:400]}")
                print(f"   OUT: {out[:300]}")
                print()
                n += 1
                if n >= args.limit:
                    return 0
    if n == 0:
        print("Ошибок не найдено")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Канонический анализатор opencode-сессий")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("dump")
    p.add_argument("session")
    p.add_argument("-o", default=None)
    p.set_defaults(fn=cmd_dump)

    p = sub.add_parser("tools")
    p.add_argument("session")
    p.set_defaults(fn=cmd_tools)

    p = sub.add_parser("writes")
    p.add_argument("session")
    p.set_defaults(fn=cmd_writes)

    p = sub.add_parser("text")
    p.add_argument("session")
    p.add_argument("--role", default=None)
    p.add_argument("--limit-chars", type=int, default=1200)
    p.set_defaults(fn=cmd_text)

    p = sub.add_parser("errors")
    p.add_argument("session")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_errors)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())