#!/usr/bin/env python3
"""Code-factory facade: contracts -> provenance -> evidence -> reducer."""
import argparse, json, os, sys, tempfile
from pathlib import Path
from code_factory_runner import (create_state,load_state,save_state,start,submit_evidence,add_budget,
    auditor_block,finalize,resume,replay,validate,register_artifact,guard_artifact,sanitize_artifact)
from contract_validator import validate as validate_contract


def _default_state():
    if os.getenv("OPENCODE_FACTORY_STATE"): return os.environ["OPENCODE_FACTORY_STATE"]
    if os.getenv("OPENCODE_RUNS_DIR"): return os.path.join(os.environ["OPENCODE_RUNS_DIR"],"factory_state.json")
    return os.path.join(tempfile.gettempdir(),"factory_state.json")
def _state_path(args): return args.state or _default_state()
def _load_output(path):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f"output not found: {path}")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def cmd_init(a):
    gates=[x.strip() for x in a.gates.split(",") if x.strip()] if a.gates else None
    st=create_state(a.task_id,a.task_name,a.limit,a.budget,gates); save_state(st,_state_path(a)); start(st,_state_path(a))
    print(json.dumps({"ok":True,"state":st["cycle"]["state"],"path":_state_path(a),"required_gates":st["projection"]["required_gates"],"version":3})); return 0

def _git_snapshot(module, task_id, workdir=None):
    """Детерминированный снапшот рабочего дерева после сдачи воркера.

    Инициализирует git-репо в CWD (если его нет) и коммитит изменения.
    Используется как защита от потери кода между сессиями (см. нахождение #6).
    Не требует git: если git недоступен или коммитить нечего — тихий no-op.
    """
    try:
        import subprocess
        wd = workdir or os.getcwd()
        git = subprocess.run(["git", "-C", wd, "rev-parse", "--is-inside-work-tree"],
                             capture_output=True, text=True)
        if git.returncode != 0:
            subprocess.run(["git", "-C", wd, "init", "-q"], check=False)
            subprocess.run(["git", "-C", wd, "add", "-A"], check=False)
            subprocess.run(["git", "-C", wd, "commit", "-q", "-m",
                            f"factory: bootstrap {task_id}"], check=False)
        else:
            subprocess.run(["git", "-C", wd, "add", "-A"], check=False)
            r = subprocess.run(["git", "-C", wd, "status", "--porcelain"],
                               capture_output=True, text=True)
            if r.stdout.strip():
                subprocess.run(["git", "-C", wd, "commit", "-q", "-m",
                                f"factory: {task_id} {module}"], check=False)
        return "ok"
    except Exception:
        return "skipped"

def cmd_submit(a):
    try: st=load_state(_state_path(a)); data=_load_output(a.output)
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 3
    errors=validate_contract(a.agent_type,data)
    if errors: print(json.dumps({"ok":False,"error":"INVALID","details":errors})); return 2
    try:
        s=submit_evidence(st,a.agent_type,a.module or data.get("module","default"),data,_state_path(a),output_file=a.output,artifact_refs=a.artifact or [])
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 4
    if a.agent_type == "worker":
        task_id = st.get("projection", {}).get("task", {}).get("task_id") or st.get("task", {}).get("task_id")
        _git_snapshot(a.module or data.get("module", "default"), task_id or a.task_id)
    print(json.dumps({"ok":True,"state":s,"stop_reason":st["cycle"]["stop_reason"],"attempt":st["cycle"]["attempt"],"rework_rounds":st["cycle"]["rework_rounds"],"attempt_limit":st["cycle"]["attempt_limit"],"gate_set":st["projection"]["gate_set"],"tribunal_required":st["projection"]["tribunal_required"],"provenance_errors":st["projection"]["provenance_errors"]})); return 0

def cmd_artifact_register(a):
    try:
        st=load_state(_state_path(a)); aid=register_artifact(st,a.file,_state_path(a),origin=a.origin,tool_id=a.tool_id,source_ref=a.source_ref,media_type=a.media_type,artifact_id=a.artifact_id)
        print(json.dumps({"ok":True,"artifact_id":aid,"record":st["artifacts"].get(aid)})); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 4

