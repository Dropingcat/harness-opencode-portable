#!/usr/bin/env python3
"""Compatibility entrypoint: rebuild all generated runtime artifacts, including skills_graph.json."""
import json
from compile_runtime import compile_runtime, repo_root


def build() -> dict:
    return compile_runtime(repo_root(), write=False)["graph"]


def main() -> int:
    result = compile_runtime(repo_root(), write=True)
    graph = result["graph"]
    out = repo_root() / "config" / "skills_graph.json"
    print(json.dumps({"ok": True, "path": str(out), "policy_hash": result["snapshot"]["policy_hash"], "nodes": len(graph["nodes"]), "edges": len(graph["edges"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
