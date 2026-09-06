#!/usr/bin/env python3
"""Единый контроллер фабрики кода: валидация контракта + state machine + audit."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from code_factory_runner import create_state, load_state, save_state, start, record_verdict, add_budget, auditor_block, finalize, resume
from contract_validator import validate as validate_contract


def _default_state() -> str:
    if os.getenv("OPENCODE_FACTORY_STATE"):
        return os.environ["OPENCODE_FACTORY_STATE"]
    if os.getenv("OPENCODE_RUNS_DIR"):
        return os.path.join(os.environ["OPENCODE_RUNS_DIR"], "factory_state.json")
    return os.path.join(tempfile.gettempdir(), "factory_state.json")


def _state_path(args) -> str:
    return args.state or _default_state()


def cmd_init(args) -> int:
    path = _state_path(args)
    state = create_state(args.task_id, args.task_name, iteration_limit=args.limit, max_cost_rub=args.budget)
    save_state(state, path)
    start(state, path)
    print(json.dumps({"ok": True, "state": "RUNNING", "path": path}))
    return 0


def cmd_submit(args) -> int:
    path = _state_path(args)
    if not Path(path).exists():
        print(json.dumps({"ok": False, "error": f"state not found: {path}"}))
        return 3
    state = load_state(path)
    out_path = args.output
    if not Path(out_path).exists():
        print(json.dumps({"ok": False, "error": f"output not found: {out_path}"}))
        return 2
    try:
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid JSON: {e}"}))
        return 2
    errors = validate_contract(args.agent_type, data)
    if errors:
        print(json.dumps({"ok": False, "error": "INVALID", "details": errors}))
        return 2
    module = args.module or data.get("module", "default")
    if args.agent_type == "reviewer":
        new_state = record_verdict(state, module, data["verdict"], path)
    elif args.agent_type == "auditor":
        verdict = data["verdict"]
        if verdict == "INVALID_INPUT":
            new_state = "BLOCKED"
            state["cycle"]["state"] = "BLOCKED"
            state["cycle"]["stop_reason"] = "invalid_input"
            save_state(state, path)
        elif verdict == "REJECT":
            new_state = record_verdict(state, module, "REJECT", path)
        elif verdict == "REQUEST_CHANGES":
            new_state = record_verdict(state, module, "REQUEST_CHANGES", path)
        else:
            new_state = record_verdict(state, module, "APPROVE", path)
    elif args.agent_type == "tester":
        state["verdicts"].setdefault(f"test_{module}", []).append({"iteration": state["cycle"]["iteration"], "result": data["result"]})
        # Tests PASS + нет активных незакрытых rework -> PASSED
        if data.get("result") == "PASS":
            open_rework = any(
                v.get("verdict") in ("REQUEST_CHANGES", "REJECT")
                for verifieds in state["verdicts"].values()
                for v in verifieds
                if isinstance(v, dict)
            )
            if not open_rework:
                state["cycle"]["state"] = "PASSED"
                state["cycle"]["stop_reason"] = "tests_passed"
        save_state(state, path)
        new_state = state["cycle"]["state"]
    else:
        new_state = state["cycle"]["state"]
    print(json.dumps({"ok": True, "state": new_state, "stop_reason": state["cycle"]["stop_reason"]}))
    return 0


def cmd_budget(args) -> int:
    path = _state_path(args)
    state = load_state(path)
    new_state = add_budget(state, args.steps, args.cost, path)
    print(json.dumps({"ok": True, "state": new_state, "stop_reason": state["cycle"]["stop_reason"]}))
    return 0


def cmd_auditor_block(args) -> int:
    path = _state_path(args)
    state = load_state(path)
    print(json.dumps({"ok": True, "state": auditor_block(state, path)}))
    return 0


def cmd_finalize(args) -> int:
    path = _state_path(args)
    state = load_state(path)
    print(json.dumps({"ok": True, "state": finalize(state, path)}))
    return 0


def cmd_status(args) -> int:
    path = _state_path(args)
    if not Path(path).exists():
        print(json.dumps({"ok": False, "error": "no state"}))
        return 3
    state = load_state(path)
    print(json.dumps(resume(state), ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="factory_ctl")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("task_id")
    p_init.add_argument("task_name")
    p_init.add_argument("--limit", type=int, default=3)
    p_init.add_argument("--budget", type=float, default=20.0)
    p_init.add_argument("--state")
    p_sub = sub.add_parser("submit")
    p_sub.add_argument("agent_type", choices=["worker", "reviewer", "tester", "auditor", "experimenter"])
    p_sub.add_argument("output")
    p_sub.add_argument("--state")
    p_sub.add_argument("--module", default=None)
    p_bud = sub.add_parser("budget")
    p_bud.add_argument("steps", type=int)
    p_bud.add_argument("cost", type=float)
    p_bud.add_argument("--state")
    p_ab = sub.add_parser("auditor_block")
    p_ab.add_argument("--state")
    p_fin = sub.add_parser("finalize")
    p_fin.add_argument("--state")
    p_st = sub.add_parser("status")
    p_st.add_argument("--state")
    args = parser.parse_args()
    return {
        "init": cmd_init,
        "submit": cmd_submit,
        "budget": cmd_budget,
        "auditor_block": cmd_auditor_block,
        "finalize": cmd_finalize,
        "status": cmd_status,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
