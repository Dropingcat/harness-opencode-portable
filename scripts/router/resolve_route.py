#!/usr/bin/env python3
"""Deterministic router resolver backed exclusively by compiled runtime_snapshot.json."""
import argparse
import json
import re
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_snapshot() -> dict:
    path = repo_root() / "config" / "runtime_snapshot.json"
    if not path.exists():
        raise RuntimeError("runtime_snapshot.json missing; run scripts/router/compile_runtime.py")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("generated") or not data.get("policy_hash"):
        raise RuntimeError("runtime_snapshot.json is not a valid compiled snapshot")
    return data


def match_routes(task_text: str, routes: dict) -> list[tuple[str, dict, int]]:
    hits = []
    for route_id, meta in routes.items():
        m = re.search(meta["match_regex"], task_text, flags=re.IGNORECASE)
        if m:
            hits.append((route_id, meta, len(m.group(0))))
    return hits


def _profile_rank(profile: str) -> int:
    return {"soft": 1, "standard": 2, "strict": 3}.get(profile, 0)


def _rank_hits(hits: list[tuple[str, dict, int]], hints: dict) -> list[tuple[str, dict, int]]:
    bucket_hint = hints.get("bucket") or hints.get("expected_bucket")
    if bucket_hint:
        compatible = [h for h in hits if h[1].get("bucket") == bucket_hint]
        if compatible:
            hits = compatible
    return sorted(
        hits,
        key=lambda h: (
            -int(h[1].get("priority", 0)),
            -_profile_rank(hints.get("preferred_profile") or h[1].get("default_profile", "")),
            -h[2],
            h[0],
        ),
    )


def resolve(task_text: str, hints: dict | None = None) -> dict:
    hints = hints or {}
    snap = load_snapshot()
    routes_cfg = snap["routes"]
    capsules_cfg = snap["capsules"]
    buckets_cfg = snap["buckets"]
    profiles_cfg = snap["profiles"]
    exec_modes = snap["execution_modes"]
    runtime_bindings = snap["runtime_bindings"]
    policy = snap["route_resolution"]
    guard_policy = snap["guard_policy"]

    explicit_route = hints.get("route_id")
    if explicit_route:
        if explicit_route not in routes_cfg:
            return {"ok": False, "state": "ESCALATED", "reason_codes": ["REQUIRES_USER_OR_OPERATOR"], "error": "unknown_explicit_route", "route_id": explicit_route, "policy_hash": snap["policy_hash"]}
        hits = [(explicit_route, routes_cfg[explicit_route], len(task_text))]
    else:
        hits = match_routes(task_text, routes_cfg)

    if not hits:
        return {"ok": False, "state": "ESCALATED", "reason_codes": ["REQUIRES_USER_OR_OPERATOR"], "error": "no_route_match", "policy_hash": snap["policy_hash"]}

    ranked = _rank_hits(hits, hints)
    if len(ranked) > 1 and not policy.get("allow_multi_match", True):
        return {"ok": False, "state": "ESCALATED", "reason_codes": ["REQUIRES_USER_OR_OPERATOR"], "error": "ambiguous_multi_route", "candidates": [h[0] for h in ranked], "policy_hash": snap["policy_hash"]}

    route_id, route_meta, _ = ranked[0]
    profile = hints.get("preferred_profile") or route_meta["default_profile"]
    if profile not in profiles_cfg:
        return {"ok": False, "state": "ESCALATED", "reason_codes": ["REQUIRES_USER_OR_OPERATOR"], "error": "unknown_profile", "profile": profile, "policy_hash": snap["policy_hash"]}

    bucket = route_meta["bucket"]
    bucket_meta = buckets_cfg[bucket]
    capsules = list(dict.fromkeys(route_meta.get("capsules", [])))
    skills = []
    tools = []
    for cap_id in capsules:
        cap = capsules_cfg.get(cap_id, {})
        skills.extend(cap.get("provided_skills", []))
        tools.extend(cap.get("related_tools", []))
    skills.extend(route_meta.get("skills", []))
    tools.extend(route_meta.get("preferred_tools", []))
    tools.extend(bucket_meta.get("tools", []))
    skills = list(dict.fromkeys(skills))
    tools = list(dict.fromkeys(tools))

    preferred_mode = profiles_cfg[profile]["preferred_execution_mode"]
    bucket_mode = bucket_meta.get("default_execution_mode")
    mode = preferred_mode
    if bucket_mode in exec_modes and profile in exec_modes[bucket_mode].get("use_when_profiles", []):
        mode = bucket_mode
    if mode not in exec_modes or profile not in exec_modes[mode].get("use_when_profiles", []):
        return {"ok": False, "state": "ESCALATED", "reason_codes": ["REQUIRES_USER_OR_OPERATOR"], "error": "no_compatible_execution_mode", "profile": profile, "bucket": bucket, "policy_hash": snap["policy_hash"]}

    untrusted = set(guard_policy.get("untrusted_tools", []))
    untrusted_selected = sorted(set(tools) & untrusted)
    guard_required = bool(route_meta.get("guard_required", False) or bucket_meta.get("guard_required", False) or untrusted_selected)
    tool_bindings = {tool: runtime_bindings[tool] for tool in tools if tool in runtime_bindings}

    max_candidates = int(policy.get("max_routes_returned", 3))
    candidates = [
        {"route_id": rid, "bucket": meta.get("bucket"), "profile": meta.get("default_profile"), "priority": meta.get("priority", 0), "match_length": ml}
        for rid, meta, ml in ranked[:max_candidates]
    ]

    return {
        "ok": True,
        "route_id": route_id,
        "bucket": bucket,
        "profile": profile,
        "execution_mode": mode,
        "capsules": capsules,
        "skills": skills,
        "tools": tools,
        "guard_required": guard_required,
        "guard_untrusted_tools": untrusted_selected,
        "start_with": route_meta.get("start_with", []),
        "finish_with": route_meta.get("finish_with", []),
        "reason_codes": ["BUCKET_ASSIGNED"],
        "snapshot_backed": True,
        "policy_hash": snap["policy_hash"],
        "tool_bindings": tool_bindings,
        "candidates": candidates,
        "resolution_strategy": policy.get("multi_match_strategy"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve task text from compiled runtime policy")
    parser.add_argument("task_text")
    parser.add_argument("--route-id")
    parser.add_argument("--bucket")
    parser.add_argument("--profile", dest="preferred_profile", choices=["soft", "standard", "strict"])
    args = parser.parse_args()
    hints = {k: v for k, v in vars(args).items() if k != "task_text" and v is not None}
    print(json.dumps(resolve(args.task_text, hints), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
