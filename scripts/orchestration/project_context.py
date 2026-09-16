import sqlite3
from pathlib import Path
import json
import re


def _harness_root():
    import os
    env = os.environ.get("OPENCODE_HARNESS_ROOT")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def board(kb: Path, limit: int = 8):
    if not kb.exists():
        return {"error": f"kanban.db отсутствует: {kb}"}
    try:
        conn = sqlite3.connect(str(kb))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT s.*, a.group_name FROM statuses s "
            "JOIN agents a ON s.agent_id = a.id "
            "ORDER BY s.created_at DESC LIMIT ?", (min(limit, 50),)
        ).fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            out.append({
                "agent_id": d.get("agent_id"), "task_name": d.get("task_name"),
                "status": d.get("status"), "phase": d.get("phase"),
                "progress": d.get("progress"), "message": (d.get("message") or "")[:120],
                "created_at": d.get("created_at"),
                "group_name": d.get("group_name"),  # секция канбана (code-factory/writing/research)
            })
        return {"rows": out}
    except Exception as e:
        return {"error": str(e)}


def tech_debt(root: Path):
    p = root / "config" / "tech_debt.json"
    if not p.exists():
        return {"error": "tech_debt.json отсутствует"}
    try:
        d = json.load(open(p, encoding="utf-8-sig"))
        debts = d.get("debts", [])
        open_debts = [x for x in debts if x.get("status") == "open"]
        return {"total": len(debts), "open": len(open_debts), "ids": [x.get("id") for x in open_debts]}
    except Exception as e:
        return {"error": str(e)}


def tracker(root: Path):
    """Извлекает открытые задачи из IMPLEMENTATION_TRACKER.md (checkbox - [ ])."""
    p = root / "IMPLEMENTATION_TRACKER.md"
    if not p.exists():
        return {"error": "tracker отсутствует"}
    try:
        t = p.read_text(encoding="utf-8")
        ws = []
        lines = t.splitlines()
        cur_ws = None
        for ln in lines:
            m = re.match(r"^###\s+(.+)$", ln)
            if m:
                cur_ws = m.group(1).strip()[:80]
                continue
            if "- [ ]" in ln or "☐" in ln:
                ws.append({"ws": cur_ws, "item": ln[ln.index("]") + 1:].strip()[:110] if "]" in ln else ln.strip()[:110]})
        return {"open_items": ws}
    except Exception as e:
        return {"error": str(e)}


def memory_lessons(root: Path, limit: int = 5):
    p = root / "config" / "memory_registry.json"
    if not p.exists():
        return {"error": "memory_registry.json отсутствует"}
    try:
        d = json.load(open(p, encoding="utf-8-sig"))
        ls = d.get("levels", {}).get("L3", {}).get("lessons", {})
        items = []
        for k, v in ls.items():
            if isinstance(v, dict):
                items.append({"id": k, "text": (v.get("lesson_text") or v.get("lesson") or v.get("text") or "")[:120], "admissions": v.get("admissions", 0)})
        items.sort(key=lambda x: -x["admissions"])
        return {"count": len(items), "recent": items[:limit]}
    except Exception as e:
        return {"error": str(e)}


def factory_state(root: Path):
    p = root / ".runs" / "factory_state.json"
    if not p.exists():
        return {"state": None}
    try:
        d = json.load(open(p, encoding="utf-8-sig"))
        c = d.get("cycle", {})
        return {"state": c.get("state"), "attempt": c.get("attempt"), "rework_rounds": c.get("rework_rounds")}
    except Exception as e:
        return {"error": str(e)}


def portal_refs(root: Path):
    docs = ["ARCHITECTURE.md", "MANIFEST.md", "CONTRIBUTING.md", "README.md", "GLOBAL_TASK_CONTROLLER.md", "CAPABILITY_REGISTRY.md"]
    return [d for d in docs if (root / d).exists()]


def main():
    root = _harness_root()
    ctx = {
        "root": str(root),
        "kanban": board(root / ".kanban.db"),
        "tech_debt": tech_debt(root),
        "tracker": tracker(root),
        "memory_l3": memory_lessons(root),
        "factory": factory_state(root),
        "portal_docs": portal_refs(root),
    }
    # Portable UTF-8 output: avoid UnicodeEncodeError on cp1251 Windows consoles.
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(json.dumps(ctx, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()