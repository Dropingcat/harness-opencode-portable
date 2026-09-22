from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CODE_FACTORY = ROOT / "scripts" / "code-factory"
if str(CODE_FACTORY) not in sys.path:
    sys.path.insert(0, str(CODE_FACTORY))

from code_factory_runner import (  # noqa: E402
    create_state,
    finalize,
    guard_artifact,
    load_state,
    register_artifact,
    replay,
    save_state,
    start,
    submit_evidence,
    validate,
)


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _worker(module: str = "core") -> dict:
    return {"module": module, "code": "def value():\n    return 42\n", "description": "bounded implementation"}


def _reviewer(module: str = "core", verdict: str = "APPROVE") -> dict:
    return {
        "module": module,
        "verdict": verdict,
        "comments": [
            {
                "file": "core.py",
                "line": 1,
                "problem": "reviewed implementation boundary",
                "suggestion": "retain typed contract",
                "falsification": "run the acceptance test and observe a different result",
            }
        ],
    }


def _tester(module: str = "core", result: str = "PASS") -> dict:
    return {"module": module, "result": result, "passed": 3 if result == "PASS" else 2, "failed": 0 if result == "PASS" else 1, "coverage": 95}


def _auditor(verdict: str = "APPROVE") -> dict:
    return {
        "verdict": verdict,
        "justification": "The event chain, contracts, gates, and provenance were checked end to end.",
        "process_analysis": {
            "contracts_respected": True,
            "iteration_count": 1,
            "iteration_limit": 3,
            "role_violation": False,
        },
    }


def _new_state(tmp_path: Path, *, limit: int = 3):
    state_path = tmp_path / "factory_state.json"
    state = create_state("TASK-CODER-E2E", "Coder event sourced acceptance", limit, 20.0)
    save_state(state, str(state_path))
    start(state, str(state_path))
    return state, state_path


def test_happy_path_worker_review_test_audit_finalize_and_replay(tmp_path: Path) -> None:
    state, state_path = _new_state(tmp_path)
    module = "core"

    submit_evidence(state, "worker", module, _worker(module), str(state_path), output_file=str(_write(tmp_path / "worker.json", _worker(module))))
    submit_evidence(state, "reviewer", module, _reviewer(module), str(state_path), output_file=str(_write(tmp_path / "reviewer.json", _reviewer(module))))
    submit_evidence(state, "tester", module, _tester(module), str(state_path), output_file=str(_write(tmp_path / "tester.json", _tester(module))))
    final_state = submit_evidence(state, "auditor", module, _auditor(), str(state_path), output_file=str(_write(tmp_path / "auditor.json", _auditor())))

    assert final_state == "PASSED"
    assert validate(state) == []
    before = replay(state)
    assert before["cycle"]["state"] == "PASSED"
    assert before["gate_set"] == {"reviewer": "PASS", "tester": "PASS", "auditor": "PASS"}

    assert finalize(state, str(state_path)) == "DONE"
    restored = load_state(str(state_path))
    after = replay(restored)
    assert after["cycle"]["state"] == "DONE"
    assert after["cycle"]["stop_reason"] == "finalized"
    assert validate(restored) == []


def test_untrusted_artifact_requires_guard_before_evidence_reference(tmp_path: Path) -> None:
    state, state_path = _new_state(tmp_path)
    external = tmp_path / "external.txt"
    external.write_text("untrusted source text", encoding="utf-8")
    aid = register_artifact(state, str(external), str(state_path), origin="web", tool_id="webfetch")

    worker_payload = _worker()
    worker_file = _write(tmp_path / "worker.json", worker_payload)
    with pytest.raises(ValueError, match="guard PASS required"):
        submit_evidence(state, "worker", "core", worker_payload, str(state_path), output_file=str(worker_file), artifact_refs=[aid])

    assert guard_artifact(state, aid, "PASS", str(state_path), guard_id="guard-e2e") == "PASS"
    assert submit_evidence(state, "worker", "core", worker_payload, str(state_path), output_file=str(worker_file), artifact_refs=[aid]) == "RUNNING"
    assert validate(state) == []


def test_two_reviewer_retries_raise_tribunal_requirement_without_silent_truth_mutation(tmp_path: Path) -> None:
    state, state_path = _new_state(tmp_path, limit=3)
    module = "core"
    worker_payload = _worker(module)
    submit_evidence(state, "worker", module, worker_payload, str(state_path), output_file=str(_write(tmp_path / "worker.json", worker_payload)))

    review = _reviewer(module, "REQUEST_CHANGES")
    submit_evidence(state, "reviewer", module, review, str(state_path), output_file=str(_write(tmp_path / "review1.json", review)))
    assert state["cycle"]["state"] == "REWORK"
    submit_evidence(state, "reviewer", module, review, str(state_path), output_file=str(_write(tmp_path / "review2.json", review)))

    replayed = replay(state)
    assert replayed["cycle"]["state"] == "REWORK"
    assert replayed["tribunal_required"] == [{"module": module, "review_fail_count": 2, "threshold": 2}]
    with pytest.raises(ValueError, match="expected PASSED"):
        finalize(state, str(state_path))


def test_event_chain_tamper_is_detected(tmp_path: Path) -> None:
    state, state_path = _new_state(tmp_path)
    payload = _worker()
    submit_evidence(state, "worker", "core", payload, str(state_path), output_file=str(_write(tmp_path / "worker.json", payload)))
    state["events"][0]["payload"]["task_name"] = "tampered"
    errors = validate(state)
    assert any("hash" in err.lower() for err in errors)


def test_factory_cli_worker_submit_never_snapshots_process_cwd_without_explicit_workdir(tmp_path: Path) -> None:
    import subprocess

    # The distributed code milestone intentionally has no .git directory.  Build a
    # disposable controller repository instead of assuming the Harness checkout is
    # itself a Git worktree.  This preserves the real invariant we care about:
    # factory_ctl must never mutate whatever Git repository happens to be process CWD.
    controller = tmp_path / "controller_repo"
    controller.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=controller, check=True)
    subprocess.run(["git", "config", "user.email", "coder-acceptance@local.invalid"], cwd=controller, check=True)
    subprocess.run(["git", "config", "user.name", "Coder Acceptance"], cwd=controller, check=True)
    (controller / "sentinel.txt").write_text("controller repository\n", encoding="utf-8")
    subprocess.run(["git", "add", "sentinel.txt"], cwd=controller, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=controller, check=True)

    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=controller, capture_output=True, text=True, check=True).stdout.strip()
    state_path = tmp_path / "state.json"
    init = subprocess.run(
        [sys.executable, str(CODE_FACTORY / "factory_ctl.py"), "init", "t-safe", "safe snapshot", "--state", str(state_path)],
        cwd=controller, capture_output=True, text=True,
    )
    assert init.returncode == 0, init.stdout + init.stderr
    worker_file = _write(tmp_path / "worker_cli.json", _worker())
    submit = subprocess.run(
        [sys.executable, str(CODE_FACTORY / "factory_ctl.py"), "submit", "worker", str(worker_file), "--state", str(state_path)],
        cwd=controller, capture_output=True, text=True,
    )
    assert submit.returncode == 0, submit.stdout + submit.stderr
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=controller, capture_output=True, text=True, check=True).stdout.strip()
    assert after == before
