#!/usr/bin/env python3
"""sleep_git.py — git-обёртка цикла сна агента (M6).

Канон: гл.20 (параллельные суб-ветки по кластерам задач из корзины урона),
гл.26 (цикл сна: baseline -> суб-ветки -> merge -> возврат к baseline),
гл.34 (снимок перед крупным изменением; безопасность: ничего чужого
и необратимого не удаляем — только свои sleep-ветки, по маркеру).

Цикл сна (соответствует пользовательскому запросу):
    snapshot (легковесный git tag baseline/<task_id>/<ts> на HEAD ПЕРЕД сном)
    -> create_sleep_branches (fix/<rule_id> от baseline-коммита, маркер-коммит)
    -> execute_branch (колбэк-исполнитель на каждой ветке; failed НЕ удаляется)
    -> merge_branches (в target; конфликт -> abort и продолжение со следующей)
    -> restore_baseline (checkout baseline-tag, удаление СВОИХ sleep-веток по маркеру)

Usage:
    python sleep_git.py snapshot --task <id>
    python sleep_git.py run --task <id> --branches fix/A,fix/B [--exec "cmd"]
                              [--target main] [--keep-failed] [--dry-run]
    python sleep_git.py restore --task <id> [--keep-failed] [--dry-run]

API:
    SleepGit(repo_root=None, dry_run=False, target="main")
    sg.snapshot_baseline(task_id)           -> {tag, commit}
    sg.create_sleep_branches(plan_branches, task_id) -> [{branch, created}]
    sg.execute_branch(branch, executor_fn)  -> {branch, status: ok|failed}
    sg.merge_branches(branches, target="main") -> [{branch, status: ok|conflict}]
    sg.restore_baseline(task_id)            -> {restored_to}
    sg.report()                             -> {baseline, branches, merged, restored}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKERS_REL = Path(".runs") / "sleep_markers"  # маркеры коммитятся в sleep-ветки
STATE_REL = Path(".runs") / "sleep_state"      # служебное состояние цикла (не коммитится)


class GitSleepError(RuntimeError):
    """Ошибка git-операции цикла сна."""


def _now_ts() -> str:
    """Уникальная метка времени для тегов baseline (микросекунды против коллизий)."""
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _safe_token(rule_id: str) -> str:
    """rule_id -> безопасный токен для имени файла-маркера."""
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in rule_id)


class SleepGit:
    """Детерминированная git-обёртка цикла сна. Все мутации — через git CLI.

    dry_run=True: мутирующие команды печатаются и НЕ выполняются; read-only
    команды (rev-parse, ls-tree, tag --list) выполняются по-настоящему.
    """

    def __init__(self, repo_root: Optional[str] = None,
                 dry_run: bool = False, target: str = "main") -> None:
        self.repo = Path(repo_root).resolve() if repo_root else REPO_ROOT
        self.dry_run = dry_run
        self.target = target
        self.state: Dict[str, Any] = {"baseline": None, "branches": [],
                                      "executed": [], "merged": [], "restored": None}

    # ------------------------------------------------------------ git helpers
    def _git(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Мутирующая git-команда. В dry_run — симулируется (печать, rc=0)."""
        cmd = ["git", "-C", str(self.repo)] + list(args)
        if self.dry_run:
            print("[dry-run]", " ".join(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              errors="replace", check=False)
        if check and proc.returncode != 0:
            raise GitSleepError(
                f"git {' '.join(args)} failed (rc={proc.returncode}): "
                f"{proc.stderr.strip()}")
        return proc

    def _git_ro(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Read-only git-команда — выполняется даже в dry_run."""
        cmd = ["git", "-C", str(self.repo)] + list(args)
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              errors="replace", check=False)
        if check and proc.returncode != 0:
            raise GitSleepError(
                f"git {' '.join(args)} failed (rc={proc.returncode}): "
                f"{proc.stderr.strip()}")
        return proc

    # ------------------------------------------------------------ state files
    def _state_path(self, task_id: str) -> Path:
        return self.repo / STATE_REL / f"{task_id}.json"

    def _save_state(self, task_id: str) -> None:
        if self.dry_run:
            return
        p = self._state_path(task_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.state, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    def _load_state(self, task_id: str) -> Dict[str, Any]:
        p = self._state_path(task_id)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    # ------------------------------------------------------------ 1. snapshot
    def snapshot_baseline(self, task_id: str) -> Dict[str, str]:
        """Легковесный tag baseline/<task_id>/<ts> на текущем HEAD (ПЕРЕД сном).

        Канон гл.34: снимок перед крупным изменением. Ничего не коммитит,
        не трогает рабочую копию — только создаёт tag.
        """
        tag = f"baseline/{task_id}/{_now_ts()}"
        commit = self._git_ro(["rev-parse", "HEAD"]).stdout.strip()
        self._git(["tag", tag])  # lightweight (без -a/-m)
        self.state["baseline"] = {"tag": tag, "commit": commit}
        self._save_state(task_id)
        return {"tag": tag, "commit": commit}

    # ------------------------------------------------------------ 2. branches
    def create_sleep_branches(self, plan_branches: List[str],
                              task_id: str) -> List[Dict[str, Any]]:
        """Суб-ветки fix/<rule_id> от baseline-коммита + маркер-коммит.

        На каждой ветке коммитится ПУСТОЙ файл-маркер
        .runs/sleep_markers/<task_id>/<rule_id> (commit message sleep/<task_id>/<rule_id>).
        Маркер — единственный способ отличить СВОИ sleep-ветки от чужих fix/*.
        Существующая ветка не пересоздаётся (created=False).
        """
        base = (self.state.get("baseline") or {}).get("commit")
        if not base:
            raise GitSleepError(
                f"create_sleep_branches: нет baseline — сначала snapshot_baseline('{task_id}')")
        markers_dir = self.repo / MARKERS_REL / task_id
        result: List[Dict[str, Any]] = []
        for name in plan_branches:
            branch = name if name.startswith("fix/") else f"fix/{name}"
            exists = self._git_ro(["rev-parse", "--verify", branch],
                                  check=False).returncode == 0
            if exists:
                print(f"[sleep_git] ветка {branch} уже существует — пропуск")
                result.append({"branch": branch, "created": False})
                continue
            rule = branch[len("fix/"):]
            marker = markers_dir / _safe_token(rule)
            self._git(["checkout", "-b", branch, base])
            if not self.dry_run:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("", encoding="utf-8")  # пустой файл-маркер
            self._git(["add", "--", str(marker.relative_to(self.repo))])
            self._git(["commit", "-m", f"sleep/{task_id}/{rule}"])
            result.append({"branch": branch, "created": True})
        self.state["branches"] = [r["branch"] for r in result if r["created"]]
        self._save_state(task_id)
        # не оставляем рабочую копию на последней ветке — возврат на baseline
        self._git(["checkout", self.state["baseline"]["tag"]])
        return result

    # ------------------------------------------------------------ 3. execute
    def execute_branch(self, branch: str,
                       executor_fn: Callable[[str], Optional[Dict[str, Any]]]
                       ) -> Dict[str, str]:
        """Выполнить фикс на ветке через колбэк executor_fn(branch).

        - колбэк делает фикс (и коммитит его сам — это его ответственность);
        - возвращает dict -> ok; None/исключение -> failed;
        - failed ветка НЕ удаляется, только помечается (канон: не терять работу).
        """
        self._git(["checkout", branch])
        try:
            result = executor_fn(branch)
            status = "ok" if result is not None else "failed"
        except Exception as exc:  # noqa: BLE001 — executor сбой не роняет цикл
            print(f"[sleep_git] executor failed on {branch}: {exc}")
            status = "failed"
        entry = {"branch": branch, "status": status}
        self.state["executed"] = [e for e in self.state.get("executed", [])
                                  if e["branch"] != branch] + [entry]
        return entry

    # ------------------------------------------------------------ 4. merge
    def _resolve_target(self, target: str) -> str:
        """target по умолчанию 'main'; если ветки нет — текущая ветка HEAD."""
        if self._git_ro(["rev-parse", "--verify", f"refs/heads/{target}"],
                        check=False).returncode == 0:
            return target
        cur = self._git_ro(["symbolic-ref", "--short", "HEAD"],
                           check=False).stdout.strip()
        if cur:
            print(f"[sleep_git] ветка '{target}' не найдена — использую текущую '{cur}'")
            return cur
        raise GitSleepError(f"целевая ветка '{target}' не существует и HEAD detached")

    def merge_branches(self, branches: List[str], target: Optional[str] = None
                       ) -> List[Dict[str, str]]:
        """Последовательный merge веток в target.

        Конфликт НЕ блокирует: merge --abort, статус conflict, переход к
        следующей ветке (канон гл.26 — возврат к baseline всё равно выполняется).
        """
        target = self._resolve_target(target or self.target)
        results: List[Dict[str, str]] = []
        for branch in branches:
            self._git(["checkout", target])
            proc = self._git(["merge", "--no-ff", "--no-edit", branch], check=False)
            if proc.returncode == 0:
                results.append({"branch": branch, "status": "ok"})
            else:
                print(f"[sleep_git] конфликт при merge {branch} -> {target}; abort")
                self._git(["merge", "--abort"], check=False)
                results.append({"branch": branch, "status": "conflict"})
        self.state["merged"] = results
        return results

    # ------------------------------------------------------------ 5. restore
    def _find_own_sleep_branches(self, task_id: str,
                                 state: Optional[Dict[str, Any]] = None
                                 ) -> List[str]:
        """Свои sleep-ветки: из state-файла, иначе скан fix/* по маркеру.

        Маркер-скан: ветка наша, если в ней есть файл
        .runs/sleep_markers/<task_id>/* (git ls-tree).
        """
        branches = (state or {}).get("branches")
        if branches:
            return [b for b in branches if b.startswith("fix/")]
        found: List[str] = []
        refs = self._git_ro(
            ["for-each-ref", "--format=%(refname:short)", "refs/heads/fix/"],
            check=False).stdout.splitlines()
        for ref in refs:
            branch = ref.strip()
            if not branch:
                continue
            out = self._git_ro(
                ["ls-tree", "-r", "--name-only", branch, "--",
                 str(MARKERS_REL / task_id)],
                check=False).stdout.strip()
            if out:
                found.append(branch)
        return found

    def restore_baseline(self, task_id: str, keep_failed: bool = False
                         ) -> Dict[str, str]:
        """Возврат к baseline: checkout tag + удаление СВОИХ sleep-веток.

        Удаляются ТОЛЬКО ветки, созданные этим сном (по маркеру/state).
        keep_failed=True — failed-ветки не удаляются (сохранить для разбора).
        """
        state = self.state if self.state.get("baseline") else (self._load_state(task_id) or {})
        tag = (state.get("baseline") or {}).get("tag")
        if not tag:
            tags = [t for t in self._git_ro(
                ["tag", "--list", f"baseline/{task_id}/*"]).stdout.split()
                if t.startswith(f"baseline/{task_id}/")]
            if tags:
                tag = sorted(tags)[-1]
        if not tag:
            raise GitSleepError(f"restore: нет baseline-тега для задачи '{task_id}'")
        self._git(["checkout", tag])
        own = self._find_own_sleep_branches(task_id, state)
        if keep_failed:
            failed = {e["branch"] for e in state.get("executed", [])
                      if e["status"] == "failed"}
            own = [b for b in own if b not in failed]
        for branch in own:
            print(f"[sleep_git] удаляю sleep-ветку {branch} (по маркеру)")
            # идемпотентно: ветка может быть уже удалена предыдущим run (branch -D на отсутствующей = rc!=0)
            self._git(["branch", "-D", branch], check=False)
        self.state["restored"] = tag
        self._save_state(task_id)
        return {"restored_to": tag}

    # ------------------------------------------------------------ 6. report
    def report(self) -> Dict[str, Any]:
        """Итог цикла: {baseline, branches:[{name,status}], merged, restored}."""
        status_map = {}
        for e in self.state.get("executed", []):
            status_map[e["branch"]] = e["status"]
        for m in self.state.get("merged", []):
            if m["status"] == "ok":
                status_map[m["branch"]] = "merged"
        branches = [{"name": b, "status": status_map.get(b, "created")}
                    for b in self.state.get("branches", [])]
        return {
            "baseline": self.state.get("baseline"),
            "branches": branches,
            "merged": [m["branch"] for m in self.state.get("merged", [])
                       if m["status"] == "ok"],
            "restored": self.state.get("restored"),
        }


# ==================================================================== CLI
def _run_exec(cmd: str, branch: str, sg: SleepGit) -> Optional[Dict[str, Any]]:
    """Исполнитель для CLI --exec: shell-команда на checkout-нутой ветке.

    Команда сама должна внести изменения и закоммитить их (ответственность
    исполнителя). Ненулевой rc -> None -> ветка failed (не удаляется).
    """
    print(f"[sleep_git] exec на {branch}: {cmd}")
    if sg.dry_run:
        return {"exec": cmd}
    proc = subprocess.run(cmd, shell=True, cwd=str(sg.repo),
                          text=True, errors="replace")
    return {"exec": cmd, "rc": proc.returncode} if proc.returncode == 0 else None


def _ensure_clean(sg: SleepGit) -> None:
    if sg.dry_run:
        return
    # служебные пути цикла сна (.runs/sleep_state, .runs/sleep_markers, .runs/session_deltas)
    # НЕ считаются грязной рабочей копией — иначе повторный run блокируется своим же состоянием.
    ignore = (str(STATE_REL), str(MARKERS_REL))
    dirty_lines = [
        ln for ln in sg._git_ro(["status", "--porcelain"]).stdout.splitlines()
        if not any(ig in ln for ig in ignore)
    ]
    if dirty_lines:
        raise GitSleepError(
            "рабочая копия не чистая — закоммитьте/спрячьте изменения "
            "перед циклом сна (snapshot должен быть точкой старта)")


def _cmd_snapshot(args: argparse.Namespace) -> int:
    sg = SleepGit(repo_root=args.repo, dry_run=args.dry_run)
    result = sg.snapshot_baseline(args.task)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.branches:
        raise SystemExit("run: требуется --branches fix/A,fix/B [,fix/C...]")
    sg = SleepGit(repo_root=args.repo, dry_run=args.dry_run, target=args.target)
    _ensure_clean(sg)
    sg.snapshot_baseline(args.task)  # гл.34: снапшот ОБЯЗАТЕЛЕН перед сном
    plan = [b.strip() for b in args.branches.split(",") if b.strip()]
    created = sg.create_sleep_branches(plan, args.task)
    if args.exec:
        exec_fn: Callable[[str], Optional[Dict[str, Any]]] = lambda b: _run_exec(args.exec, b, sg)
    else:  # noop-исполнитель: ничего не делает -> ветка ok (только маркер)
        exec_fn = lambda b: {}
    executed = [sg.execute_branch(c["branch"], exec_fn) for c in created if c["created"]]
    ok_branches = [e["branch"] for e in executed if e["status"] == "ok"]
    sg.merge_branches(ok_branches, target=args.target) if ok_branches else None
    sg.restore_baseline(args.task, keep_failed=args.keep_failed)
    print(json.dumps(sg.report(), ensure_ascii=False, indent=2))
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    sg = SleepGit(repo_root=args.repo, dry_run=args.dry_run)
    restored = sg.restore_baseline(args.task, keep_failed=args.keep_failed)
    state = sg._load_state(args.task)
    sg.state.update(state)
    print(json.dumps({"restored_to": restored["restored_to"],
                      "report": sg.report()}, ensure_ascii=False, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sleep_git.py",
        description="git-обёртка цикла сна агента (M6): snapshot -> суб-ветки -> "
                    "execute -> merge -> restore")
    parser.add_argument("--repo", default=None,
                        help="путь к git-репо (по умолчанию корень portable)")
    parser.add_argument("--dry-run", action="store_true",
                        help="печатать мутирующие git-команды, не выполнять")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="tag baseline/<task>/<ts> на HEAD")
    p_snap.add_argument("--task", required=True)
    p_snap.set_defaults(fn=_cmd_snapshot)

    p_run = sub.add_parser("run", help="полный цикл сна")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--branches", required=True,
                       help="запятые: fix/A,fix/B")
    p_run.add_argument("--exec", default=None,
                       help="shell-команда исполнителя (noop без неё)")
    p_run.add_argument("--target", default="main",
                       help="ветка для merge (по умолчанию main)")
    p_run.add_argument("--keep-failed", action="store_true",
                       help="не удалять failed-ветки при restore")
    p_run.set_defaults(fn=_cmd_run)

    p_rest = sub.add_parser("restore", help="возврат к baseline + очистка")
    p_rest.add_argument("--task", required=True)
    p_rest.add_argument("--keep-failed", action="store_true")
    p_rest.set_defaults(fn=_cmd_restore)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())