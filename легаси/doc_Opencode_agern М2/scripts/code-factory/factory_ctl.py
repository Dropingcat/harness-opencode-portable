#!/usr/bin/env python3
"""Code-factory facade: validate agent contracts -> append evidence -> reduce state."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from code_factory_runner import create_state, load_state, save_state, start, submit_evidence, add_budget, auditor_block, finalize, resume, replay, validate
from contract_validator import validate as validate_contract


def _default_state() -> str:
    if os.getenv("OPENCODE_FACTORY_STATE"): return os.environ["OPENCODE_FACTORY_STATE"]
    if os.getenv("OPENCODE_RUNS_DIR"): return os.path.join(os.environ["OPENCODE_RUNS_DIR"], "factory_state.json")
    return os.path.join(tempfile.gettempdir(), "factory_state.json")

def _state_path(args): return args.state or _default_state()

def _load_output(path):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f"output not found: {path}")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def cmd_init(args):
    gates=[x.strip() for x in args.gates.split(",") if x.strip()] if args.gates else None
    state=create_state(args.task_id,args.task_name,args.limit,args.budget,gates)
    save_state(state,_state_path(args)); start(state,_state_path(args))
    print(json.dumps({"ok":True,"state":state["cycle"]["state"],"path":_state_path(args),"required_gates":state["projection"]["required_gates"]})); return 0

def cmd_submit(args):
    path=_state_path(args)
    try: state=load_state(path)
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 3
    try: data=_load_output(args.output)
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 2
    errors=validate_contract(args.agent_type,data)
    if errors: print(json.dumps({"ok":False,"error":"INVALID","details":errors})); return 2
    module=args.module or data.get("module","default")
    try: new_state=submit_evidence(state,args.agent_type,module,data,path)
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 4
    print(json.dumps({"ok":True,"state":new_state,"stop_reason":state["cycle"]["stop_reason"],"attempt":state["cycle"]["attempt"],"gate_set":state["projection"]["gate_set"]})); return 0

def cmd_budget(args):
    state=load_state(_state_path(args)); s=add_budget(state,args.steps,args.cost,_state_path(args)); print(json.dumps({"ok":True,"state":s,"stop_reason":state["cycle"]["stop_reason"]})); return 0

def cmd_auditor_block(args):
    state=load_state(_state_path(args)); print(json.dumps({"ok":True,"state":auditor_block(state,_state_path(args))})); return 0

def cmd_finalize(args):
    try:
        state=load_state(_state_path(args)); s=finalize(state,_state_path(args)); print(json.dumps({"ok":True,"state":s})); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 4

def cmd_status(args):
    try: state=load_state(_state_path(args)); print(json.dumps(resume(state),ensure_ascii=False)); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 3

def cmd_replay(args):
    try:
        state=load_state(_state_path(args)); p=replay(state); print(json.dumps({"ok":True,"projection":p,"integrity_errors":validate(state)},ensure_ascii=False)); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 3

def main():
    parser=argparse.ArgumentParser(prog="factory_ctl"); sub=parser.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("init"); p.add_argument("task_id"); p.add_argument("task_name"); p.add_argument("--limit",type=int,default=3); p.add_argument("--budget",type=float,default=20.0); p.add_argument("--gates"); p.add_argument("--state")
    p=sub.add_parser("submit"); p.add_argument("agent_type",choices=["worker","reviewer","tester","auditor","experimenter"]); p.add_argument("output"); p.add_argument("--state"); p.add_argument("--module")
    p=sub.add_parser("budget"); p.add_argument("steps",type=int); p.add_argument("cost",type=float); p.add_argument("--state")
    p=sub.add_parser("auditor_block"); p.add_argument("--state")
    p=sub.add_parser("finalize"); p.add_argument("--state")
    p=sub.add_parser("status"); p.add_argument("--state")
    p=sub.add_parser("replay"); p.add_argument("--state")
    args=parser.parse_args(); return {"init":cmd_init,"submit":cmd_submit,"budget":cmd_budget,"auditor_block":cmd_auditor_block,"finalize":cmd_finalize,"status":cmd_status,"replay":cmd_replay}[args.cmd](args)

if __name__=="__main__": sys.exit(main())
