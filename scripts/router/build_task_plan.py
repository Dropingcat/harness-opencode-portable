#!/usr/bin/env python3
"""Build grouped execution plan: task -> claims -> routed claim groups."""

import argparse
import json
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _add_repo_to_path() -> None:
    root = repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_add_repo_to_path()
from scripts.router.split_claims import split_claims  # type: ignore
from scripts.router.resolve_route import resolve  # type: ignore


def build_task_plan(task_text: str) -> dict:
    split = split_claims(task_text)
    claims = split["claims"]
    grouped: dict[str, list[dict]] = {}
    conflicts = []

    for claim in claims:
        route_plan = resolve(claim["text"], {"expected_bucket": claim["bucket"]})
        effective_bucket = route_plan.get("bucket") if route_plan.get("ok") else claim["bucket"]
        if route_plan.get("ok") and effective_bucket != claim["bucket"]:
            conflicts.append({"claim_id": claim["claim_id"], "claim_bucket": claim["bucket"], "route_bucket": effective_bucket})
        entry = {
            "claim_id": claim["claim_id"], "text": claim["text"], "kind": claim["kind"],
            "matched_kinds": claim.get("matched_kinds", []), "bucket": effective_bucket,
            "claim_bucket": claim["bucket"], "priority": claim["priority"], "route_plan": route_plan,
        }
        grouped.setdefault(effective_bucket, []).append(entry)

    summary = {
        bucket: {
            "claim_count": len(items),
            "route_ids": sorted({i["route_plan"].get("route_id", "unknown") for i in items if i["route_plan"].get("ok")}),
            "profiles": sorted({i["route_plan"].get("profile", "unknown") for i in items if i["route_plan"].get("ok")}),
        }
        for bucket, items in grouped.items()
    }
    unresolved = [i["claim_id"] for items in grouped.values() for i in items if not i["route_plan"].get("ok")]
    return {
        "ok": not conflicts and not unresolved,
        "state": "READY" if not conflicts and not unresolved else "ESCALATED",
        "task_text": task_text,
        "claim_count": len(claims),
        "grouped_buckets": grouped,
        "summary": summary,
        "routing_conflicts": conflicts,
        "unresolved_claims": unresolved,
        "reason_codes": ["CLAIM_PARSED", "BUCKET_ASSIGNED"] + (["REQUIRES_USER_OR_OPERATOR"] if conflicts or unresolved else []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic claim-aware task plan")
    parser.add_argument("task_text")
    args = parser.parse_args()
    print(json.dumps(build_task_plan(args.task_text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
