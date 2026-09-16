#!/usr/bin/env python3
"""Deterministic first-pass claim splitter for the unified harness."""

import argparse
import json
import re
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(name: str) -> dict:
    return json.loads((repo_root() / "config" / name).read_text(encoding="utf-8"))


def split_units(text: str) -> list[str]:
    raw = re.split(r"(?:\r?\n\s*[-*•]\s+|\r?\n\s*\d+[.)]\s+|[.;]\s+|\r?\n+)", text)
    units = [u.strip(" -•\t\r\n") for u in raw if u and u.strip(" -•\t\r\n")]
    return units or [text.strip()]


def detect_kind(text: str, claim_kinds: dict) -> tuple[str, list[str]]:
    """Return highest-priority matching kind and all matches for auditability."""
    matches: list[tuple[int, str]] = []
    for kind, meta in claim_kinds.items():
        if re.search(meta["match_regex"], text, flags=re.IGNORECASE):
            matches.append((int(meta.get("priority", 0)), kind))
    if not matches:
        return "requirement", []
    matches.sort(key=lambda x: (-x[0], x[1]))
    return matches[0][1], [kind for _, kind in matches]


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
        kind, matched_kinds = detect_kind(unit, kinds_cfg)
        bucket = kind_to_bucket.get(kind, "integration")
        priority = priority_rules.get(kind, priority_rules.get("default", "normal"))
        claim = {
            "claim_id": make_claim_id(i),
            "text": unit,
            "kind": kind,
            "matched_kinds": matched_kinds,
            "bucket": bucket,
            "priority": priority,
            "dependencies": [],
            "reason_codes": ["CLAIM_PARSED", "BUCKET_ASSIGNED"],
        }
        claims.append(claim)
        grouped.setdefault(bucket, []).append(claim["claim_id"])
    return {"ok": True, "claims": claims, "grouped_buckets": grouped}


def main() -> int:
    parser = argparse.ArgumentParser(description="Split task text into deterministic claim units")
    parser.add_argument("task_text")
    args = parser.parse_args()
    print(json.dumps(split_claims(args.task_text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
