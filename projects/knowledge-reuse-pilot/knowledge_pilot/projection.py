"""Graphify-compatible graph and deterministic wiki links from the SAME catalog."""
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
import re

from .lease import FileLease, LeaseBusy
from .paths import checked_output


PROJECTION_VERSION = "artifact-navigation/2"


def _write(path, text, root=None):
    from .paths import write_text
    if root is None:
        from .runtime import HOME
        root = HOME
    return write_text(path, text, root)


def export_catalog(catalog):
    try:
        with FileLease(catalog.home / "state/projection.lease", catalog.home):
            return _export_catalog(catalog)
    except LeaseBusy:
        return {"status": "blocked", "reason": "another projection export is active"}


def _export_catalog(catalog):
    outputs = {}

    def emit(path, text):
        outputs[str(path.relative_to(catalog.home))] = sha256(text.encode("utf-8")).hexdigest()
        return _write(path, text, catalog.home)

    with catalog.db() as db:
        db.execute("BEGIN")
        files = {row["id"]: dict(row) for row in db.execute("SELECT * FROM files ORDER BY path")}
        edges = [dict(row) for row in db.execute("SELECT * FROM edges ORDER BY source_id,source_hash,target,relation")]
        externals = {row["id"]: row["uri"] for row in db.execute("SELECT * FROM externals")}
        coverage = db.execute("SELECT value FROM meta WHERE key='coverage'").fetchone()
        dispositions = {}
        for record in db.execute("SELECT path,hash,status FROM registrations ORDER BY seq DESC"):
            dispositions.setdefault((record["path"], record["hash"]), record["status"])
    nodes = {}
    links = []
    scope_ids = {name: i for i, name in enumerate(sorted(set(catalog.roots) | {row["root"] for row in files.values()}))}

    def node(ident, digest):
        key = f"artifact:{ident}:{digest or 'unindexed'}"
        if key not in nodes:
            row = files.get(ident, {})
            path = row.get("path")
            current = bool(row and row.get("hash") == digest and row.get("status") != "missing")
            uri = externals.get(ident)
            nodes[key] = {"id": key, "label": Path(path).name if path else uri or ident,
                          "source_file": path or uri or "", "source_location": f"sha256:{digest or 'not-extracted'}",
                          "community": scope_ids.get(row.get("root"), -1),
                          "attributes": {"root": row.get("root", "unknown"), "status": row.get("status", "unindexed"), "disposition": dispositions.get((path, digest), "undeclared"), "sha256": digest or "", "current_revision": str(current), "historical_bytes_retained": "false"}}
        return key

    for ident, row in files.items():
        node(ident, row["hash"])
    for edge in edges:
        links.append({"source": node(edge["source_id"], edge["source_hash"]),
                      "target": node(edge["target"], edge["target_hash"]),
                      "relation": edge["relation"], "confidence": "EXTRACTED",
                      "origin": edge["origin"], "meaning": "explicit reference, not proof of factual truth"})
    graph = {"directed": True, "multigraph": True,
             "graph": {"schema_version": PROJECTION_VERSION, "producer": "knowledge-reuse-pilot", "communities": "corpus scopes, not inferred clusters"},
             "nodes": sorted(nodes.values(), key=lambda x: x["id"]), "links": links}
    graph_path = catalog.home / "graphify-out/graph.json"
    changed = emit(graph_path, json.dumps(graph, ensure_ascii=False, sort_keys=True, indent=1))
    groups = defaultdict(list)
    outgoing = defaultdict(list)
    for edge in edges:
        outgoing[edge["source_id"]].append(edge)
    for ident, row in files.items():
        name = re.sub(r"[\[\]\r\n]", "_", Path(row["path"]).name)
        groups[row["root"]].append(f"- [{name}](artifacts/{ident}.md) — `{row['status']}`")
        lines = [f"# {name}", "", f"Source location: {Path(row['path']).as_uri()}",
                 f"Scope: `{row['root']}`", f"Extraction: `{row['status']}`",
                 f"Current indexed SHA256: `{row['hash'] or 'not-extracted'}`", "",
                 "Links are observations. An extracted link does not certify the claim.",
                 "Historical hashes do not imply that historical original bytes are retained.", "", "## Observed outgoing links"]
        for edge in outgoing[ident]:
            destination = externals.get(edge["target"], f"./{edge['target']}.md")
            lines.append(f"- `{edge['relation']}` → [{edge['target']}]({destination}), target revision `{edge['target_hash']}`, origin `{edge['origin']}`")
        changed += emit(catalog.home / f"wiki/artifacts/{ident}.md", "\n".join(lines) + "\n")
    index = ["# Corpus navigation", "", "Generated links only; read the source artifacts, not a regenerated summary.", "",
             "Search returns candidates, not automatic approval. Unsupported/truncated input remains visible.", ""]
    for scope, lines in sorted(groups.items()):
        for offset in range(0, len(lines), 200):
            page = f"{scope}-{offset // 200 + 1}.md"
            changed += emit(catalog.home / "wiki" / page, f"# {scope}\n\n" + "\n".join(lines[offset:offset + 200]) + "\n")
            index.append(f"- [{scope}, {offset + 1}–{min(offset + 200, len(lines))}]({page})")
    changed += emit(catalog.home / "wiki/index.md", "\n".join(index) + "\n")
    manifest = catalog.home / "graphify-out/manifest.json"
    changed += _write(manifest, json.dumps({"version": PROJECTION_VERSION, "outputs": outputs}, sort_keys=True, indent=1), catalog.home)
    return {"graph": str(graph_path), "wiki": str(catalog.home / "wiki/index.md"),
            "nodes": len(nodes), "edges": len(links), "changed_files": changed,
            "manifest": str(manifest), "manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
            "coverage": json.loads(coverage[0]) if coverage else {"complete": False}}


def valid_export(catalog, result):
    try:
        manifest = checked_output(result["manifest"], catalog.home)
        if not manifest.is_file() or manifest.stat().st_size > 16 * 1024 * 1024:
            return False
        body = manifest.read_bytes()
        if sha256(body).hexdigest() != result["manifest_sha256"]:
            return False
        record = json.loads(body)
        if record["version"] != PROJECTION_VERSION:
            return False
        from .catalog import digest_file
        return all((path := checked_output(catalog.home / relative, catalog.home)).is_file() and digest_file(path) == digest
                   for relative, digest in record["outputs"].items())
    except (KeyError, OSError, ValueError, TypeError):
        return False


def graph_query(catalog, question, budget=1500):
    from graphify.serve import _query_graph_text, _read_graph
    graph_path = catalog.home / "graphify-out/graph.json"
    if not graph_path.is_file():
        return {"engine": "graphifyy-0.9.95", "status": "not_built", "text": "Export the catalog graph first."}
    graph = _read_graph(str(graph_path))
    text = _query_graph_text(graph, question, depth=2, token_budget=max(100, min(int(budget), 3000)))
    limited = len(text) > 10000
    return {"engine": "graphifyy-0.9.95", "status": "ok", "text": text[:10000],
            "wrapper_truncated": limited, "graph": str(graph_path),
            "note": "narrow the query or use trace if truncated" if limited else ""}