def cmd_artifact_guard(a):
    try:
        st=load_state(_state_path(a)); v=guard_artifact(st,a.artifact_id,a.verdict,_state_path(a),guard_id=a.guard_id,guard_policy_hash=a.policy_hash)
        print(json.dumps({"ok":True,"artifact_id":a.artifact_id,"verdict":v})); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 4

def cmd_artifact_sanitize(a):
    try:
        st=load_state(_state_path(a)); aid=sanitize_artifact(st,a.source_artifact_id,a.file,_state_path(a),sanitizer_id=a.sanitizer_id,artifact_id=a.artifact_id,notes=a.notes)
        print(json.dumps({"ok":True,"artifact_id":aid,"source_artifact_id":a.source_artifact_id})); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 4

def cmd_budget(a):
    st=load_state(_state_path(a)); s=add_budget(st,a.steps,a.cost,_state_path(a)); print(json.dumps({"ok":True,"state":s,"stop_reason":st["cycle"]["stop_reason"]})); return 0
def cmd_auditor_block(a):
    st=load_state(_state_path(a)); print(json.dumps({"ok":True,"state":auditor_block(st,_state_path(a))})); return 0
def cmd_finalize(a):
    try: st=load_state(_state_path(a)); print(json.dumps({"ok":True,"state":finalize(st,_state_path(a))})); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 4
def cmd_status(a):
    try: print(json.dumps(resume(load_state(_state_path(a))),ensure_ascii=False)); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 3
def cmd_replay(a):
    try:
        st=load_state(_state_path(a)); p=replay(st); print(json.dumps({"ok":True,"projection":p,"integrity_errors":validate(st)},ensure_ascii=False)); return 0
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 3

def main():
    q=argparse.ArgumentParser(prog="factory_ctl"); sub=q.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("init"); p.add_argument("task_id"); p.add_argument("task_name"); p.add_argument("--limit",type=int,default=3); p.add_argument("--budget",type=float,default=20.0); p.add_argument("--gates"); p.add_argument("--state")
    p=sub.add_parser("submit"); p.add_argument("agent_type",choices=["worker","reviewer","tester","auditor","experimenter"]); p.add_argument("output"); p.add_argument("--state"); p.add_argument("--module"); p.add_argument("--artifact",action="append",help="registered artifact id used as input/context; repeatable")
    p=sub.add_parser("artifact-register"); p.add_argument("file"); p.add_argument("--origin",required=True,choices=["agent_output","local_file","tool_internal","web","external_tool","subagent","user_supplied"]); p.add_argument("--tool-id"); p.add_argument("--source-ref"); p.add_argument("--media-type"); p.add_argument("--artifact-id"); p.add_argument("--state")
    p=sub.add_parser("artifact-guard"); p.add_argument("artifact_id"); p.add_argument("verdict",choices=["PASS","FAIL","BLOCK","INVALID"]); p.add_argument("--guard-id",default="manual_guard"); p.add_argument("--policy-hash"); p.add_argument("--state")
    p=sub.add_parser("artifact-sanitize"); p.add_argument("source_artifact_id"); p.add_argument("file"); p.add_argument("--sanitizer-id",default="manual_sanitizer"); p.add_argument("--artifact-id"); p.add_argument("--notes"); p.add_argument("--state")
    p=sub.add_parser("budget"); p.add_argument("steps",type=int); p.add_argument("cost",type=float); p.add_argument("--state")
    p=sub.add_parser("auditor_block"); p.add_argument("--state")
    p=sub.add_parser("finalize"); p.add_argument("--state")
    p=sub.add_parser("status"); p.add_argument("--state")
    p=sub.add_parser("replay"); p.add_argument("--state")
    a=q.parse_args(); funcs={"init":cmd_init,"submit":cmd_submit,"artifact-register":cmd_artifact_register,"artifact-guard":cmd_artifact_guard,"artifact-sanitize":cmd_artifact_sanitize,"budget":cmd_budget,"auditor_block":cmd_auditor_block,"finalize":cmd_finalize,"status":cmd_status,"replay":cmd_replay}
    return funcs[a.cmd](a)
if __name__=="__main__": sys.exit(main())
