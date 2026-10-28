"""Full approved-scope evidence: immutable extraction, no-op pass and navigation."""
import json
import time
from pathlib import Path

from knowledge_pilot.runtime import HOME, catalog, configure


def verify():
    configure()
    from knowledge_pilot.paths import write_text
    from knowledge_pilot.projection import export_catalog, graph_query, valid_export
    from knowledge_pilot.extract import safe_data
    store = catalog()
    started = time.monotonic()
    clean = store.refresh()
    first = store.scan()
    assert first.get("scan_completed"), first
    assert not first["missing_roots"] and not first["errors"], first
    with store.db() as db:
        before = [tuple(row) for row in db.execute("SELECT id,hash,size,mtime_ns,status FROM files WHERE root!='pilot-results' ORDER BY id")]
    second = store.scan()
    with store.db() as db:
        after = [tuple(row) for row in db.execute("SELECT id,hash,size,mtime_ns,status FROM files WHERE root!='pilot-results' ORDER BY id")]
        scopes = [dict(row) for row in db.execute("SELECT root,status,COUNT(*) AS files FROM files GROUP BY root,status ORDER BY root,status")]
        links = dict(db.execute("SELECT relation,COUNT(*) FROM edges GROUP BY relation").fetchall())
        result = db.execute("SELECT path FROM files WHERE root='pilot-results' AND status IN ('extracted','partial') ORDER BY path LIMIT 1").fetchone()
        issues = [dict(row) for row in db.execute("SELECT path,status,detail FROM files WHERE status IN ('failed','needs_ocr','oversized') ORDER BY path LIMIT 15")]
    assert second.get("scan_completed") and second["parsed"] == 0, second
    assert first["files"] == second["files"] and before == after, "corpus changed between no-op verification passes"
    graph = export_catalog(store)
    assert "graph" in graph and valid_export(store, graph), graph
    repeated_graph = export_catalog(store)
    assert repeated_graph["changed_files"] == 0, repeated_graph
    lookup = store.lookup("nitrogen diffusion", limit=3)
    assert lookup["candidates"], "real corpus lookup returned no candidates"
    query = graph_query(store, "data.csv", budget=700)
    assert query["status"] == "ok" and query["text"], query
    trace = store.trace(result["path"]) if result else {"found": False}
    assert trace.get("found") and any(edge["relation"] == "derived_from" for edge in trace["edges"]), trace
    evidence = {"verification": "PASS", "elapsed_seconds": round(time.monotonic() - started, 2),
        "cache_migration": clean, "first_scan": first, "second_scan": second,
        "indexed_source_records_unchanged_between_passes": before == after,
        "no_repeated_extraction": second["parsed"] == 0,
        "coverage_by_scope": scopes, "link_relations": links,
        "navigation": graph, "second_projection_changed_files": repeated_graph["changed_files"],
        "lookup": {"action": lookup["action"], "candidates": lookup["candidates"]},
        "native_graphify_query": query, "registered_worker_output_trace": trace,
        "unresolved_input_examples": issues,
        "limitations": ["Unsupported/truncated/failed/OCR-needed inputs remain explicit; PASS is a pipeline check, not full-text completeness.",
            "Historical report approval is never inferred; local generated profiles are drafts.",
            "No live Flowsint service or website_to_text execution. Downloader remains separate.",
            "No inspection/import of the live OpenCode database on C:; only session exports already in approved roots."]}
    write_text(HOME / "artifacts/full_corpus_check.json", json.dumps(safe_data(evidence), ensure_ascii=False, indent=2), HOME)
    print(json.dumps({"verification": "PASS", "files": first["files"], "second_parsed": second["parsed"],
        "graph_nodes": graph["nodes"], "graph_edges": graph["edges"], "coverage_complete": second["complete"],
        "evidence": str(HOME / "artifacts/full_corpus_check.json")}, ensure_ascii=False))
    return evidence


if __name__ == "__main__":
    verify()
