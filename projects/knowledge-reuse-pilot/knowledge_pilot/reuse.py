"""Conservative reuse: explicit declared coverage + current input/output hashes."""
from pathlib import Path
from collections import deque
import json
import time
import uuid

from .catalog import digest_file


def normalize(value):
    return " ".join(str(value).casefold().split())


def reference(catalog, value):
    path = Path(value).resolve()
    if not (catalog.allowed(path) or catalog.managed(path)) or not path.is_file():
        raise ValueError(f"not an existing allowed corpus file: {path}")
    if path.stat().st_size > catalog.max_file_bytes:
        raise ValueError("explicit evidence exceeds the file-size policy")
    return {"id": catalog.ident(path), "path": str(path), "sha256": digest_file(path)}


def register(catalog, artifact, *, coverage, inputs, status, gaps=None, preserve_disposition=False):
    if status not in {"accepted", "draft", "superseded", "rejected"}:
        raise ValueError("unsupported declared artifact status")
    if not coverage or len(coverage) > 64 or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in coverage):
        raise ValueError("coverage requires bounded nonempty question strings")
    if status == "accepted" and not inputs:
        raise ValueError("an accepted derived report requires explicit input references")
    output = reference(catalog, artifact)
    input_refs = []
    for value in inputs:
        ref = reference(catalog, value["path"] if isinstance(value, dict) else value)
        if isinstance(value, dict) and value.get("sha256") != ref["sha256"]:
            raise ValueError("explicit input revision is no longer current")
        input_refs.append(ref)
    if any(x["id"] == output["id"] for x in input_refs):
        raise ValueError("an artifact cannot derive from itself")
    if catalog.managed(output["path"]):
        counts = {"extracted": 0, "unchanged": 0}
        catalog._scan_file(Path(output["path"]), "pilot-results", "managed", counts)
    coverage_json = json.dumps(sorted(set(normalize(x) for x in coverage)), ensure_ascii=False)
    inputs_json = json.dumps(input_refs, sort_keys=True, ensure_ascii=False)
    gaps_json = json.dumps(gaps or [], ensure_ascii=False)
    record = (output["path"], output["sha256"], status, coverage_json, inputs_json, gaps_json)
    with catalog.db() as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM registrations WHERE path=? ORDER BY seq DESC LIMIT 1", (output["path"],)).fetchone()
        for question in coverage:
            db.execute("INSERT OR IGNORE INTO artifact_mentions VALUES (?,?,?)", (output["path"], output["sha256"], normalize(question)))
        same_record = old and tuple(old[k] for k in ("path", "hash", "status", "coverage", "inputs", "gaps")) == record
        preserved = old and preserve_disposition and old["hash"] == output["sha256"]
        if same_record or preserved:
            return {"id": old["id"], "reused_registration": True, "artifact": output, "status": old["status"], "disposition_preserved": bool(preserved)}
        ident = uuid.uuid4().hex
        db.execute("INSERT INTO registrations (id,path,hash,status,coverage,inputs,gaps,created) VALUES (?,?,?,?,?,?,?,?)", (ident, *record, time.time()))
        for source in input_refs:
            db.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?,?)", (output["id"], output["sha256"], source["id"], source["sha256"], "derived_from", "explicit_registration"))
    return {"id": ident, "reused_registration": False, "artifact": output, "status": status, "acceptance": "declared; not independent fact certification"}


def dependency_reasons(catalog, row, heads):
    """Validate the declared dependency closure; never treat a cycle as evidence."""
    reasons, checked = [], set()
    pending = [(row, frozenset())]
    while pending and len(checked) < 128 and len(reasons) < 16:
        current, ancestors = pending.pop()
        if current["path"] in ancestors:
            reasons.append({"path": current["path"], "reason": "dependency_cycle"})
            continue
        if current["path"] in checked:
            continue
        checked.add(current["path"])
        inputs = json.loads(current["inputs"])
        for item in [{"path": current["path"], "sha256": current["hash"]}] + inputs:
            try:
                actual = reference(catalog, item["path"])
                if actual["sha256"] != item["sha256"]:
                    reasons.append({"path": item["path"], "reason": "content_changed", "expected": item["sha256"], "actual": actual["sha256"]})
            except (ValueError, OSError) as exc:
                reasons.append({"path": item["path"], "reason": "missing_or_out_of_scope", "detail": str(exc)[:200]})
        for item in inputs:
            upstream = heads.get(item["path"])
            if upstream:
                if upstream["status"] != "accepted" or upstream["hash"] != item["sha256"]:
                    reasons.append({"path": item["path"], "reason": "upstream_disposition_or_revision_changed", "status": upstream["status"]})
                else:
                    pending.append((upstream, ancestors | {current["path"]}))
        if len(pending) > 128:
            reasons.append({"reason": "dependency_budget_exceeded"})
            break
    if pending and not reasons:
        reasons.append({"reason": "dependency_budget_exceeded"})
    return reasons[:16]


