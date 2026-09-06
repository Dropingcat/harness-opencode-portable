#!/usr/bin/env python3
"""Resolve MCP families and servers for a route."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def load(name: str) -> dict:
    return json.loads((root() / "config" / name).read_text(encoding="utf-8"))


def resolve(route_id: str) -> dict:
    registry = load("mcp_registry.json")["servers"]
    policy = load("mcp_capsule_policy.json")
    priorities = policy.get("family_priority", {}).get(route_id, [])
    resolved = []
    for family_id in priorities:
        servers = [s for s in registry.values() if s.get("family") == family_id]
        if not servers:
            continue
        resolved.append({"family": family_id, "servers": servers})
    return {"ok": bool(resolved), "route_id": route_id, "families": resolved}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: resolve_mcp_capsule.py [route_id]")
        return 2
    print(json.dumps(resolve(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())