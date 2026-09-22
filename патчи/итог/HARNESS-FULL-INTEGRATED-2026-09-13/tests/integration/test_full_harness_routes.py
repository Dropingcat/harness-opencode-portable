from __future__ import annotations

from pathlib import Path

from scripts.router.resolve_route import resolve

ROOT = Path(__file__).resolve().parents[2]


def test_writer_researcher_coder_routes_share_one_runtime_snapshot() -> None:
    cases = {
        "написать текст статьи": ("writing-prose", "writing"),
        "исследуй литературу и проверь гипотезу": ("academic-research", "research"),
        "реализуй модуль и прогони тесты": ("code-implementation", "code"),
    }
    hashes = set()
    for prompt, expected in cases.items():
        result = resolve(prompt)
        assert result["ok"] is True
        assert (result["route_id"], result["bucket"]) == expected
        assert result["snapshot_backed"] is True
        hashes.add(result["policy_hash"])
    assert len(hashes) == 1


def test_core_peer_agents_and_runtime_entrypoints_are_packaged() -> None:
    required = [
        "agents/writing-orchestrator.md",
        "agents/article-writer.md",
        "agents/research-orchestrator.md",
        "agents/researcher.md",
        "agents/code-orchestrator.md",
        "agents/coder-worker.md",
        "agents/code-reviewer.md",
        "agents/code-tester.md",
        "agents/code-auditor.md",
        "scripts/writer/cli.py",
        "scripts/researcher/researcher_core",
        "scripts/code-factory/factory_ctl.py",
        "scripts/jobs/job_ctl.py",
        "scripts/router/resolve_route.py",
        "mcp/launchers/opencode_code_worker.py",
        "mcp/launchers/opencode_research_academic.py",
        "mcp/launchers/opencode_tribunal_role.py",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    assert missing == []
