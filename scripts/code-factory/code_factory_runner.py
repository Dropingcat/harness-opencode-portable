#!/usr/bin/env python3
"""Event-sourced code factory with artifact provenance.

Agents emit typed evidence. Artifacts are registered by hash. Untrusted inputs
must be guard-approved or replaced by a sanitized derivative before evidence may
reference them. The reducer remains the sole task-state authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from provenance import artifact_from_file, load_policy as load_provenance_policy, policy_hash as provenance_policy_hash, sha256_file
from state_reducer import canonical, event_hash, load_policy, reduce_events, verify_event_chain

DEFAULT_ITERATION_LIMIT = 3
DEFAULT_MAX_COST_RUB = 20.0
STATES = ["PENDING", "RUNNING", "REWORK", "PASSED", "FAILED", "AMBIGUOUS", "BLOCKED", "DONE"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_event(state: dict, typ: str, actor: str, payload: dict, attempt_id: str | None = None) -> dict:
    events = state.setdefault("events", [])
    ev = {"seq": len(events)+1, "event_id": str(uuid.uuid4()), "type": typ, "actor": actor,
          "attempt_id": attempt_id, "payload": payload, "ts": _now(),
          "prev_hash": events[-1]["event_hash"] if events else None}
    ev["event_hash"] = event_hash(ev)
    events.append(ev)
    return ev


def _materialize(state: dict) -> dict:
    projection = reduce_events(state["events"], load_policy())
    state["projection"] = projection
    for key in ("cycle","budget","attempts","evidence","verdicts","audit","tribunal_required"):
        state[key] = projection[key]
    state["artifacts"] = projection["artifacts"]
    state["artifact_guards"] = projection["artifact_guards"]
    state["provenance_errors"] = projection["provenance_errors"]
    state["_meta"]["updated_at"] = _now()
    return state


def create_state(task_id: str, task_name: str, iteration_limit: int = DEFAULT_ITERATION_LIMIT,
                 max_cost_rub: float = DEFAULT_MAX_COST_RUB, required_gates: list[str] | None = None) -> dict:
    gate_policy = load_policy(); prov_policy = load_provenance_policy()
    if iteration_limit < 1: raise ValueError("iteration_limit must be >= 1")
    gates = required_gates or list(gate_policy["required_gates"])
    gate_hash = hashlib.sha256(canonical(gate_policy).encode()).hexdigest()
    state={"_meta":{"version":3,"format":"event-sourced+provenance","created_at":_now(),"updated_at":_now()},"events":[]}
    _append_event(state,"TASK_CREATED","controller",{
        "task_id":task_id,"task_name":task_name,"attempt_limit":iteration_limit,"max_cost_rub":max_cost_rub,
        "required_gates":gates,"gate_policy_hash":gate_hash,"gate_policy":gate_policy,
        "provenance_policy_hash":provenance_policy_hash(prov_policy),"provenance_policy":prov_policy})
    return _materialize(state)


def load_state(path: str) -> dict:
    state=json.loads(Path(path).read_text(encoding="utf-8"))
    if state.get("_meta",{}).get("version") != 3:
        raise ValueError("factory state is not stage-3 provenance format; initialize a new run")
    errors=verify_event_chain(state.get("events",[]))
    if errors: raise ValueError("event log integrity failure: "+"; ".join(errors))
    return _materialize(state)


def save_state(state: dict, path: str) -> str:
    _materialize(state); content=json.dumps(state,ensure_ascii=False,indent=2)
    parent=os.path.dirname(os.path.abspath(path)); os.makedirs(parent,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=parent,prefix=".factory_tmp_",suffix=".tmp")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f: f.write(content)
        os.replace(tmp,path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return f"ok: wrote {os.path.getsize(path)} bytes to {path}"


def start(state: dict,path: str) -> str:
    if state["cycle"]["state"]!="PENDING": raise ValueError(f"start: expected PENDING, got {state['cycle']['state']}")
    _append_event(state,"ATTEMPT_STARTED","controller",{"attempt_id":"attempt-1","attempt_no":1,"kind":"initial"},"attempt-1")
    save_state(state,path); return state["cycle"]["state"]


def register_artifact(state: dict, file_path: str, path: str, *, origin: str, tool_id: str|None=None,
                      source_ref: str|None=None, media_type: str|None=None, metadata: dict|None=None,
                      artifact_id: str|None=None) -> str:
    aid=artifact_id or str(uuid.uuid4())
    rec=artifact_from_file(aid,file_path,origin=origin,tool_id=tool_id,source_ref=source_ref,
                           media_type=media_type,metadata=metadata,policy=load_provenance_policy())
    _append_event(state,"ARTIFACT_REGISTERED","controller",rec,state["attempts"][-1]["attempt_id"] if state["attempts"] else None)
    save_state(state,path); return aid


def guard_artifact(state: dict, artifact_id: str, verdict: str, path: str, *, guard_id: str="manual_guard",
                   findings: dict|None=None, guard_policy_hash: str|None=None) -> str:
    _materialize(state)
    if artifact_id not in state["artifacts"]: raise ValueError(f"unknown artifact_id: {artifact_id}")
    verdict=verdict.upper()
    if verdict not in {"PASS","FAIL","BLOCK","INVALID"}: raise ValueError("guard verdict must be PASS/FAIL/BLOCK/INVALID")
    payload={"artifact_id":artifact_id,"verdict":verdict,"guard_id":guard_id,
             "guard_policy_hash":guard_policy_hash,"findings":findings or {}}
    _append_event(state,"ARTIFACT_GUARD_VERDICT",guard_id,payload,state["attempts"][-1]["attempt_id"] if state["attempts"] else None)
    save_state(state,path); return verdict


def sanitize_artifact(state: dict, source_artifact_id: str, sanitized_file: str, path: str, *,
                      sanitizer_id: str="manual_sanitizer", artifact_id: str|None=None,
                      notes: str|None=None) -> str:
    _materialize(state)
    if source_artifact_id not in state["artifacts"]: raise ValueError(f"unknown source artifact: {source_artifact_id}")
    p=Path(sanitized_file)
    if not p.exists(): raise FileNotFoundError(sanitized_file)
    aid=artifact_id or str(uuid.uuid4())
    payload={"artifact_id":aid,"origin":"sanitized","trust":"sanitized","guard_required":False,
             "tool_id":sanitizer_id,"source_ref":None,"source_artifact_id":source_artifact_id,
             "path_hint":str(p),"content_hash":sha256_file(p),"size_bytes":p.stat().st_size,
             "media_type":"application/octet-stream","metadata":{"sanitizer_id":sanitizer_id,"notes":notes}}
    _append_event(state,"ARTIFACT_SANITIZED",sanitizer_id,payload,state["attempts"][-1]["attempt_id"] if state["attempts"] else None)
    save_state(state,path); return aid


def _begin_rework_if_fixing_worker(state: dict, agent_type: str) -> None:
    _materialize(state)
    if agent_type != "worker": return
    if state["cycle"]["state"] != "REWORK": return
    if state["cycle"]["rework_rounds"] >= state["cycle"]["attempt_limit"]: return
    next_no = state["cycle"]["attempt"] + 1
    aid = f"attempt-{next_no}"
    _append_event(state, "ATTEMPT_STARTED", "state_reducer", {"attempt_id": aid, "attempt_no": next_no, "kind": "rework"}, aid)
    _materialize(state)


def submit_evidence(state: dict, agent_type: str, module: str, data: dict, path: str,
                    *, output_file: str|None=None, artifact_refs: list[str]|None=None) -> str:
    if state["cycle"]["state"] in {"DONE","FAILED","BLOCKED","AMBIGUOUS"}: raise ValueError(f"cannot submit evidence in terminal state {state['cycle']['state']}")
    attempt_id=state["attempts"][-1]["attempt_id"]
    output_artifact_id=None
    if output_file:
        output_artifact_id=str(uuid.uuid4())
        rec=artifact_from_file(output_artifact_id,output_file,origin="agent_output",tool_id=agent_type,
                               source_ref=module,media_type="application/json",policy=load_provenance_policy())
        _append_event(state,"ARTIFACT_REGISTERED",agent_type,rec,attempt_id)
    if not output_artifact_id:
        raise ValueError("stage-3 evidence requires output_file provenance")
    refs=list(artifact_refs or [])
    _materialize(state)
    missing=[x for x in refs if x not in state["artifacts"]]
    if missing: raise ValueError("unknown artifact refs: "+", ".join(missing))
    guards=state["artifact_guards"]
    for aid in refs:
        rec=state["artifacts"][aid]
        if rec.get("guard_required"):
            gs=[g for g in guards if g.get("artifact_id")==aid]
            if not gs or gs[-1].get("verdict")!="PASS":
                raise ValueError(f"artifact {aid} is not admissible: guard PASS required")
    payload={"evidence_id":str(uuid.uuid4()),"agent_type":agent_type,"module":module,"data":data,
             "output_artifact_id":output_artifact_id,"artifact_refs":refs}
    _append_event(state,"AGENT_EVIDENCE",agent_type,payload,attempt_id); _materialize(state); _begin_rework_if_fixing_worker(state, agent_type); save_state(state,path)
    return state["cycle"]["state"]


def add_budget(state,steps,cost_rub,path): _append_event(state,"BUDGET_SPENT","controller",{"steps":steps,"cost_rub":cost_rub},state["attempts"][-1]["attempt_id"] if state["attempts"] else None); save_state(state,path); return state["cycle"]["state"]
def auditor_block(state,path): _append_event(state,"MANUAL_BLOCK","controller",{"reason":"auditor_block"},state["attempts"][-1]["attempt_id"] if state["attempts"] else None); save_state(state,path); return state["cycle"]["state"]
def finalize(state,path):
    if state["cycle"]["state"]!="PASSED": raise ValueError(f"finalize: expected PASSED, got {state['cycle']['state']}")
    _append_event(state,"TASK_FINALIZED","controller",{}); save_state(state,path); return state["cycle"]["state"]

def validate(state):
    errors=[]
    if state.get("_meta",{}).get("version")!=3: errors.append("unsupported state version")
    errors.extend(verify_event_chain(state.get("events",[])))
    try:
        p=reduce_events(state.get("events",[]),load_policy())
        if p["cycle"]["state"] not in STATES: errors.append(f"unknown state: {p['cycle']['state']}")
        errors.extend([f"provenance[{x.get('seq')}]: {x.get('error')}" for x in p.get("provenance_errors",[])])
    except Exception as e: errors.append(f"reducer failure: {e}")
    return errors

def replay(state):
    errors=verify_event_chain(state.get("events",[]))
    if errors: raise ValueError("event log integrity failure: "+"; ".join(errors))
    return reduce_events(state["events"],load_policy())

def resume(state):
    p=replay(state)
    return {"task_id":p["task"].get("task_id"),"state":p["cycle"]["state"],"attempt":p["cycle"]["attempt"],"iteration":p["cycle"]["iteration"],
            "attempt_limit":p["cycle"]["attempt_limit"],"iteration_limit":p["cycle"]["iteration_limit"],"rework_rounds":p["cycle"]["rework_rounds"],
            "stop_reason":p["cycle"]["stop_reason"],
            "required_gates":p["required_gates"],"gate_set":p["gate_set"],"budget_spent_rub":p["budget"]["spent_cost_rub"],"budget_max_rub":p["budget"]["max_cost_rub"],
            "tribunal_required":p["tribunal_required"],
            "event_count":len(state["events"]),"artifact_count":len(p["artifacts"]),"provenance_errors":p["provenance_errors"],
            "gate_policy_hash":p["task"].get("gate_policy_hash"),"provenance_policy_hash":p["task"].get("provenance_policy_hash"),
            "last_event_hash":state["events"][-1]["event_hash"] if state["events"] else None}
