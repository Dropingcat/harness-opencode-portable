# -*- coding: utf-8 -*-
"""sleep_integration.py — M11: интеграция M5-M10 в полный цикл сна meta_daemon.

Полный цикл сна (обёртка НАД meta_daemon — сам meta_daemon.py НЕ меняется):

    M7  register_task + open_sleep (суб-трекеры веток)
    M6  snapshot_baseline -> create_sleep_branches -> execute_branch
        (в каждой ветке: M10.perfectionist_review после фикса -> M7.checkpoint)
        -> merge_branches -> restore_baseline
    M7  mark_branch (merged/failed) + close_sleep
    M9  recover_hp(hp, sleep_success)
    M10 skill_upgrade_proposal(usage_stats) + write_contract_suggestion
    M5  git_session_sync.sync (подхват текстовых изменений сессий во время сна) + audit
    M8  [опционально, --monte-carlo] прогноз цикла сна на сетке сценариев

Канон:
  гл.28 — 6 отказов автономного режима (autonomy_guard);
  гл.29 — проверка живости демона: «молчание должно быть событием» (liveness_check).

Scope out:
  - meta_daemon.py / damage_basket.py / sleep_planner.py НЕ меняются;
  - в тестовом режиме реальный git не вызывается: если модуль M5-M10 недоступен
    в текущем checkout — lazy-импорт + fallback-имитация с пометкой simulated: true.

API:
    run_sleep_cycle(task_id, branches, baseline=True, hp=100.0, ...) -> dict
    liveness_check(state_dir=None, max_silence_minutes=30, orchestrator="research") -> dict
    autonomy_guard(events) -> list

CLI:
    python sleep_integration.py cycle --task <id> --branches fix/A,fix/B [--hp 80] [--usage '{"x":3}']
    python sleep_integration.py liveness [--state-dir <dir>] [--max-silence 30]
    python sleep_integration.py guard --events '[{"tool":"arxiv_search","repeat":3}]'
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
_META_DIR = REPO_ROOT / "scripts" / "meta"
_TOOLS_DIR = REPO_ROOT / "scripts" / "tools"
_ORCH_DIR = REPO_ROOT / "scripts" / "orchestration"
DEFAULT_STATE_DIR = REPO_ROOT / ".meta_state"

# Канон гл.28: хождение по кругу = повтор одного tool-вызова без прогресса.
CIRCLE_REPEAT_THRESHOLD = 3
# Канон гл.28: тихое упрощение = запрещённые приёмы в тексте/методе.
FORBIDDEN_SHORTCUTS = (
    "hack", "workaround", "костыль", "заглушка", "опустим", "упростим",
    "не будем проверять", "временно", "отложим", "пропустим проверку",
)
# Канон гл.12 (M10): «3 раза в сессию -> кандидат в навык».
SKILL_MIN_COUNT = 3

# Канонический порядок 6 отказов автономного режима (детерминированный вывод).
_AUTONOMY_FAILURES = (
    ("false_ready", "ложная готовность", "critical"),
    ("silent_simplification", "тихое упрощение", "critical"),
    ("circle", "хождение по кругу", "major"),
    ("scope_creep", "расползание", "critical"),
    ("silent_error", "молчаливая ошибка", "major"),
    ("budget_exhausted", "исчерпание бюджета", "critical"),
)


# --------------------------------------------------------------------------
# Утилиты
# --------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> Optional[datetime]:
    """ISO-строка -> datetime (UTC). 'Z' нормализуется в '+00:00'.

    W7 TD-DEV-22: naive datetime (tzinfo=None) интерпретируется как UTC —
    иначе сравнение с aware `now` в liveness_check падает TypeError
    ("can't subtract offset-naive and offset-aware datetimes"). Aware — как есть.
    """
    try:
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, AttributeError):
        return None


def _load_module(name: str, search_dirs: List[Path], simulate: bool = False):
    """Lazy-импорт модуля M5-M10. Если недоступен в checkout (или simulate) — None.

    Модули живут на отдельных ветках, которых может не быть в текущем
    checkout; импорт не должен ронять интеграцию.
    """
    if simulate:
        return None
    for d in search_dirs:
        d = Path(d)
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001 — недоступность модуля = fallback, не ошибка
        return None


# --------------------------------------------------------------------------
# Fallback-имитации M5-M10 (интерфейс повторяет реальные модули 1:1)
# --------------------------------------------------------------------------
class _FallbackBaselineTracker:
    """Имитация M7 baseline_tracker (в памяти, без файлов/прогресса)."""

    def __init__(self) -> None:
        self.tasks: Dict[str, dict] = {}

    def register_task(self, task_id: str, agent: str, dispatcher: str) -> dict:
        t = self.tasks.get(task_id)
        if t is None:
            t = {"task_id": task_id, "agent": agent, "dispatcher": dispatcher,
                 "baseline_commit": "<simulated>", "baseline_ts": _now_iso(),
                 "status": "active", "sub_trackers": []}
            self.tasks[task_id] = t
        return t

    def open_sleep(self, task_id: str, branches: List[str]) -> list:
        t = self.tasks[task_id]
        for b in branches:
            if not any(st["branch"] == b for st in t["sub_trackers"]):
                t["sub_trackers"].append({"branch": b, "baseline": "<simulated>",
                                          "checkpoints": [], "status": "pending",
                                          "agent_pid": None})
        t["status"] = "sleeping"
        return list(t["sub_trackers"])

    def checkpoint(self, task_id: str, branch: str, description: str) -> dict:
        t = self.tasks[task_id]
        st = next((x for x in t["sub_trackers"] if x["branch"] == branch), None)
        if st is None:
            raise ValueError(f"ветка '{branch}' не найдена в задаче '{task_id}'")
        entry = {"description": description, "ts": _now_iso(), "commit": "<simulated>"}
        st["checkpoints"].append(entry)
        return entry

    def mark_branch(self, task_id: str, branch: str, status: str) -> dict:
        t = self.tasks[task_id]
        st = next((x for x in t["sub_trackers"] if x["branch"] == branch), None)
        if st is None:
            raise ValueError(f"ветка '{branch}' не найдена в задаче '{task_id}'")
        st["status"] = status
        return st

    def close_sleep(self, task_id: str, merged_branches: Optional[list] = None) -> dict:
        t = self.tasks[task_id]
        if merged_branches:
            for b in merged_branches:
                st = next((x for x in t["sub_trackers"] if x["branch"] == b), None)
                if st is not None:
                    st["status"] = "merged"
        sts = [st.get("status") for st in t.get("sub_trackers", [])]
        if sts and all(s == "merged" for s in sts):
            t["status"] = "done"
        return t


class _FallbackSleepGit:
    """Имитация M6 SleepGit (без реального git, всё в памяти)."""

    def __init__(self, repo_root=None, dry_run: bool = False, target: str = "main") -> None:
        self.repo = Path(repo_root) if repo_root else REPO_ROOT
        self.dry_run = dry_run
        self.target = target
        self.state: Dict[str, Any] = {"baseline": None, "branches": [],
                                      "executed": [], "merged": [], "restored": None}

    def snapshot_baseline(self, task_id: str) -> dict:
        tag = f"baseline/{task_id}/sim-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.state["baseline"] = {"tag": tag, "commit": "<simulated>"}
        return self.state["baseline"]

    def create_sleep_branches(self, plan_branches: List[str], task_id: str) -> list:
        result = []
        for name in plan_branches:
            branch = name if name.startswith("fix/") else f"fix/{name}"
            result.append({"branch": branch, "created": True})
        self.state["branches"] = [r["branch"] for r in result]
        return result

    def execute_branch(self, branch: str, executor_fn) -> dict:
        try:
            result = executor_fn(branch)
            status = "ok" if result is not None else "failed"
        except Exception:  # noqa: BLE001 — executor не роняет цикл
            status = "failed"
        entry = {"branch": branch, "status": status}
        self.state["executed"] = [e for e in self.state.get("executed", [])
                                  if e["branch"] != branch] + [entry]
        return entry

    def merge_branches(self, branches: List[str], target: Optional[str] = None) -> list:
        results = [{"branch": b, "status": "ok"} for b in branches]
        self.state["merged"] = results
        return results

    def restore_baseline(self, task_id: str, keep_failed: bool = False) -> dict:
        tag = (self.state.get("baseline") or {}).get("tag") or f"baseline/{task_id}/sim"
        self.state["restored"] = tag
        return {"restored_to": tag}

    def report(self) -> dict:
        status_map = {}
        for e in self.state.get("executed", []):
            status_map[e["branch"]] = e["status"]
        for m in self.state.get("merged", []):
            if m["status"] == "ok":
                status_map[m["branch"]] = "merged"
        branches = [{"name": b, "status": status_map.get(b, "created")}
                    for b in self.state.get("branches", [])]
        return {"baseline": self.state.get("baseline"), "branches": branches,
                "merged": [m["branch"] for m in self.state.get("merged", [])
                           if m["status"] == "ok"],
                "restored": self.state.get("restored")}


def _fallback_recover_hp(hp: float, sleep_success: bool) -> float:
    """Имитация M9 recover_hp: +15 при успешном сне, -20 при провале (0..100)."""
    hp = max(0.0, min(100.0, float(hp)))
    if sleep_success:
        return min(100.0, hp + 15.0)
    return max(0.0, hp - 20.0)


class _FallbackEnhancers:
    """Имитация M10 sleep_enhancers (детерминированные аналоги)."""

    def perfectionist_review(self, branch: str, artifact_path: str) -> dict:
        path = Path(artifact_path or "")
        return {"branch": branch, "artifact": str(path),
                "findings": [], "cleanup_suggested": False}

    def skill_upgrade_proposal(self, usage_stats: Dict[str, int]) -> dict:
        candidates = []
        for name, count in sorted((usage_stats or {}).items(),
                                  key=lambda kv: -int(kv[1])):
            try:
                cnt = int(count)
            except (TypeError, ValueError):
                cnt = 0
            if cnt >= SKILL_MIN_COUNT:
                candidates.append({
                    "name": name, "count": cnt,
                    "reason": f"использован {cnt} раз (порог {SKILL_MIN_COUNT}): кандидат в навык",
                })
        return {"candidates": candidates, "suggestions": []}

    def write_contract_suggestion(self, action: str, evidence: str) -> dict:
        name = action.strip().lower()
        return {"contract": {"name": name,
                             "input_schema": {"type": "object", "required": [],
                                              "properties": {}},
                             "output_schema": {"type": "object", "required": [],
                                               "properties": {}},
                             "guard": "вход валидируется по схеме; выход — "
                                      "детерминированный, без вмешательства LLM."},
                "evidence": evidence}


class _FallbackSessionSync:
    """Имитация M5 git_session_sync: подхват дельт без реального git."""

    def sync(self, session_dir=None, since_minutes: int = 60,
             branch: str = "main", no_commit: bool = True) -> dict:
        return {"status": "simulated", "simulated": True, "new_deltas": 0,
                "results": [], "audit": {"findings": [], "count": 0}}

    def audit_delta(self, delta_path) -> dict:
        return {"findings": [], "count": 0}


# --------------------------------------------------------------------------
# run_sleep_cycle — полный цикл сна M5-M10
# --------------------------------------------------------------------------
def _branch_executor(branch: str, bt, enh, task_id: str,
                     artifact_path: Optional[str],
                     perf_findings: List[dict]) -> dict:
    """Исполнитель ветки M6.execute_branch: после фикса — perfectionist-ревью
    (M10) + чекпоинт (M7). Фикс вносит спец-агент; здесь инспекция результата.
    """
    perf = enh.perfectionist_review(branch, artifact_path or "")
    perf_findings.append({"branch": branch, **perf})
    bt.checkpoint(
        task_id, branch,
        f"perfectionist: {len(perf['findings'])} findings, "
        f"cleanup_suggested={perf['cleanup_suggested']}")
    return {"branch": branch, "reviewed": True, "findings": len(perf["findings"])}


def run_sleep_cycle(task_id: str, branches: List[str], baseline: bool = True,
                    hp: float = 100.0, usage_stats: Optional[Dict[str, int]] = None,
                    orchestrator: str = "research",
                    artifact_path: Optional[str] = None,
                    no_git: bool = False, session_dir: Optional[str] = None,
                    since_minutes: int = 60, run_monte_carlo: bool = False,
                    simulate: bool = False) -> dict:
    """Полный цикл сна M5-M10. Возвращает JSON-отчёт.

    baseline=False — пропускает M7-трекер (register/open_sleep/close_sleep),
    M6-цикл (snapshot/merge/restore) выполняется всегда.
    """
    branches = [b.strip() for b in branches if b and b.strip()]
    steps: List[dict] = []
    perf_findings: List[dict] = []

    # --- lazy-подключение M5-M10 (fallback при недоступности в checkout) ---
    mods = {
        "M7": _load_module("baseline_tracker", [_ORCH_DIR], simulate),
        "M6": _load_module("sleep_git", [_TOOLS_DIR], simulate),
        "M9": _load_module("hp_regulator", [_TOOLS_DIR], simulate),
        "M10": _load_module("sleep_enhancers", [_TOOLS_DIR], simulate),
        "M5": _load_module("git_session_sync", [_TOOLS_DIR], simulate),
        "M8": _load_module("monte_carlo_sleep", [_TOOLS_DIR], simulate),
    }
    simulated_any = any(m is None for m in mods.values())

    bt = mods["M7"].register_task if mods["M7"] else _FallbackBaselineTracker()
    if mods["M7"]:
        bt = mods["M7"]
    if not mods["M6"]:
        sg = _FallbackSleepGit(repo_root=str(REPO_ROOT))
    else:
        sg = mods["M6"].SleepGit(repo_root=str(REPO_ROOT), dry_run=False)
    hp_reg = mods["M9"] if mods["M9"] else None
    enh = mods["M10"] if mods["M10"] else _FallbackEnhancers()
    ss = mods["M5"] if mods["M5"] else _FallbackSessionSync()

    # --- 1. M7: register_task + open_sleep (суб-трекеры веток) --------------
    tracker_reg = None
    if baseline:
        tracker_reg = bt.register_task(task_id, agent="sleep", dispatcher="meta_daemon")
        bt.open_sleep(task_id, branches)
        steps.append({"step": "m7_register_open", "module": "M7",
                      "simulated": mods["M7"] is None, "ok": True,
                      "task_id": task_id, "branches": len(branches)})

    # --- 2. M6: полный git-цикл сна ----------------------------------------
    if mods["M6"]:
        sg.snapshot_baseline(task_id)
    else:
        sg.snapshot_baseline(task_id)
    created = sg.create_sleep_branches(branches, task_id)
    steps.append({"step": "m6_snapshot_branches", "module": "M6",
                  "simulated": mods["M6"] is None, "ok": True,
                  "branches": [c["branch"] for c in created]})

    executed: List[dict] = []
    for c in created:
        if not c.get("created"):
            continue
        res = sg.execute_branch(c["branch"], lambda b, _c=c: _branch_executor(
            b, bt, enh, task_id, artifact_path, perf_findings))
        executed.append(res)

    ok_branches = [e["branch"] for e in executed if e["status"] == "ok"]
    merged = sg.merge_branches(ok_branches, target="main") if ok_branches else []
    merged_ok = [m["branch"] for m in merged if m["status"] == "ok"]
    try:
        restored = sg.restore_baseline(task_id, keep_failed=True)
    except Exception as exc:  # noqa: BLE001 — restore не блокирует отчёт
        restored = {"restored_to": None, "error": str(exc)}
    report = sg.report()
    steps.append({"step": "m6_merge_restore", "module": "M6",
                  "simulated": mods["M6"] is None, "ok": True,
                  "merged": merged_ok, "restored": restored.get("restored_to")})

    # --- 3. M7: mark_branch + close_sleep ------------------------------------
    if baseline:
        for e in executed:
            status = "merged" if e["branch"] in merged_ok else "failed"
            try:
                bt.mark_branch(task_id, e["branch"], status)
            except Exception as exc:  # noqa: BLE001
                steps.append({"step": "m7_mark_error", "module": "M7",
                              "simulated": mods["M7"] is None, "ok": False,
                              "branch": e["branch"], "error": str(exc)})
        final_task = bt.close_sleep(task_id, merged_ok)
        steps.append({"step": "m7_mark_close", "module": "M7",
                      "simulated": mods["M7"] is None, "ok": True,
                      "task_status": final_task.get("status")})

    # --- 4. M9: recover_hp(hp, sleep_success) --------------------------------
    created_ok = len([c for c in created if c.get("created")])
    sleep_success = created_ok > 0 and len(merged_ok) == created_ok
    if hp_reg is not None:
        hp_after = float(hp_reg.recover_hp(float(hp), sleep_success))
    else:
        hp_after = _fallback_recover_hp(float(hp), sleep_success)
    steps.append({"step": "m9_recover_hp", "module": "M9",
                  "simulated": hp_reg is None, "ok": True,
                  "hp_before": float(hp), "hp_after": hp_after,
                  "sleep_success": sleep_success})

    # --- 5. M10: skill_upgrade_proposal + write_contract_suggestion ---------
    stats = usage_stats or {}
    proposal = enh.skill_upgrade_proposal(stats)
    skill_candidates: List[dict] = []
    for cand in proposal.get("candidates", []):
        contract = enh.write_contract_suggestion(
            cand["name"], f"{cand['count']} раз в сессию (порог {SKILL_MIN_COUNT})")
        skill_candidates.append({"name": cand["name"], "count": cand["count"],
                                 "reason": cand["reason"],
                                 "contract": contract["contract"]})
    steps.append({"step": "m10_skills", "module": "M10",
                  "simulated": mods["M10"] is None, "ok": True,
                  "candidates": len(skill_candidates)})

    # --- 6. M5: git_session_sync.sync + audit ---------------------------------
    if mods["M5"]:
        try:
            deltas = ss.collect_text_deltas(session_dir, since_minutes)
            results = []
            for d in deltas:
                payload = dict(d)
                payload["no_commit"] = no_git
                res = ss.commit_delta(payload, branch="main")
                audit = (ss.audit_delta(res["delta_path"])
                         if res.get("delta_path") else {"findings": [], "count": 0})
                results.append({"session_id": d["session_id"],
                                "delta_path": res.get("delta_path"),
                                "committed": res.get("committed", False),
                                "audit": audit})
            session_sync = {"new_deltas": len(deltas), "results": results,
                            "simulated": False}
        except Exception as exc:  # noqa: BLE001
            session_sync = {"new_deltas": 0, "results": [], "simulated": True,
                            "error": str(exc)}
    else:
        session_sync = ss.sync(session_dir=session_dir, since_minutes=since_minutes,
                               no_commit=no_git)
    steps.append({"step": "m5_session_sync", "module": "M5",
                  "simulated": mods["M5"] is None, "ok": True,
                  "new_deltas": session_sync.get("new_deltas", 0)})

    # --- 7. [опц.] M8: Monte-Carlo прогноз в связке ---------------------------
    monte_carlo: Dict[str, Any] = {"status": "skipped"}
    if run_monte_carlo:
        if mods["M8"]:
            try:
                selected = mods["M8"].scenarios()[:12]
                results = [mods["M8"].run_scenario(sc, None) for sc in selected]
                stats_mc = mods["M8"].aggregate(results)
                monte_carlo = {"status": "run", "scenarios": len(results),
                               "success_rate": stats_mc.get("success_rate"),
                               "std": stats_mc.get("std"),
                               "verdict": stats_mc.get("verdict")}
            except Exception as exc:  # noqa: BLE001
                monte_carlo = {"status": "error", "simulated": True,
                               "error": str(exc)}
        else:
            monte_carlo = {"status": "simulated", "simulated": True,
                           "note": "модуль M8 недоступен в checkout"}
        steps.append({"step": "m8_monte_carlo", "module": "M8",
                      "simulated": mods["M8"] is None, "ok": True,
                      "status": monte_carlo.get("status")})

    # --- отчёт -----------------------------------------------------------------
    return {
        "task_id": task_id,
        "baseline": (tracker_reg or {}).get("baseline_commit") if baseline else None,
        "branches": report.get("branches", []),
        "merged": merged_ok,
        "hp_after": round(hp_after, 2),
        "sleep_success": sleep_success,
        "perfectionist_findings": perf_findings,
        "skill_candidates": skill_candidates,
        "session_sync": session_sync,
        "monte_carlo": monte_carlo,
        "steps": steps,
        "simulated": simulated_any,
        "ts": _now_iso(),
    }


# --------------------------------------------------------------------------
# liveness_check — проверка живости демона (канон гл.29)
# --------------------------------------------------------------------------
def liveness_check(state_dir: Optional[str] = None,
                   max_silence_minutes: int = 30,
                   orchestrator: str = "research") -> dict:
    """«Молчание должно быть событием»: демон жив, пока последний аудит свежий.

    Читает timestamp последнего аудита из
    `<state_dir>/<orchestrator>_meta_state.json` (поле `saved_at`,
    пишется OrchestratorIntegration._save_state). Если тишина дольше
    max_silence_minutes — демон считается мёртвым/спящим.
    """
    state_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
    state_file = state_dir / f"{orchestrator}_meta_state.json"
    now = datetime.now(timezone.utc)

    if not state_file.exists():
        return {"alive": False, "reason": "no_state_file",
                "state_file": str(state_file), "orchestrator": orchestrator,
                "silent_minutes": None, "max_silence_minutes": max_silence_minutes,
                "checked_at": now.isoformat()}

    last_ts: Optional[datetime] = None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        saved = data.get("saved_at")
        if saved:
            last_ts = _parse_iso(saved)
    except (json.JSONDecodeError, OSError):
        last_ts = None
    if last_ts is None:
        # fallback: mtime файла состояния — последний признак активности
        try:
            last_ts = datetime.fromtimestamp(state_file.stat().st_mtime,
                                             tz=timezone.utc)
        except OSError:
            last_ts = now

    silent_min = round((now - last_ts).total_seconds() / 60.0, 1)
    alive = silent_min <= max_silence_minutes
    return {"alive": alive, "silent_minutes": silent_min,
            "max_silence_minutes": max_silence_minutes,
            "last_seen": last_ts.isoformat(),
            "state_file": str(state_file), "orchestrator": orchestrator,
            "checked_at": now.isoformat()}


# --------------------------------------------------------------------------
# autonomy_guard — 6 отказов автономного режима (канон гл.28)
# --------------------------------------------------------------------------
def _txt(value: Any) -> str:
    return value.lower() if isinstance(value, str) else ""


def _detect_false_ready(events: List[Any]) -> List[int]:
    """Отказ 1: ложная готовность — заявлен done, критериев приёмки нет."""
    hits = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        declared = (e.get("declared_done") is True
                    or e.get("status") == "done"
                    or e.get("type") in ("declared_done", "done"))
        criteria = (e.get("acceptance") or e.get("acceptance_criteria")
                    or e.get("criteria"))
        if declared and not criteria:
            hits.append(i)
    return hits


def _detect_silent_simplification(events: List[Any]) -> List[int]:
    """Отказ 2: тихое упрощение — запрещённые приёмы (hack/костыль/заглушка)."""
    hits = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        hit = (e.get("workaround") is True
               or e.get("silent_simplification") is True
               or e.get("type") in ("simplification", "silent_simplification",
                                    "workaround"))
        text = " ".join(str(e.get(k, "")) for k in
                        ("message", "text", "method", "approach", "note"))
        if not hit and any(m in _txt(text) for m in FORBIDDEN_SHORTCUTS):
            hit = True
        if hit:
            hits.append(i)
    return hits


def _detect_circle(events: List[Any]) -> List[int]:
    """Отказ 3: хождение по кругу — повтор одного tool-вызова без прогресса.

    Либо событие с полем repeat >= порога, либо серия одинаковых tool подряд.
    """
    hits = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        tool = e.get("tool")
        repeat = e.get("repeat")
        if tool and isinstance(repeat, int) and repeat >= CIRCLE_REPEAT_THRESHOLD:
            hits.append(i)
    # серия одинаковых tool-вызовов подряд (без других событий между ними)
    for i, e in enumerate(events):
        if not isinstance(e, dict) or not e.get("tool"):
            continue
        tool = e["tool"]
        j = i
        while j < len(events) and isinstance(events[j], dict) \
                and events[j].get("tool") == tool:
            j += 1
        run = j - i
        if run >= CIRCLE_REPEAT_THRESHOLD:
            hits.extend(range(i, j))
    # дедупликация с сохранением порядка
    seen: set = set()
    dedup = []
    for idx in hits:
        if idx not in seen:
            seen.add(idx)
            dedup.append(idx)
    return dedup


def _detect_scope_creep(events: List[Any]) -> List[int]:
    """Отказ 4: расползание — изменения вне заявленного scope."""
    hits = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        if (e.get("out_of_scope") is True
                or e.get("type") in ("out_of_scope", "scope_creep")):
            hits.append(i)
            continue
        scope = e.get("scope")
        changed = e.get("changed") or e.get("files")
        if isinstance(scope, list) and isinstance(changed, list):
            if any(f not in scope for f in changed):
                hits.append(i)
    return hits


def _detect_silent_error(events: List[Any]) -> List[int]:
    """Отказ 5: молчаливая ошибка — пустые except, проглоченные сбои."""
    hits = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        if (e.get("bare_except") is True
                or e.get("silent_error") is True
                or e.get("type") in ("bare_except", "empty_except", "silent_error")):
            hits.append(i)
            continue
        body = e.get("except")
        if isinstance(body, str) and body.strip().lower() in ("pass", ""):
            hits.append(i)
    return hits


def _detect_budget_exhausted(events: List[Any]) -> List[int]:
    """Отказ 6: исчерпание бюджета — расход растёт, прогресса нет."""
    hits = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        if e.get("type") in ("budget_exhausted", "budget"):
            hits.append(i)
            continue
        spent = e.get("spent")
        progress = e.get("progress")
        if spent is not None and progress is not None:
            try:
                spent_f = float(spent)
                prog_f = float(progress)
                limit_f = float(e["budget"]) if e.get("budget") is not None else spent_f
                if spent_f >= limit_f and prog_f <= 0:
                    hits.append(i)
            except (TypeError, ValueError):
                continue
    return hits


def autonomy_guard(events: List[Any]) -> List[dict]:
    """Детерминированно выявляет 6 отказов автономного режима (канон гл.28).

    Принимает список событий (dict). Каждое событие проверяется всеми шестью
    детекторами. Возвращает список failures в каноническом порядке:
        [{id, name, severity, description, events: [индексы событий]}]
    """
    events = list(events) if isinstance(events, list) else []
    detectors = (
        ("false_ready", _detect_false_ready),
        ("silent_simplification", _detect_silent_simplification),
        ("circle", _detect_circle),
        ("scope_creep", _detect_scope_creep),
        ("silent_error", _detect_silent_error),
        ("budget_exhausted", _detect_budget_exhausted),
    )
    failures: List[dict] = []
    for fid, detector in detectors:
        idx = detector(events)
        if not idx:
            continue
        # канонический (id, name, severity) из карты
        name, severity = fid, fid
        for _fid, _name, _sev in _AUTONOMY_FAILURES:
            if _fid == fid:
                name, severity = _name, _sev
                break
        failures.append({"id": fid, "name": name, "severity": severity,
                         "description": _failure_description(fid),
                         "events": idx})
    return failures


def _failure_description(fid: str) -> str:
    """Человекочитаемое описание отказа (канон гл.28)."""
    descriptions = {
        "false_ready": "агент заявил готовность (done), но критерии приёмки "
                       "отсутствуют или пусты",
        "silent_simplification": "использованы запрещённые приёмы "
                                 "(hack/костыль/заглушка/упрощение) вместо "
                                 "честного решения",
        "circle": "повторные вызовы одного и того же tool без прогресса "
                  "(хождение по кругу)",
        "scope_creep": "изменения выходят за пределы заявленного scope",
        "silent_error": "ошибка проглочена пустым except — сбой остался "
                        "незамеченным",
        "budget_exhausted": "бюджет исчерпан, а прогресс отсутствует",
    }
    return descriptions.get(fid, fid)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _parse_stats(raw: Optional[str]) -> Dict[str, int]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--usage не JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("--usage должен быть объектом {action: count}")
    return data


def _cmd_cycle(args: argparse.Namespace) -> int:
    branches = [b.strip() for b in args.branches.split(",") if b.strip()]
    result = run_sleep_cycle(
        task_id=args.task, branches=branches, baseline=not args.no_baseline,
        hp=args.hp, usage_stats=_parse_stats(args.usage),
        orchestrator=args.orchestrator, artifact_path=args.artifact,
        no_git=args.no_git, session_dir=args.session_dir,
        since_minutes=args.since_minutes, run_monte_carlo=args.monte_carlo,
        simulate=args.simulate)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_liveness(args: argparse.Namespace) -> int:
    result = liveness_check(state_dir=args.state_dir,
                            max_silence_minutes=args.max_silence,
                            orchestrator=args.orchestrator)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("alive") else 1


def _cmd_guard(args: argparse.Namespace) -> int:
    try:
        events = json.loads(args.events)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--events не JSON: {exc}") from exc
    if not isinstance(events, list):
        raise SystemExit("--events должен быть списком событий")
    result = autonomy_guard(events)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result else 0


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="sleep_integration.py",
        description="M11: интеграция M5-M10 в полный цикл сна meta_daemon "
                    "(канон гл.28/29).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cycle = sub.add_parser("cycle", help="полный цикл сна M5-M10")
    p_cycle.add_argument("--task", required=True, help="task_id")
    p_cycle.add_argument("--branches", required=True,
                         help="ветки через запятую: fix/A,fix/B")
    p_cycle.add_argument("--hp", type=float, default=100.0, help="HP до сна")
    p_cycle.add_argument("--usage", default=None,
                         help="JSON {'action': count} для M10 skill-upgrade")
    p_cycle.add_argument("--no-baseline", action="store_true",
                         help="пропустить M7-трекер (baseline=False)")
    p_cycle.add_argument("--orchestrator", default="research")
    p_cycle.add_argument("--artifact", default=None,
                         help="путь к файлу для M10.perfectionist_review")
    p_cycle.add_argument("--no-git", action="store_true",
                         help="M5: только записать дельты, без git commit")
    p_cycle.add_argument("--session-dir", default=None,
                         help="каталог ses_*.json для M5")
    p_cycle.add_argument("--since-minutes", type=int, default=60,
                         help="M5: окно свежести сессий")
    p_cycle.add_argument("--monte-carlo", action="store_true",
                         help="добавить M8 Monte-Carlo прогноз в отчёт")
    p_cycle.add_argument("--simulate", action="store_true",
                         help="принудительно имитировать все модули M5-M10")
    p_cycle.set_defaults(fn=_cmd_cycle)

    p_live = sub.add_parser("liveness", help="проверка живости демона (гл.29)")
    p_live.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p_live.add_argument("--max-silence", type=int, default=30,
                        dest="max_silence", help="макс. тишина в минутах")
    p_live.add_argument("--orchestrator", default="research")
    p_live.set_defaults(fn=_cmd_liveness)

    p_guard = sub.add_parser("guard", help="6 отказов автономного режима (гл.28)")
    p_guard.add_argument("--events", required=True,
                         help="JSON-список событий, напр. "
                              "'[{\"tool\":\"arxiv_search\",\"repeat\":3}]'")
    p_guard.set_defaults(fn=_cmd_guard)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())