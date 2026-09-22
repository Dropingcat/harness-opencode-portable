#!/usr/bin/env python3
"""Resolve active capsules and layers for a route using hierarchy configs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def load(name: str) -> dict:
    return json.loads((root() / "config" / name).read_text(encoding="utf-8"))


def resolve(route_id: str) -> dict:
    registry = load("capsule_registry.json")["capsules"]
    hierarchy = load("capsule_route_hierarchy.json")
    chain = hierarchy.get("route_bindings", {}).get(route_id, [])
    capsules = []
    for cid in chain:
        meta = registry.get(cid)
        if not meta:
            continue
        capsules.append(
            {
                "capsule_id": cid,
                "type": meta.get("type"),
                "status": meta.get("status"),
                "source_of_truth": meta.get("source_of_truth", []),
            }
        )
    return {"ok": bool(capsules), "route_id": route_id, "layers": chain, "capsules": capsules}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: resolve_capsules.py <route_id>")
        return 2
    print(json.dumps(resolve(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
