#!/usr/bin/env python3
"""Build deterministic skill routing graph from module configs."""

import json
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def add_node(nodes: dict, node_id: str, node_type: str, **attrs):
    nodes[node_id] = {"id": node_id, "type": node_type, **attrs}


def add_edge(edges: list, src: str, rel: str, dst: str, **attrs):
    edges.append({"src": src, "rel": rel, "dst": dst, **attrs})


def build() -> dict:
    root = repo_root()
    cfg = root / "config"
    routes = read_json(cfg / "profile_routes.json")["routes"]
    buckets = read_json(cfg / "bucket_contracts.json")["buckets"]
    capsules = read_json(cfg / "skill_capsule_policy.json")["capsules"]
    route_map = read_json(cfg / "skill_to_route_map.json")["routes"]
    profiles = read_json(cfg / "strictness_profiles.json")["profiles"]
    skills_reg = read_json(cfg / "skills_registry.json")
    runtime_bindings = read_json(cfg / "tool_runtime_bindings.json")["tools"]

    nodes = {}
    edges = []

    for pid, pdata in profiles.items():
        add_node(nodes, f"profile:{pid}", "profile", name=pid, guard_mode=pdata.get("guard_mode"))

    for bid, bdata in buckets.items():
        add_node(nodes, f"bucket:{bid}", "bucket", name=bid, guard_required=bdata.get("guard_required", False))
        if bdata.get("default_profile"):
            add_edge(edges, f"bucket:{bid}", "DEFAULT_PROFILE", f"profile:{bdata['default_profile']}")

    skill_classes = {}
    for cls_key in ["core_runtime_skills", "optional_domain_skills", "reference_only_skills"]:
        for skill in skills_reg.get(cls_key, []):
            runtime_class = cls_key.replace("_skills", "")
            skill_classes[skill] = runtime_class

    for cid, cdata in capsules.items():
        add_node(nodes, f"capsule:{cid}", "capsule", name=cid, runtime_class=cdata.get("runtime_class"), advertise_by_default=cdata.get("advertise_by_default", False))
        if cdata.get("guard_profile"):
            add_edge(edges, f"capsule:{cid}", "DEFAULT_PROFILE", f"profile:{cdata['guard_profile']}")
        if cdata.get("fallback_capsule"):
            add_edge(edges, f"capsule:{cid}", "FALLBACK_TO", f"capsule:{cdata['fallback_capsule']}")
        for skill in cdata.get("provided_skills", []):
            add_node(nodes, f"skill:{skill}", "skill", name=skill, runtime_class=skill_classes.get(skill, "unclassified"))
            add_edge(edges, f"capsule:{cid}", "PROVIDES_SKILL", f"skill:{skill}")
            add_edge(edges, f"skill:{skill}", "CLASSIFIED_AS", f"class:{skill_classes.get(skill, 'unclassified')}")
        for tool in cdata.get("related_tools", []):
            binding = runtime_bindings.get(tool, {})
            add_node(nodes, f"tool:{tool}", "tool", name=tool, kind=binding.get("kind"), entrypoint=binding.get("entrypoint"))
            add_edge(edges, f"capsule:{cid}", "USES_TOOL", f"tool:{tool}")
            if binding.get("provider"):
                runtime_id = f"runtime:{binding['provider']}"
                add_node(nodes, runtime_id, "runtime", provider=binding["provider"], kind=binding.get("kind"), entrypoint=binding.get("entrypoint"))
                add_edge(edges, f"tool:{tool}", "BINDS_RUNTIME", runtime_id)

    for rid, rdata in routes.items():
        add_node(nodes, f"route:{rid}", "route", name=rid, match_regex=rdata.get("match_regex"))
        add_edge(edges, f"route:{rid}", "ROUTES_TO", f"bucket:{rdata['bucket']}")
        add_edge(edges, f"route:{rid}", "DEFAULT_PROFILE", f"profile:{rdata['default_profile']}")
        route_meta = route_map.get(rid, {})
        for cap in route_meta.get("capsules", []):
            add_edge(edges, f"route:{rid}", "USES_CAPSULE", f"capsule:{cap}")
        for skill in route_meta.get("skills", []):
            add_node(nodes, f"skill:{skill}", "skill", name=skill, runtime_class=skill_classes.get(skill, "unclassified"))
            add_edge(edges, f"route:{rid}", "REQUIRES_SKILL", f"skill:{skill}")

    for tool, binding in runtime_bindings.items():
        add_node(nodes, f"tool:{tool}", "tool", name=tool, kind=binding.get("kind"), entrypoint=binding.get("entrypoint"))
        runtime_id = f"runtime:{binding['provider']}"
        add_node(nodes, runtime_id, "runtime", provider=binding.get("provider"), kind=binding.get("kind"), entrypoint=binding.get("entrypoint"))
        add_edge(edges, f"tool:{tool}", "BINDS_RUNTIME", runtime_id)
        for step in route_meta.get("start_with", []):
            sid = f"step:start:{rid}:{len(step)}:{abs(hash(step)) % 100000}"
            add_node(nodes, sid, "step", stage="start", text=step)
            add_edge(edges, f"route:{rid}", "STARTS_WITH", sid)
        for step in route_meta.get("finish_with", []):
            sid = f"step:finish:{rid}:{len(step)}:{abs(hash(step)) % 100000}"
            add_node(nodes, sid, "step", stage="finish", text=step)
            add_edge(edges, f"route:{rid}", "FINISHES_WITH", sid)

    return {
        "version": 1,
        "nodes": list(nodes.values()),
        "edges": edges,
        "indexes": {
            "routes": sorted([k for k in nodes if k.startswith("route:")]),
            "capsules": sorted([k for k in nodes if k.startswith("capsule:")]),
            "skills": sorted([k for k in nodes if k.startswith("skill:")]),
            "tools": sorted([k for k in nodes if k.startswith("tool:")]),
        },
    }


def main() -> int:
    root = repo_root()
    graph = build()
    out = root / "config" / "skills_graph.json"
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out), "nodes": len(graph["nodes"]), "edges": len(graph["edges"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
