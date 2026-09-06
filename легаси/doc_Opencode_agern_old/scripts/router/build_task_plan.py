#!/usr/bin/env python3
"""Build grouped execution plan: task -> claims -> routed claim groups."""

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
    grouped = {}

    for claim in claims:
        route_plan = resolve(claim["text"])
        entry = {
            "claim_id": claim["claim_id"],
            "text": claim["text"],
            "kind": claim["kind"],
            "bucket": claim["bucket"],
            "priority": claim["priority"],
            "route_plan": route_plan,
        }
        grouped.setdefault(claim["bucket"], []).append(entry)

    summary = {
        bucket: {
            "claim_count": len(items),
            "route_ids": sorted(list({i["route_plan"].get("route_id", "unknown") for i in items if i["route_plan"].get("ok")})),
            "profiles": sorted(list({i["route_plan"].get("profile", "unknown") for i in items if i["route_plan"].get("ok")})),
        }
        for bucket, items in grouped.items()
    }

    return {
        "ok": True,
        "task_text": task_text,
        "claim_count": len(claims),
        "grouped_buckets": grouped,
        "summary": summary,
        "reason_codes": ["CLAIM_PARSED", "BUCKET_ASSIGNED"],
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: build_task_plan.py <task_text>")
        return 2
    print(json.dumps(build_task_plan(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
