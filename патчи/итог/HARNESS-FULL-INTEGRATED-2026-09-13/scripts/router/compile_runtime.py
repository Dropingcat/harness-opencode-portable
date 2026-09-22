#!/usr/bin/env python3
"""Compile authoritative orchestration policy into deterministic runtime artifacts.

Authoritative inputs are declared in config/runtime_source_manifest.json.
Generated outputs must not be hand-edited. Validation is fail-closed: a broken
cross-reference prevents snapshot generation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def _fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def load_sources(root: Path | None = None) -> tuple[dict, dict[str, dict]]:
    root = root or repo_root()
    manifest = read_json(root / "config" / "runtime_source_manifest.json")
    sources: dict[str, dict] = {}
    for name, rel in manifest["authority"].items():
        path = root / rel
        if not path.exists():
            raise FileNotFoundError(f"authoritative source missing: {name} -> {rel}")
        sources[name] = read_json(path)
    return manifest, sources


def validate_sources(s: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    routes = s["routes"].get("routes", {})
    contracts = s["tool_contracts"].get("contracts", {})
    buckets = s["buckets"].get("buckets", {})
    capsules = s["capsules"].get("capsules", {})
    profiles = s["profiles"].get("profiles", {})
    modes = s["execution_modes"].get("modes", {})
    bindings = s["runtime_bindings"].get("tools", {})
    skills_reg = s["skills_registry"]

    known_skills = set()
    for key in ("core_runtime_skills", "optional_domain_skills", "reference_only_skills"):
        known_skills.update(skills_reg.get(key, []))
    # Capsule-provided skills are valid even before registry normalization is complete.
    for c in capsules.values():
        known_skills.update(c.get("provided_skills", []))

    if not routes:
        _fail(errors, "routes_authority has no routes")

    for rid, r in routes.items():
        for req in ("match_regex", "bucket", "default_profile"):
            if not r.get(req):
                _fail(errors, f"route {rid}: missing {req}")
        try:
            re.compile(r.get("match_regex", ""), re.IGNORECASE)
        except re.error as e:
            _fail(errors, f"route {rid}: invalid match_regex: {e}")
        if r.get("bucket") not in buckets:
            _fail(errors, f"route {rid}: unknown bucket {r.get('bucket')!r}")
        if r.get("default_profile") not in profiles:
            _fail(errors, f"route {rid}: unknown profile {r.get('default_profile')!r}")
        for cap in r.get("capsules", []):
            if cap not in capsules:
                _fail(errors, f"route {rid}: unknown capsule {cap!r}")
            elif rid not in capsules[cap].get("supported_routes", []):
                _fail(errors, f"route {rid}: capsule {cap!r} does not declare route support")
        for tool in r.get("preferred_tools", []):
            if tool not in bindings:
                _fail(errors, f"route {rid}: preferred tool {tool!r} has no runtime binding")
            if tool not in contracts:
                _fail(errors, f"route {rid}: preferred tool {tool!r} has no tool contract")
        for skill in r.get("skills", []):
            if skill not in known_skills:
                _fail(errors, f"route {rid}: unknown/unregistered skill {skill!r}")

    for cid, c in capsules.items():
        fb = c.get("fallback_capsule")
        if fb and fb not in capsules:
            _fail(errors, f"capsule {cid}: unknown fallback {fb!r}")
        gp = c.get("guard_profile")
        if gp and gp not in profiles:
            _fail(errors, f"capsule {cid}: unknown guard_profile {gp!r}")
        for rid in c.get("supported_routes", []):
            if rid not in routes:
                _fail(errors, f"capsule {cid}: supports unknown route {rid!r}")
        for tool in c.get("related_tools", []):
            if tool not in bindings:
                _fail(errors, f"capsule {cid}: related tool {tool!r} has no runtime binding")

    for bid, b in buckets.items():
        p = b.get("default_profile")
        if p and p not in profiles:
            _fail(errors, f"bucket {bid}: unknown default_profile {p!r}")
        mode = b.get("default_execution_mode")
        if mode and mode not in modes:
            _fail(errors, f"bucket {bid}: unknown default_execution_mode {mode!r}")
        for tool in b.get("tools", []):
            if tool not in bindings:
                _fail(errors, f"bucket {bid}: tool {tool!r} has no runtime binding")

    for mid, m in modes.items():
        for p in m.get("use_when_profiles", []):
            if p not in profiles:
                _fail(errors, f"execution mode {mid}: unknown compatible profile {p!r}")

    for tool, c in contracts.items():
        if tool not in bindings:
            _fail(errors, f"tool contract {tool}: no runtime binding")
        for req in ("required_input", "optional_input", "skills_before_use"):
            if not isinstance(c.get(req, []), list):
                _fail(errors, f"tool contract {tool}: {req} must be a list")

    return sorted(set(errors))


def _skill_classes(registry: dict) -> dict[str, str]:
    out = {}
    for key in ("core_runtime_skills", "optional_domain_skills", "reference_only_skills"):
        cls = key.replace("_skills", "")
        for skill in registry.get(key, []):
            out[skill] = cls
    return out


def build_graph(snapshot: dict) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(node_id: str, typ: str, **attrs: Any) -> None:
        nodes[node_id] = {"id": node_id, "type": typ, **attrs}

    def edge(src: str, rel: str, dst: str, **attrs: Any) -> None:
        edges.append({"src": src, "rel": rel, "dst": dst, **attrs})

    skill_classes = snapshot["indexes"].get("skill_classes", {})
    for pid, p in snapshot["profiles"].items():
        node(f"profile:{pid}", "profile", name=pid, guard_mode=p.get("guard_mode"))
    for bid, b in snapshot["buckets"].items():
        node(f"bucket:{bid}", "bucket", name=bid, guard_required=b.get("guard_required", False))
        if b.get("default_profile"):
            edge(f"bucket:{bid}", "DEFAULT_PROFILE", f"profile:{b['default_profile']}")
    for cid, c in snapshot["capsules"].items():
        node(f"capsule:{cid}", "capsule", name=cid, runtime_class=c.get("runtime_class"), advertise_by_default=c.get("advertise_by_default", False))
        if c.get("guard_profile"):
            edge(f"capsule:{cid}", "DEFAULT_PROFILE", f"profile:{c['guard_profile']}")
        if c.get("fallback_capsule"):
            edge(f"capsule:{cid}", "FALLBACK_TO", f"capsule:{c['fallback_capsule']}")
        for skill in c.get("provided_skills", []):
            node(f"skill:{skill}", "skill", name=skill, runtime_class=skill_classes.get(skill, "unclassified"))
            edge(f"capsule:{cid}", "PROVIDES_SKILL", f"skill:{skill}")
        for tool in c.get("related_tools", []):
            bind = snapshot["runtime_bindings"].get(tool, {})
            node(f"tool:{tool}", "tool", name=tool, kind=bind.get("kind"), entrypoint=bind.get("entrypoint"))
            edge(f"capsule:{cid}", "USES_TOOL", f"tool:{tool}")
    for rid, r in snapshot["routes"].items():
        node(f"route:{rid}", "route", name=rid, match_regex=r["match_regex"], priority=r.get("priority", 0))
        edge(f"route:{rid}", "ROUTES_TO", f"bucket:{r['bucket']}")
        edge(f"route:{rid}", "DEFAULT_PROFILE", f"profile:{r['default_profile']}")
        for cap in r.get("capsules", []): edge(f"route:{rid}", "USES_CAPSULE", f"capsule:{cap}")
        for skill in r.get("skills", []):
            node(f"skill:{skill}", "skill", name=skill, runtime_class=skill_classes.get(skill, "unclassified"))
            edge(f"route:{rid}", "REQUIRES_SKILL", f"skill:{skill}")
        for stage in ("start", "finish"):
            for text in r.get(f"{stage}_with", []):
                digest = hashlib.sha256(f"{stage}\0{rid}\0{text}".encode()).hexdigest()[:12]
                sid = f"step:{stage}:{rid}:{digest}"
                node(sid, "step", stage=stage, text=text)
                edge(f"route:{rid}", "STARTS_WITH" if stage == "start" else "FINISHES_WITH", sid)
    for tool, bind in snapshot["runtime_bindings"].items():
        node(f"tool:{tool}", "tool", name=tool, kind=bind.get("kind"), entrypoint=bind.get("entrypoint"))
        if bind.get("provider"):
            runid = f"runtime:{bind['provider']}"
            node(runid, "runtime", provider=bind["provider"], kind=bind.get("kind"), entrypoint=bind.get("entrypoint"))
            edge(f"tool:{tool}", "BINDS_RUNTIME", runid)
    edge_key = lambda e: (e.get("src", ""), e.get("rel", ""), e.get("dst", ""), json.dumps(e, sort_keys=True, ensure_ascii=False))
    return {
        "version": 3,
        "generated_from_policy_hash": snapshot["policy_hash"],
        "generated": True,
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": sorted(edges, key=edge_key),
        "indexes": {
            "routes": sorted(k for k in nodes if k.startswith("route:")),
            "capsules": sorted(k for k in nodes if k.startswith("capsule:")),
            "skills": sorted(k for k in nodes if k.startswith("skill:")),
            "tools": sorted(k for k in nodes if k.startswith("tool:")),
        },
    }


def build_snapshot(s: dict[str, dict]) -> dict:
    route_authority = s["routes"]["routes"]
    tool_contracts = s["tool_contracts"]["contracts"]
    skill_classes = _skill_classes(s["skills_registry"])
    source_hashes = {name: sha256_obj(value) for name, value in sorted(s.items())}
    policy_hash = sha256_obj({name: s[name] for name in sorted(s)})
    routes = {}
    for rid, r in sorted(route_authority.items()):
        routes[rid] = {**r}
        routes[rid]["guard_required"] = bool(r.get("guard_required") if r.get("guard_required") is not None else s["buckets"]["buckets"][r["bucket"]].get("guard_required", False))
    return {
        "version": 1,
        "generated": True,
        "do_not_edit": "Generated by scripts/router/compile_runtime.py from config/runtime_source_manifest.json",
        "policy_hash": policy_hash,
        "source_hashes": source_hashes,
        "routes": routes,
        "tool_contracts": tool_contracts,
        "buckets": s["buckets"]["buckets"],
        "capsules": s["capsules"]["capsules"],
        "profiles": s["profiles"]["profiles"],
        "execution_modes": s["execution_modes"]["modes"],
        "runtime_bindings": s["runtime_bindings"]["tools"],
        "route_resolution": s["route_resolution"]["resolution"],
        "guard_policy": s["guard_policy"],
        "tool_capsule_policy": s["tool_capsule_policy"],
        "indexes": {
            "route_ids": sorted(routes),
            "tool_ids": sorted(s["runtime_bindings"]["tools"]),
            "capsule_ids": sorted(s["capsules"]["capsules"]),
            "profile_ids": sorted(s["profiles"]["profiles"]),
            "execution_mode_ids": sorted(s["execution_modes"]["modes"]),
            "skill_classes": skill_classes,
        },
    }


def compatibility_artifacts(snapshot: dict) -> dict[str, dict]:
    routes = snapshot["routes"]
    profile_routes = {
        "version": 2, "generated": True, "generated_from_policy_hash": snapshot["policy_hash"],
        "routes": {rid: {k: r[k] for k in ("match_regex", "bucket", "default_profile", "priority") if k in r} for rid, r in routes.items()}
    }
    context_routes = []
    for rid, r in routes.items():
        item = {
            "id": rid,
            "when_regex": r["match_regex"],
            "skills": r.get("skills", []),
            "preferred_tools": r.get("preferred_tools", []),
            "guard_required": r.get("guard_required", False),
            "agent_hint": r.get("agent_hint", ""),
        }
        if r.get("triz_required"): item["triz_required"] = True
        context_routes.append(item)
    tool_skill = {
        "version": 2, "generated": True, "generated_from_policy_hash": snapshot["policy_hash"],
        "invariant": "GENERATED COMPATIBILITY VIEW. Edit routes_authority.json / tool_contracts_authority.json instead.",
        "context_routes": context_routes,
        "tool_contracts": snapshot["tool_contracts"],
    }
    skill_map = {
        "version": 2, "generated": True, "generated_from_policy_hash": snapshot["policy_hash"],
        "routes": {rid: {k: r.get(k, []) for k in ("capsules", "skills", "start_with", "finish_with")} for rid, r in routes.items()}
    }
    return {"profile_routes_compat": profile_routes, "tool_skill_routes_compat": tool_skill, "skill_to_route_map_compat": skill_map}


def compile_runtime(root: Path | None = None, write: bool = True) -> dict:
    root = root or repo_root()
    manifest, sources = load_sources(root)
    errors = validate_sources(sources)
    if errors:
        raise ValueError("runtime policy validation failed:\n- " + "\n- ".join(errors))
    snapshot = build_snapshot(sources)
    graph = build_graph(snapshot)
    compat = compatibility_artifacts(snapshot)
    if write:
        generated = manifest["generated"]
        payloads = {"runtime_snapshot": snapshot, "skills_graph": graph, **compat}
        for key, obj in payloads.items():
            path = root / generated[key]
            path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"snapshot": snapshot, "graph": graph, "compat": compat, "errors": []}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate and verify generated artifacts are current without rewriting")
    args = ap.parse_args()
    root = repo_root()
    try:
        result = compile_runtime(root, write=not args.check)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
        return 2
    if args.check:
        manifest = read_json(root / "config" / "runtime_source_manifest.json")
        expected = {"runtime_snapshot": result["snapshot"], "skills_graph": result["graph"], **result["compat"]}
        stale = []
        for key, obj in expected.items():
            p = root / manifest["generated"][key]
            if not p.exists() or read_json(p) != obj:
                stale.append(manifest["generated"][key])
        if stale:
            print(json.dumps({"ok": False, "error": "generated_artifacts_stale", "stale": stale, "policy_hash": result["snapshot"]["policy_hash"]}, ensure_ascii=False, indent=2))
            return 3
    print(json.dumps({"ok": True, "policy_hash": result["snapshot"]["policy_hash"], "routes": len(result["snapshot"]["routes"]), "tools": len(result["snapshot"]["tool_contracts"]), "mode": "check" if args.check else "write"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