def apply_reuse(catalog, answer):
    with catalog.db() as db:
        rows = db.execute("SELECT * FROM registrations ORDER BY seq DESC").fetchall()
    heads = {}
    for row in rows:
        heads.setdefault(row["path"], row)
    seen = set()
    eligible = []
    for row in rows:
        if row["path"] in seen:
            continue
        seen.add(row["path"])
        if normalize(answer["question"]) in json.loads(row["coverage"]):
            eligible.append(row)
    stale, excluded = [], []
    for row in eligible:
        if row["status"] != "accepted":
            excluded.append({"path": row["path"], "status": row["status"]})
            continue
        reasons = dependency_reasons(catalog, row, heads)
        if reasons:
            stale.extend(reasons)
            continue
        gaps = json.loads(row["gaps"])
        return {**answer, "action": "EXTEND" if gaps else "REUSE", "read_next": [{"path": row["path"], "sha256": row["hash"], "registration": row["id"]}], "inputs": json.loads(row["inputs"]), "gaps": gaps, "acceptance": "declared; not independent fact certification", "stale_reasons": [], "excluded_reports": excluded}
    return {**answer, "action": "REVALIDATE" if stale else answer["action"], "stale_reasons": stale, "excluded_reports": excluded}


def trace(catalog, artifact, depth):
    byte_budget, used, truncated = 18000, 0, False
    depth = max(0, min(int(depth), 8))
    nodes, edges = [], []

    def append_bounded(collection, item):
        nonlocal used, truncated
        size = len(json.dumps(item, ensure_ascii=True).encode("utf-8")) + 2
        if used + size > byte_budget:
            truncated = True
            return False
        collection.append(item)
        used += size
        return True

    with catalog.db() as db:
        row = db.execute("SELECT * FROM files WHERE id=? OR path=?", (artifact, str(Path(artifact).resolve()))).fetchone()
        if not row:
            return {"found": False, "nodes": [], "edges": []}
        pending = deque([(row["id"], row["hash"], 0)])
        visited, enqueued = set(), {(row["id"], row["hash"])}
        while pending and len(visited) < 64:
            ident, digest, level = pending.popleft()
            if (ident, digest) in visited:
                continue
            visited.add((ident, digest))
            current = db.execute("SELECT path,hash,status FROM files WHERE id=?", (ident,)).fetchone()
            external = db.execute("SELECT uri FROM externals WHERE id=?", (ident,)).fetchone()
            if not append_bounded(nodes, {"id": ident, "sha256": digest, "path": current["path"] if current else None, "uri": external["uri"] if external else None, "current_revision": bool(current and current["hash"] == digest), "status": current["status"] if current else "external_locator" if external else "unindexed"}):
                break
            if level >= depth:
                if db.execute("SELECT 1 FROM edges WHERE source_id=? AND source_hash=? LIMIT 1", (ident, digest)).fetchone():
                    truncated = True
                continue
            cursor = db.execute("SELECT * FROM edges WHERE source_id=? AND source_hash=? ORDER BY target,target_hash,relation LIMIT ?", (ident, digest, 129 - len(edges)))
            for edge in cursor:
                if len(edges) >= 128 or not append_bounded(edges, dict(edge)):
                    truncated = True
                    break
                key = (edge["target"], edge["target_hash"])
                if key not in enqueued:
                    if len(enqueued) < 64:
                        enqueued.add(key)
                        pending.append((*key, level + 1))
                    else:
                        truncated = True
    return {"found": True, "nodes": nodes, "edges": edges, "truncated": truncated or bool(pending),
            "limits": {"nodes": 64, "edges": 128, "json_bytes": 20000, "depth": depth},
            "authority": "explicit observed links; not inferred fact support"}
