#!/usr/bin/env python3
"""domain_map.py — Волна 6, многослойная карта + TMS-веса (вопросы 6/7).

Карта накапливается между прогонами:
  domain_map/
    layers/run_YYYYMMDD_seed_<id>.json   — слой прогона (рёбра: узел→группа)
    overlay.json                          — {edge: {weight, sources, last_seen}}
    index.json                            — список слоёв

Вес ребра = число независимых подтверждений (credibility по 37 §1.2),
НЕ достоверность (weight≠truth).
Конфликт слоёв (SUPPORTED в одном, CONTRADICTED в другом) = nogood
(исключается, не решается) — миктотеории Cyc.

Usage: python3 domain_map.py <verdicts.json> <topics_tree.json> <domain_map_dir> [--run-id <id>] [--no-write]
"""
import argparse
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime
from pathlib import Path

CONFLICT = "nogood"


def walk_nodes(node, acc):
    acc[node["id"]] = node
    for c in node.get("children", []):
        walk_nodes(c, acc)


def build_layer(verdicts, topics):
    """Слой прогона: рёбра (node_id -> gid) с вердиктами."""
    nodes = {}
    walk_nodes(topics["topics_tree"], nodes)

    # группа -> её узел
    gid2node = {}
    for nid, node in nodes.items():
        for gid in node.get("claims", []):
            gid2node[str(gid)] = nid

    edges = []
    for g in verdicts:
        gid = str(g.get("original_index"))
        nid = gid2node.get(gid)
        if not nid:
            continue
        edges.append({
            "node": nid,
            "gid": gid,
            "verdict": g.get("verdict"),
            "confidence": g.get("confidence"),
            "n_sources": g.get("n_sources", 0),
        })
    return {"edges": edges, "created": datetime.now().isoformat(timespec="seconds")}


def _edge_key(node, gid):
    return f"{node}::{gid}"


def merge_overlay(old_overlay, layer):
    """Накопление веса между прогонами. weight = credibility (число подтверждений)."""
    overlay = json.loads(json.dumps(old_overlay))
    seen = set()
    for e in layer["edges"]:
        key = _edge_key(e["node"], e["gid"])
        seen.add(key)
        rec = overlay.setdefault(key, {"node": e["node"], "gid": e["gid"],
                                       "weight": 0, "sources": 0,
                                       "verdicts": [], "last_seen": layer["created"]})
        rec["verdicts"].append({
            "verdict": e["verdict"], "confidence": e["confidence"],
            "when": layer["created"]})
        rec["sources"] = max(rec["sources"], e.get("n_sources", 0))
        rec["last_seen"] = layer["created"]
        # вес = число подтверждений (SUPPORTED), не достоверность
        rec["weight"] = sum(1 for v in rec["verdicts"] if v["verdict"] == "SUPPORTED")
        rec["runs"] = len(rec["verdicts"])
    # конфликты = nogood: SUPPORTED и CONTRADICTED/UNSUPPORTED на одно ребро
    nogoods = []
    for key, rec in overlay.items():
        verdicts_set = {v["verdict"] for v in rec["verdicts"]}
        if "SUPPORTED" in verdicts_set and verdicts_set & {"CONTRADICTED", "UNSUPPORTED"}:
            rec["status"] = CONFLICT
            nogoods.append(key)
        else:
            rec.setdefault("status", "ok")
    return overlay, nogoods


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("verdicts_json")
    ap.add_argument("topics_tree_json")
    ap.add_argument("domain_map_dir")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--no-write", action="store_true", help="только прочитать/слить, не писать")
    args = ap.parse_args()

    verdicts = json.load(open(args.verdicts_json, encoding="utf-8"))
    if isinstance(verdicts, dict) and "verdicts" in verdicts:
        verdicts = verdicts["verdicts"]
    topics = json.load(open(args.topics_tree_json, encoding="utf-8"))

    layer = build_layer(verdicts, topics)

    dmap = Path(args.domain_map_dir)
    dmap.mkdir(parents=True, exist_ok=True)
    (dmap / "layers").mkdir(exist_ok=True)

    # overlay + index
    overlay_path = dmap / "overlay.json"
    index_path = dmap / "index.json"
    old_overlay = {}
    if overlay_path.is_file():
        try:
            old_overlay = json.load(open(overlay_path, encoding="utf-8"))
        except json.JSONDecodeError:
            old_overlay = {}
    old_index = json.load(open(index_path, encoding="utf-8")) if index_path.is_file() else {"runs": []}

    run_id = args.run_id or datetime.now().strftime("run_%Y%m%d_seed_%H%M%S")
    layer_path = dmap / "layers" / f"{run_id}.json"

    if not args.no_write:
        with open(layer_path, "w", encoding="utf-8") as f:
            json.dump(layer, f, ensure_ascii=False, indent=1)

    overlay, nogoods = merge_overlay(old_overlay, layer)

    if not args.no_write:
        with open(overlay_path, "w", encoding="utf-8") as f:
            json.dump(overlay, f, ensure_ascii=False, indent=1)
        if run_id not in old_index["runs"]:
            old_index["runs"].append(run_id)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(old_index, f, ensure_ascii=False, indent=1)

    n_supported = sum(1 for e in layer["edges"] if e["verdict"] == "SUPPORTED")
    n_edges = len(layer["edges"])
    print(f"✅ domain_map: рёбер {n_edges}, SUPPORTED {n_supported}, "
          f"рёбер в overlay {len(overlay)}, nogood {len(nogoods)}, run {run_id}")
    print(f"   вес = credibility (число подтверждений), не достоверность")


if __name__ == "__main__":
    main()
