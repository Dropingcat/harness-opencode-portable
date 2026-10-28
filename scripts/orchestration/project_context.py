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


def _tracker_object(pairs):
    """Do not silently accept duplicate JSON keys (including counts/readiness)."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _structured_tracker(path: Path):
    # Resolve executable code relative to this module, never the supplied data root.
    import importlib.util
    validator_path = Path(__file__).resolve().parents[1] / "tools/check_development_tracker.py"
    spec = importlib.util.spec_from_file_location("_context_tracker_validator", validator_path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_tracker_object)
    if not isinstance(data, dict):
        raise ValueError("tracker must be an object")
    records = []
    for group, pattern in (("dev_items", r"DEV-\d+"), ("workstreams", r"WS-\d+[A-Z]?")):
        items = data.get(group)
        if not isinstance(items, list):
            raise ValueError(f"{group} must be a list")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"{group} records must be objects")
            if not isinstance(item.get("id"), str) or not re.fullmatch(pattern, item["id"]):
                raise ValueError(f"invalid {group} ID")
            for key in ("title", "status"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    raise ValueError(f"invalid {key}: {item['id']}")
            for key in ("evidence", "next_gate", "completion_scope"):
                if key in item and not isinstance(item[key], str):
                    raise ValueError(f"invalid {key}: {item['id']}")
            if "production_ready" in item and type(item["production_ready"]) is not bool:
                raise ValueError(f"invalid production_ready: {item['id']}")
            refs = item.get("internal_refs", [])
            if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                raise ValueError(f"invalid internal_refs: {item['id']}")
            if "current_readiness" in item:
                readiness = item["current_readiness"]
                if not isinstance(readiness, dict):
                    raise ValueError(f"invalid current_readiness: {item['id']}")
                if any(not isinstance(readiness.get(key), str) for key in
                       ("host_version", "scope") + validator.DIMENSIONS):
                    raise ValueError(f"invalid readiness fields: {item['id']}")
                sources = readiness.get("external_sources")
                if (not isinstance(sources, list) or not sources or
                        any(not isinstance(source, str) or not source.strip() for source in sources)):
                    raise ValueError(f"invalid readiness sources: {item['id']}")
            records.append(item)
    counts = data.get("counts")
    if not isinstance(counts, dict) or any(type(n) is not int or n < 0 for n in counts.values()):
        raise ValueError("counts must contain nonnegative integers")
    critical = data.get("critical_path", [])
    if not isinstance(critical, list) or any(not isinstance(ref, str) for ref in critical):
        raise ValueError("critical_path must be a list of IDs")
    errors = validator.check(data)
    if errors:
        raise ValueError("; ".join(errors))
    current = [{**item["current_readiness"], "id": item["id"], "declared_status": item["status"]}
               for item in records if "current_readiness" in item]
    pending = [item["id"] for item in current
               if any(item[key] != "PASS" for key in validator.DIMENSIONS)]
    open_items = []
    for item in records:
        if item["status"] != "done" or item["id"] in pending:
            label = f"{item['title']} [declared: {item['status']}]"
            if item["id"] in pending:
                readiness = item["current_readiness"]
                label += f" [host {readiness['host_version']}: current readiness incomplete]"
            open_items.append({"ws": item["id"], "item": label})
    return {
        "validation": "PASS", "counts": counts, "declared_items": records,
        "open_items": open_items,
        "current_host_readiness": {
            "authority": "Declared tracker facts only; not runtime certification",
            "host_versions": sorted({item["host_version"] for item in current}),
            "items": current, "pending_ids": pending,
            "unassessed_ids": [item["id"] for item in records if "current_readiness" not in item],
        },
    }


def tracker(root: Path):
    """Prefer the validated structured tracker; legacy is absence-only fallback."""
    structured = root / "config" / "development_tracker.json"
    legacy = root / "IMPLEMENTATION_TRACKER.md"
    metadata = {"legacy_present": legacy.exists()}
    if structured.exists() or structured.is_symlink():
        metadata.update(source=str(structured), source_format="structured_json")
        try:
            return {**metadata, **_structured_tracker(structured)}
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError) as exc:
            return {**metadata, "validation": "FAIL", "error": f"invalid structured tracker: {exc}"}
    metadata.update(
        source=str(legacy) if metadata["legacy_present"] else None,
        source_format="legacy_markdown" if metadata["legacy_present"] else None,
    )
    return {**metadata, **_legacy_tracker(root)}


def _legacy_tracker(root: Path):
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
