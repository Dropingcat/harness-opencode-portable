#!/usr/bin/env python3
"""CI smoke-test: MCP-серверы (academic_search, searxng_search) отвечают.

Запускается из GitHub Actions (ci.yml -> mcp-test job). Не зависит от
runtime opencode — тестирует call_tool напрямую через mcp SDK 1.26.0.
"""
import asyncio
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2]  # harness root
sys.path.insert(0, str(HARNESS / "mcp"))
sys.path.insert(0, str(HARNESS / "scripts" / "research"))


def txt_of(res):
    return res[0].text if isinstance(res, list) else str(res)


async def main() -> int:
    failures = []

    try:
        import academic_search_server as s
        res = await s.call_tool("arxiv_search", {"query": "nitriding steel", "max_results": 2})
        ok = '"ok": true' in txt_of(res)
        print("arxiv_search:", "OK" if ok else "FAIL")
        if not ok:
            failures.append("arxiv_search")
    except Exception as e:
        print("arxiv_search: FAIL", e)
        failures.append("arxiv_search")

    try:
        import academic_search_server as s
        res = await s.call_tool("openalex_search", {"query": "nitriding steel", "per_page": 2})
        ok = '"ok": true' in txt_of(res)
        print("openalex_search:", "OK" if ok else "FAIL")
        if not ok:
            failures.append("openalex_search")
    except Exception as e:
        print("openalex_search: FAIL", e)
        failures.append("openalex_search")

    try:
        import searxng_search_server as s
        res = await s.call_tool("searxng_search", {"query": "nitriding steel", "limit": 2})
        ok = '"ok": true' in txt_of(res)
        print("searxng_search:", "OK" if ok else "SKIP (нет инстанса)")
    except Exception as e:
        print("searxng_search: SKIP (нет инстанса):", e)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))