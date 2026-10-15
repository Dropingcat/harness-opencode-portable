#!/usr/bin/env python3
"""Canonical file scanner; no DB, receipt shortcut or command-selected provider."""
import argparse
import json
from pathlib import Path
import sys

OWN_ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'scan'])
    parser.add_argument('--harness-root')
    parser.add_argument('--config')
    parser.add_argument('--artifact')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        sys.path.insert(0, str(OWN_ROOT / 'guard/src'))
        import artifact_guard
        if Path(artifact_guard.__file__).resolve() != OWN_ROOT / 'guard/src/artifact_guard.py':
            raise ImportError()
        if args.command == 'preflight':
            result = artifact_guard.preflight(harness_root=args.harness_root, config=args.config)
            code = 0 if result['readiness'] else 1
        else:
            result = artifact_guard.scan_artifact(args.artifact, harness_root=args.harness_root, config=args.config)
            code = 0 if result['ok'] else 1
    except Exception:
        result = {'ok': False, 'verdict': 'BLOCK', 'reason': 'scanner_unavailable',
                  'required_stages': ['P0', 'P2'], 'executed_stages': [],
                  'artifact': {'sha256': None, 'bytes': None},
                  'coverage': {'complete': False}, 'identity': None}
        code = 1
    print(json.dumps(result, ensure_ascii=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
