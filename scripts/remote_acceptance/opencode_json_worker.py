#!/usr/bin/env python3
"""OpenCode semantic worker adapter for remote Harness acceptance.

Reads one serialized TribunalExecutionEnvelope JSON object from stdin and writes
exactly one provider-draft JSON object to stdout. Diagnostics go to stderr.
No Harness authority is changed here; deterministic validation occurs in the
caller after the provider returns.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # Tolerate a single markdown fence from a provider, but do not silently
    # accept arbitrary prose around multiple JSON objects.
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S | re.I)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    decoder = json.JSONDecoder()
    starts = [m.start() for m in re.finditer(r"\{", text)]
    parsed: list[dict[str, Any]] = []
    for start in starts:
        try:
            obj, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            parsed.append(obj)
    return parsed[0] if len(parsed) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opencode-bin", default=os.environ.get("OPENCODE_BIN", "opencode"))
    ap.add_argument("--model", required=True)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--runs-dir", required=True)
    args = ap.parse_args()

    try:
        envelope = json.load(sys.stdin)
    except Exception as exc:
        print(f"invalid TEX stdin: {exc}", file=sys.stderr)
        return 2
    if not isinstance(envelope, dict):
        print("TEX stdin must be a JSON object", file=sys.stderr)
        return 2

    # Import only after setting the runtime paths because _runner resolves them
    # at module import time.
    os.environ["OPENCODE_BIN"] = args.opencode_bin
    os.environ["OPENCODE_RUNS_DIR"] = str(Path(args.runs_dir).resolve())
    from mcp.launchers import _runner
    contract_path = ROOT / "config" / "tribunal_role_provider_contract.md"
    CONTRACT = contract_path.read_text(encoding="utf-8")

    _runner.OPENCODE_BIN = args.opencode_bin
    _runner.RUNS_BASE = Path(args.runs_dir).resolve()
    task = "EXECUTION_ENVELOPE:\n" + json.dumps(envelope, ensure_ascii=False, indent=2)
    result = asyncio.run(
        _runner.run_with_contract(
            "tribunal_role_remote_acceptance",
            task,
            CONTRACT,
            args.model,
            args.timeout,
        )
    )
    run_dir = Path(str(result.get("run_dir") or ""))
    if not result.get("ok"):
        print(json.dumps({"worker_result": result}, ensure_ascii=False), file=sys.stderr)
        return 3

    payload: dict[str, Any] | None = None
    results_path = run_dir / "results.json"
    if results_path.exists():
        try:
            raw = json.loads(results_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload = raw
        except Exception as exc:
            print(f"results.json parse failure: {exc}", file=sys.stderr)
    if payload is None:
        payload = _extract_json(str(result.get("stdout") or ""))
    if payload is None:
        print(json.dumps({"error": "no unique provider JSON found", "worker_result": result}, ensure_ascii=False), file=sys.stderr)
        return 4

    # Keep stdout machine-clean for SubprocessJsonProviderTransport.
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
