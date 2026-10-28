#!/usr/bin/env python3
"""CLI entrypoint; server entrypoint and more commands are added incrementally."""
import argparse
import json
import sys

from knowledge_pilot.runtime import HOME, catalog, configure


def main():
    configure()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    lookup = sub.add_parser("lookup")
    lookup.add_argument("question")
    trace = sub.add_parser("trace")
    trace.add_argument("artifact")
    sub.add_parser("export")
    sub.add_parser("refresh")
    sub.add_parser("probe")
    graph = sub.add_parser("graph")
    graph.add_argument("question")
    start = sub.add_parser("run")
    start.add_argument("operation", choices=["web_search", "network_probe", "project_context", "table_profile"])
    start.add_argument("--question")
    start.add_argument("--path")
    start.add_argument("--url")
    start.add_argument("--max-rows", type=int, default=100000)
    start.add_argument("--retry", action="store_true")
    start.add_argument("--wait", type=int, default=90)
    sub.add_parser("test")
    registration = sub.add_parser("register")
    registration.add_argument("artifact")
    registration.add_argument("--input", action="append", default=[])
    registration.add_argument("--coverage", action="append", required=True)
    registration.add_argument("--status", choices=["draft", "accepted", "superseded", "rejected"], default="draft")
    registration.add_argument("--gap", action="append", default=[])
    registration.add_argument("--confirm-acceptance", action="store_true")
    sub.add_parser("smoke")
    sub.add_parser("verify-corpus")
    args = parser.parse_args()
    if args.command == "verify-corpus":
        from verify_corpus import verify
        verify()
        return 0
    if args.command == "smoke":
        import asyncio
        from verify_mcp import verify
        asyncio.run(verify())
        return 0
    if args.command == "test":
        import unittest
        suite = unittest.defaultTestLoader.discover(str(HOME / "tests"))
        return 0 if unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite).wasSuccessful() else 1
    if args.command in {"probe", "run"}:
        from knowledge_pilot.service import Service
        service = Service()
        operation = "network_probe" if args.command == "probe" else args.operation
        payload = {key: value for key, value in vars(args).items() if key in {"question", "path", "url", "max_rows", "retry"} and value is not None}
        job = service.start(operation, **payload)
        result = service.jobs.wait(job["id"], getattr(args, "wait", 90)) if "id" in job else job
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") not in {"failed", "blocked"} else 1
    store = catalog()
    if args.command == "scan":
        result = store.scan()
        (HOME / "artifacts").mkdir(exist_ok=True)
        (HOME / "artifacts/corpus_coverage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    elif args.command == "lookup":
        result = store.lookup(args.question)
    elif args.command == "export":
        from knowledge_pilot.projection import export_catalog
        result = export_catalog(store)
    elif args.command == "refresh":
        result = store.refresh()
    elif args.command == "register":
        if args.status == "accepted" and not args.confirm_acceptance:
            parser.error("accepted requires --confirm-acceptance; acceptance is never inferred")
        result = store.register(args.artifact, coverage=args.coverage, inputs=args.input,
                                status=args.status, gaps=args.gap)
    elif args.command == "graph":
        from knowledge_pilot.projection import graph_query
        result = graph_query(store, args.question)
    else:
        result = store.trace(args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
