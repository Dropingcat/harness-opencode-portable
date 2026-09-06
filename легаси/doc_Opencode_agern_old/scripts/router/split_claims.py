#!/usr/bin/env python3
"""Deterministic first-pass claim splitter for the unified harness."""

import json
import re
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(name: str) -> dict:
    return json.loads((repo_root() / "config" / name).read_text(encoding="utf-8"))


def split_units(text: str) -> list[str]:
    raw = re.split(r"(?:\r?\n\s*[-*•]\s+|\r?\n\s*\d+[.)]\s+|[.;]\s+|\r?\n+)", text)
    units = [u.strip(" -•\t\r\n") for u in raw if u and u.strip(" -•\t\r\n")]
    return units or [text.strip()]


def detect_kind(text: str, claim_kinds: dict) -> str:
    for kind, meta in claim_kinds.items():
        if re.search(meta["match_regex"], text, flags=re.IGNORECASE):
            return kind
    return "requirement"


def make_claim_id(index: int) -> str:
    return f"CLM_{index:04d}"


def split_claims(task_text: str) -> dict:
    kinds_cfg = load_json("claim_kinds.json")["claim_kinds"]
    buckets_cfg = load_json("claim_bucket_rules.json")
    kind_to_bucket = buckets_cfg["kind_to_bucket"]
    priority_rules = buckets_cfg["priority_rules"]

    claims = []
    grouped = {}
    for i, unit in enumerate(split_units(task_text), start=1):
        kind = detect_kind(unit, kinds_cfg)
        bucket = kind_to_bucket.get(kind, "integration")
        priority = priority_rules.get(kind, priority_rules.get("default", "normal"))
        claim = {
            "claim_id": make_claim_id(i),
            "text": unit,
            "kind": kind,
            "bucket": bucket,
            "priority": priority,
            "dependencies": [],
            "reason_codes": ["CLAIM_PARSED", "BUCKET_ASSIGNED"],
        }
        claims.append(claim)
        grouped.setdefault(bucket, []).append(claim["claim_id"])
    return {"ok": True, "claims": claims, "grouped_buckets": grouped}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: split_claims.py <task_text>")
        return 2
    print(json.dumps(split_claims(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
