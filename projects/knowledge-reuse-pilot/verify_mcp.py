"""Live stdio protocol checks, including real-data no-repeat local processing."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import tempfile

from knowledge_pilot.runtime import HOME, configure

configure()

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowledge_pilot.catalog import Catalog, digest_file
from knowledge_pilot.projection import export_catalog


@asynccontextmanager
async def client(script, *args):
    parameters = StdioServerParameters(command=sys.executable,
        args=["-B", str(HOME / script), *args], cwd=str(HOME), env=dict(os.environ))
    with (HOME / "logs" / (script + ".stderr.log")).open("a", encoding="utf-8") as errlog:
        async with stdio_client(parameters, errlog=errlog) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                initialized = await session.initialize()
                yield session, initialized


async def call(session, name, arguments):
    result = await session.call_tool(name, arguments)
    if result.isError:
        raise AssertionError(f"{name}: {result.content}")
    return json.loads(next(item.text for item in result.content if item.type == "text"))


async def verify():
    evidence = {}
    async with client("mcp_server.py") as (session, initialized):
        tools = await session.list_tools()
        names = [tool.name for tool in tools.tools]
        assert {"knowledge_lookup", "knowledge_trace", "knowledge_start", "knowledge_job"}.issubset(names)
        lookup = await call(session, "knowledge_lookup", {"question": "nitrogen diffusion", "limit": 2})
        path = Path("F:/1/data.csv")
        before = digest_file(path)
        request = {"operation": "table_profile", "path": str(path), "max_rows": 1000,
                   "question": "pilot: describe F:/1/data.csv"}
        first = await call(session, "knowledge_start", request)
        finished = await call(session, "knowledge_job", {"id": first["id"], "wait_seconds": 20})
        assert finished["status"] == "completed", finished
        repeated = await call(session, "knowledge_start", request)
        assert repeated["id"] == first["id"] and repeated["reused"], repeated
        assert before == digest_file(path), "corpus input changed"
        context = await call(session, "knowledge_start", {"operation": "project_context"})
        context_result = await call(session, "knowledge_job", {"id": context["id"], "wait_seconds": 20})
        assert context_result["status"] == "completed", context_result
        evidence["pilot_mcp"] = {"server": initialized.serverInfo.name, "tools": names,
             "lookup_action": lookup["action"], "candidate_count": len(lookup["candidates"]),
             "local_analysis_job": first["id"], "repeat_job_same": True,
             "repeat_job_reused": repeated["reused"], "input_hash_unchanged": True,
             "rows_profiled": finished["result"]["rows_profiled"], "thread_context": context_result["result"]}
    with tempfile.TemporaryDirectory(dir=HOME / "tmp") as directory:
        base = Path(directory)
        source = base / "corpus"
        source.mkdir()
        (source / "primary.md").write_text("Primary evidence", encoding="utf-8")
        (source / "report.md").write_text("See [primary](primary.md).", encoding="utf-8")
        catalog = Catalog(base / "pilot", {"fixture": source})
        catalog.scan()
        graph = export_catalog(catalog)
        async with client("graphify_server.py", "--graph", graph["graph"]) as (session, initialized):
            tools = await session.list_tools()
            stats = await session.call_tool("graph_stats", {})
            queried = await session.call_tool("query_graph", {"question": "primary", "token_budget": 500})
            assert not stats.isError and not queried.isError
            assert any("primary" in getattr(item, "text", "").lower() for item in queried.content)
            evidence["native_graphify_mcp"] = {"server": initialized.serverInfo.name,
                "tool_count": len(tools.tools), "query_graph_pass": True,
                "graph_stats_pass": True, "fixture_nodes": graph["nodes"],
                "note": "real Graphify server, isolated fixture graph"}
    (HOME / "artifacts/mcp_smoke.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return evidence


if __name__ == "__main__":
    asyncio.run(verify())
