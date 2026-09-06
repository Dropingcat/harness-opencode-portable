#!/usr/bin/env python3
"""Deterministic router core resolver for the unified module."""

import json
import re
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cfg(name: str) -> dict:
    return load_json(repo_root() / "config" / name)


def maybe_graph() -> dict | None:
    path = repo_root() / "config" / "skills_graph.json"
    return load_json(path) if path.exists() else None


def outgoing(graph: dict, src: str, rel: str | None = None) -> list[dict]:
    edges = [e for e in graph.get("edges", []) if e["src"] == src]
    if rel is not None:
        edges = [e for e in edges if e["rel"] == rel]
    return edges


def node_lookup(graph: dict) -> dict:
    return {n["id"]: n for n in graph.get("nodes", [])}


def match_routes(task_text: str, routes: dict) -> list[tuple[str, dict]]:
    hits = []
    for route_id, meta in routes.items():
        if re.search(meta["match_regex"], task_text, flags=re.IGNORECASE):
            hits.append((route_id, meta))
    return hits


def resolve(task_text: str, hints: dict | None = None) -> dict:
    hints = hints or {}
    routes_cfg = cfg("profile_routes.json")["routes"]
    route_map = cfg("skill_to_route_map.json")["routes"]
    capsules_cfg = cfg("skill_capsule_policy.json")["capsules"]
    buckets_cfg = cfg("bucket_contracts.json")["buckets"]
    profiles_cfg = cfg("strictness_profiles.json")["profiles"]
    exec_modes = cfg("execution_modes.json")["modes"]
    policy = cfg("route_resolution_policy.json")["resolution"]
    graph = maybe_graph()
    graph_nodes = node_lookup(graph) if graph else {}

    hits = match_routes(task_text, routes_cfg)
    if not hits:
        return {
            "ok": False,
            "state": "ESCALATED",
            "reason_codes": ["REQUIRES_USER_OR_OPERATOR"],
            "error": "no_route_match",
        }

    if len(hits) > 1 and not policy.get("allow_multi_match", True):
        return {
            "ok": False,
            "state": "ESCALATED",
            "reason_codes": ["REQUIRES_USER_OR_OPERATOR"],
            "error": "ambiguous_multi_route",
            "candidates": [h[0] for h in hits],
        }

    route_id, route_meta = hits[0]
    profile = hints.get("preferred_profile") or route_meta["default_profile"]
    bucket = route_meta["bucket"]
    bucket_meta = buckets_cfg[bucket]
    route_contract = route_map.get(route_id, {})
    capsules = route_contract.get("capsules", [])

    skills = []
    tools = []
    if graph:
        route_node = f"route:{route_id}"
        capsules = [e["dst"].split(":", 1)[1] for e in outgoing(graph, route_node, "USES_CAPSULE")]
        for cap_id in capsules:
            cap_node = f"capsule:{cap_id}"
            skills.extend([e["dst"].split(":", 1)[1] for e in outgoing(graph, cap_node, "PROVIDES_SKILL")])
            tools.extend([e["dst"].split(":", 1)[1] for e in outgoing(graph, cap_node, "USES_TOOL")])
        skills.extend([e["dst"].split(":", 1)[1] for e in outgoing(graph, route_node, "REQUIRES_SKILL")])
    else:
        for cap_id in capsules:
            cap = capsules_cfg.get(cap_id, {})
            skills.extend(cap.get("provided_skills", []))
            tools.extend(cap.get("related_tools", []))
        skills.extend(route_contract.get("skills", []))
    tools.extend(bucket_meta.get("tools", []))

    start_with = route_contract.get("start_with", [])
    finish_with = route_contract.get("finish_with", [])
    if graph:
        route_node = f"route:{route_id}"
        graph_start = [graph_nodes[e["dst"]]["text"] for e in outgoing(graph, route_node, "STARTS_WITH") if e["dst"] in graph_nodes]
        graph_finish = [graph_nodes[e["dst"]]["text"] for e in outgoing(graph, route_node, "FINISHES_WITH") if e["dst"] in graph_nodes]
        if graph_start:
            start_with = graph_start
        if graph_finish:
            finish_with = graph_finish

    tool_bindings = {}
    if graph:
        for tool in list(dict.fromkeys(tools)):
            tool_node = f"tool:{tool}"
            binds = outgoing(graph, tool_node, "BINDS_RUNTIME")
            if binds:
                runtime_id = binds[0]["dst"]
                runtime_node = graph_nodes.get(runtime_id, {})
                tool_bindings[tool] = {
                    "kind": runtime_node.get("kind"),
                    "provider": runtime_node.get("provider"),
                    "entrypoint": runtime_node.get("entrypoint"),
                }

    preferred_mode = profiles_cfg[profile]["preferred_execution_mode"]
    mode = bucket_meta.get("default_execution_mode") or preferred_mode
    if mode not in exec_modes:
        mode = preferred_mode

    return {
        "ok": True,
        "route_id": route_id,
        "bucket": bucket,
        "profile": profile,
        "execution_mode": mode,
        "capsules": list(dict.fromkeys(capsules)),
        "skills": list(dict.fromkeys(skills)),
        "tools": list(dict.fromkeys(tools)),
        "guard_required": bucket_meta.get("guard_required", False),
        "start_with": start_with,
        "finish_with": finish_with,
        "reason_codes": ["BUCKET_ASSIGNED"],
        "graph_backed": bool(graph),
        "tool_bindings": tool_bindings,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: resolve_route.py <task_text>")
        return 2
    task_text = sys.argv[1]
    print(json.dumps(resolve(task_text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
