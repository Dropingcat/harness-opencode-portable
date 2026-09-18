#!/usr/bin/env python3
"""Stub gate for the coder-dom pre-commit hook (CD-004).

Fails when unconcious stubs are present (status=stub without `# stub:` marker).
Conscious stubs (marked `# stub: <id>` / `# dead: disable`) are allowed — they are
tracked debt, not silent code.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import stub_detect


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail on unconcious code stubs.")
    ap.add_argument("--root", default=r"E:\Documents\Документы\doc_Opencode_agern-new")
    args = ap.parse_args(argv)

    report = stub_detect.scan_stubs(args.root)
    unconcious = [s for s in report["stubs"] if not s["conscious"]]
    counts = report["counts"]

    if unconcious:
        print(f"[coder-dom] FAIL: unconcious stubs (no # stub: marker): {len(unconcious)}")
        for s in unconcious[:12]:
            print(f"  {s['module']}:{s['name']} line {s['line']}")
        print("  Fix: implement the function OR mark it # stub: <issue-id>")
        return 1

    print(f"[coder-dom] OK: stubs={counts['stubs']} interfaces={counts['interfaces']} normal={counts['normal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())