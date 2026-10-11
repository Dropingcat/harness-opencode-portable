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
    -> merge_branches (false_ready/merge-tree pre-check; конфликт -> keep, НЕ merge)
    -> restore_baseline (checkout baseline-tag, удаление ТОЛЬКО слитых sleep-веток)

W13 (глубокий git-аудит снов, RUD-7): закрыты три критические дыры:
  1. Дыра-1 (CRITICAL): конфликтная ветка при restore УДАЛЯЛАСЬ (branch -D),
     изменения не вливались -> ПОТЕРЯ ДАННЫХ. Теперь ветки класса conflict
     и false_ready ВСЕГДА в keep-множестве (не удаляются, данные целы).
  2. Дыра-2 (CRITICAL): рефлексия отсутствовала. Теперь в отчёт пишутся
     commits[], diffstat, changed_files[] каждой ветки против baseline.
  3. Дыра-3 (CRITICAL): ночной прогон шёл с --simulate (сны не гитированы).
     Интеграция W7: meta_nightly.cmd без --simulate; отчёт сна сохраняется
     в .runs/sleep_reports/<task>.json; уроки конфликтов -> .l2_memory/ и
     .runs/sleep_reports/conflicts_<date>.json.

Детекция конфликтов: git merge-tree --write-tree --name-only <target> <branch>
(сухой pre-check БЕЗ рабочей копии; exit 1 = конфликт, проверен git 2.46).
false_ready: git diff --quiet <baseline>..<branch> (с исключением маркеров) —
ветка без реальных изменений (только маркер-коммит) не готова к merge.

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
    sg.merge_branches(branches, target="main") -> [{branch, status: ok|conflict|false_ready}]
    sg.restore_baseline(task_id)            -> {restored_to}
    sg.report()                             -> отчёт сна (W13-формат, см. ниже)
    sg.write_report(task_id)                -> путь к .runs/sleep_reports/<task>.json

Отчёт сна (W13-формат, валидируется sleep_report_check.py):
    {task, baseline_tag, timestamp, simulated: false,
     branches: [{name, status, commits[], diffstat{files,insertions,deletions},
                 changed_files[]}],
     merged: [branch...],
     conflicts: [{branch, target, files[], reason, kept: true}],
     restored_to, lessons: [{branch, lesson, target: ".l2_memory"}]}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKERS_REL = Path(".runs") / "sleep_markers"  # маркеры коммитятся в sleep-ветки
STATE_REL = Path(".runs") / "sleep_state"      # служебное состояние цикла (не коммитится)
REPORTS_REL = Path(".runs") / "sleep_reports"  # отчёты сна (не коммитятся, .runs/*)
L2_REL = Path(".l2_memory")                    # сессионная память (не коммитится)

# pathspec диффов ветки: маркер-файлы служебные, в «работу» ветки не входят.
_DIFF_PATHS = [".", ":(exclude).runs/sleep_markers/**"]

# Допустимые классы статусов ветки в отчёте (W13-T4 проверка 2).
BRANCH_STATUSES = ("ok", "failed", "conflict", "keep", "false_ready", "merged", "created")

# git diff --shortstat: " 1 file changed, 1 insertion(+), 1 deletion(-)"
_SHORTSTAT_RE = re.compile(
    r"(?P<files>\d+) file[s]? changed(?:, (?P<ins>\d+) insertion[s]?\(\+\))?"
    r"(?:, (?P<del>\d+) deletion[s]?\(-\))?")


class GitSleepError(RuntimeError):
    """Ошибка git-операции цикла сна."""


def _now_ts() -> str:
    """Уникальная метка времени для тегов baseline (микросекунды против коллизий)."""
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_token(rule_id: str) -> str:
    """rule_id -> безопасный токен для имени файла-маркера."""
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in rule_id)


def _parse_shortstat(text: str) -> Dict[str, int]:
    """' 1 file changed, 2 insertions(+), 3 deletions(-)' -> {files, insertions, deletions}.

    Пустой/несовпадающий текст -> нулевой diffstat (детерминированно).
    """
    m = _SHORTSTAT_RE.search(text.strip())
    if not m:
        return {"files": 0, "insertions": 0, "deletions": 0}
    return {
        "files": int(m.group("files")),
        "insertions": int(m.group("ins") or 0),
        "deletions": int(m.group("del") or 0),
    }


def _merge_conflict_files(stdout: str) -> List[str]:
    """Конфликтные файлы из stdout git merge-tree --write-tree --name-only.

    Формат stdout при конфликте (git 2.46, проверено):
        <tree-sha>
        <file-1>
        <file-2>
        (пусто)
        Auto-merging <file-1>
        CONFLICT (content): Merge conflict in <file-1>
        ...
    Первая строка — tree-sha (пропускается); остальные неслужебные строки —
    имена файлов. Fallback: regex 'in <file>' из CONFLICT-строк.
    """
    files: List[str] = []
    lines = [ln.strip() for ln in stdout.splitlines()]
    for i, ln in enumerate(lines):
        if i == 0:
            continue
        if not ln or ln.startswith(("Auto-merging", "CONFLICT", "Warning",
                                    "warning", "hint", "error", "fatal")):
            continue
        # защита от повторного sha (tree/object id) среди строк
        if len(ln) == 40 and all(c in "0123456789abcdef" for c in ln.lower()):
            continue
        files.append(ln)
    # fallback: имена файлов из CONFLICT-строк ('Merge conflict in <file>')
    if not files:
        for m in re.finditer(r"Merge conflict in (.+)", stdout):
            name = m.group(1).strip()
            if name:
                files.append(name)
    # дедупликация с сохранением порядка
    seen: set = set()
    dedup: List[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            dedup.append(f)
    return dedup


def _empty_diff() -> Dict[str, Any]:
    return {"commits": [], "diffstat": {"files": 0, "insertions": 0, "deletions": 0},
            "changed_files": [], "changed": True}


# Стабильные ветки для слияния снов в порядке приоритета (W13-r2, TD-W13-3).
# Ночной сон НЕ должен вливаться в feature-ветку разработки.
_STABLE_TARGETS = ("master", "develop", "main")


def resolve_default_target(repo_root: Optional[str] = None) -> str:
    """Стабильная ветка для merge снов: master > develop > main > HEAD-ветка.

    W13-r2 (TD-W13-3): portable имеет ТОЛЬКО master (нет main), HEAD сидит на
    feature/b1-t2-core-config. Старый фолбэк на текущую HEAD-ветку уводил бы
    ночной сон в feature — запрещено. Приоритет: явные стабильные ветки;
    HEAD-ветка берётся только как последний фолбэк (репо без master/develop/main,
    напр. свежий temp-репо теста с инициализацией `git init -b main`).
    """
    repo = Path(repo_root).resolve() if repo_root else REPO_ROOT
    def _has(branch: str) -> bool:
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify",
             f"refs/heads/{branch}"],
            capture_output=True, text=True, errors="replace", check=False)
        return proc.returncode == 0
    for cand in _STABLE_TARGETS:
        if _has(cand):
            return cand
    cur = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
        capture_output=True, text=True, errors="replace", check=False
    ).stdout.strip()
    return cur or "master"


class SleepGit:
    """Детерминированная git-обёртка цикла сна. Все мутации — через git CLI.

    dry_run=True: мутирующие команды печатаются и НЕ выполняются; read-only
    команды (rev-parse, ls-tree, log, diff, merge-tree) выполняются по-настоящему.
    В dry_run диффы/conflict-детекция не выполняются (веток ещё нет) — только
    валидация цикла.
    """

    def __init__(self, repo_root: Optional[str] = None,
                 dry_run: bool = False, target: str = "main") -> None:
        self.repo = Path(repo_root).resolve() if repo_root else REPO_ROOT
        self.dry_run = dry_run
        self.target = target
        self.state: Dict[str, Any] = {"baseline": None, "branches": [],
                                      "executed": [], "merged": [],
                                      "conflicts": [], "false_ready": [],
                                      "branch_diffs": {}, "lessons": [],
                                      "restored": None, "task_id": None}

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
        self.state["task_id"] = task_id
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
        - failed ветка НЕ удаляется, только помечается (канон: не терять работу);
        - keep-решение принимает restore_baseline (см. W13).
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

    # ------------------------------------------------ W13: рефлексия (диффы)
    def _collect_branch_diff(self, branch: str) -> Dict[str, Any]:
        """Рефлексия ветки против baseline: commits, diffstat, changed_files.

        Маркер-файлы (.runs/sleep_markers/**) исключаются — они служебные.
        changed=False -> ветка «пустая» (только маркер) -> false_ready.
        В dry_run веток ещё нет — возвращаем пустой diff (changed=True,
        чтобы не отфильтровать ветку на этапе валидации цикла).
        """
        if self.dry_run:
            return _empty_diff()
        base = (self.state.get("baseline") or {}).get("commit")
        if not base:
            return _empty_diff()
        commits = [ln.strip() for ln in self._git_ro(
            ["log", "--format=%H", f"{base}..{branch}"],
            check=False).stdout.splitlines() if ln.strip()]
        shortstat = self._git_ro(
            ["diff", "--shortstat", f"{base}..{branch}", "--"] + _DIFF_PATHS,
            check=False).stdout.strip()
        changed_files = [ln.strip() for ln in self._git_ro(
            ["diff", "--name-only", f"{base}..{branch}", "--"] + _DIFF_PATHS,
            check=False).stdout.splitlines() if ln.strip()]
        return {
            "commits": commits,
            "diffstat": _parse_shortstat(shortstat),
            "changed_files": changed_files,
            "changed": bool(changed_files),
        }

    def collect_branch_diffs(self, branches: List[str]) -> None:
        """Собрать рефлексию по всем веткам в state['branch_diffs'] (W13-T1)."""
        for branch in branches:
            if branch not in self.state.get("branch_diffs", {}):
                self.state.setdefault("branch_diffs", {})[branch] = self._collect_branch_diff(branch)

    # ------------------------------------------------ W13: конфликт-детекция
    def _merge_tree_precheck(self, target: str, branch: str) -> Dict[str, Any]:
        """Сухой pre-check конфликта: git merge-tree --write-tree --name-only.

        exit 0 -> merge чистый (ok). exit 1 -> конфликт: files[] из stdout.
        Рабочая копия не трогается. В dry_run — пропуск (веток ещё нет).
        """
        if self.dry_run:
            return {"ok": True, "files": []}
        proc = self._git_ro(
            ["merge-tree", "--write-tree", "--name-only", target, branch],
            check=False)
        if proc.returncode == 0:
            return {"ok": True, "files": []}
        return {"ok": False, "files": _merge_conflict_files(proc.stdout)}

    # ------------------------------------------------------------ 4. merge
    def _resolve_target(self, target: str) -> str:
        """Target для merge: явно переданный / self.target / стабильная ветка.

        W13-r2 (TD-W13-3): вместо молчаливого фолбэка на текущую HEAD-ветку —
        стабильная ветка репо (master > develop > main); HEAD-ветка только как
        последний фолбэк (и НИКОГДА не feature-стиль 'feature/*', 'fix/*',
        'test-*' — иначе ночной сон вольётся в ветку разработки).
        """
        if target and target != "main" \
                and self._git_ro(["rev-parse", "--verify",
                                  f"refs/heads/{target}"],
                                 check=False).returncode == 0:
            return target
        if not target or target == "main":
            # дефолт CLI (--target main) или legacy-передача "main":
            # резолвим в стабильную ветку репо
            resolved = resolve_default_target(self.repo)
            if target == "main" and resolved != "main":
                print(f"[sleep_git] ветка 'main' не найдена — "
                      f"использую стабильную '{resolved}'")
            return resolved
        cur = self._git_ro(["symbolic-ref", "--short", "HEAD"],
                           check=False).stdout.strip()
        if cur:
            print(f"[sleep_git] ветка '{target}' не найдена — "
                  f"использую текущую '{cur}'")
            return cur
        raise GitSleepError(f"целевая ветка '{target}' не существует и HEAD detached")

    def merge_branches(self, branches: List[str], target: Optional[str] = None
                       ) -> List[Dict[str, str]]:
        """Последовательный merge веток в target с защитой от потери данных.

        W13-логика на каждую ветку:
          1. false_ready: diff против baseline пуст (только маркер) -> НЕ merge,
             класс false_ready (keep).
          2. merge-tree pre-check: конфликт -> класс conflict (keep), НЕ merge,
             рабочая копия не трогается, запись в conflicts[].
          3. реальный merge; конфликт -> abort, класс conflict (keep),
             запись в conflicts[].

        Конфликт НЕ блокирует: переход к следующей ветке (канон гл.26 —
        возврат к baseline всё равно выполняется).
        """
        target = self._resolve_target(target or self.target)
        results: List[Dict[str, str]] = []
        conflicts: List[Dict[str, Any]] = []
        for branch in branches:
            # рефлексия ветки (если ещё не собрана)
            diff = self.state.get("branch_diffs", {}).get(branch) \
                or self._collect_branch_diff(branch)
            self.state.setdefault("branch_diffs", {})[branch] = diff
            if not diff.get("changed", True):
                # Дыра-2/W13-T1: пустая ветка не готова к merge
                print(f"[sleep_git] {branch}: false_ready (нет изменений) — не merge")
                results.append({"branch": branch, "status": "false_ready"})
                if branch not in self.state.setdefault("false_ready", []):
                    self.state["false_ready"].append(branch)
                continue
            # Дыра-1/W13-T1: merge-tree pre-check (сухой, без рабочей копии)
            pre = self._merge_tree_precheck(target, branch)
            if not pre["ok"]:
                print(f"[sleep_git] {branch}: merge-tree pre-check конфликт с "
                      f"'{target}' — ветка в KEEP")
                conflicts.append({"branch": branch, "target": target,
                                  "files": pre["files"],
                                  "reason": "merge-tree exit 1", "kept": True})
                results.append({"branch": branch, "status": "conflict"})
                continue
            self._git(["checkout", target])
            proc = self._git(["merge", "--no-ff", "--no-edit", branch], check=False)
            if proc.returncode == 0:
                results.append({"branch": branch, "status": "ok"})
            else:
                print(f"[sleep_git] конфликт при merge {branch} -> {target}; abort; "
                      f"ветка в KEEP")
                self._git(["merge", "--abort"], check=False)
                conflicts.append({"branch": branch, "target": target,
                                  "files": pre["files"],
                                  "reason": "merge conflict", "kept": True})
                results.append({"branch": branch, "status": "conflict"})
        self.state["merged"] = results
        if conflicts:
            self.state.setdefault("conflicts", []).extend(conflicts)
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

    def _keep_set(self, state: Dict[str, Any], keep_failed: bool) -> set:
        """Множество веток, которые restore НЕ удаляет (W13, Дыра-1).

        - conflict (записан в state['conflicts']) — ВСЕГДА keep (данные не теряются);
        - false_ready (state['false_ready']) — ВСЕГДА keep (пустая, но своя);
        - failed при keep_failed=True — keep (канон: не терять работу).
        """
        keep: set = set(state.get("false_ready", []))
        keep |= {c["branch"] for c in state.get("conflicts", [])}
        if keep_failed:
            keep |= {e["branch"] for e in state.get("executed", [])
                     if e["status"] == "failed"}
        return keep

    def restore_baseline(self, task_id: str, keep_failed: bool = False
                         ) -> Dict[str, str]:
        """Возврат к baseline: checkout tag + удаление ТОЛЬКО слитых sleep-веток.

        Удаляются ТОЛЬКО ветки, созданные этим сном (по маркеру/state) И
        отсутствующие в keep-множестве (см. _keep_set).
        Конфликтные и false_ready ветки НЕ удаляются (Дыра-1 закрыта).
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
        keep = self._keep_set(state, keep_failed)
        to_delete = [b for b in own if b not in keep]
        for branch in to_delete:
            print(f"[sleep_git] удаляю sleep-ветку {branch} (по маркеру, слита)")
            # идемпотентно: ветка может быть уже удалена предыдущим run (branch -D на отсутствующей = rc!=0)
            self._git(["branch", "-D", branch], check=False)
        for branch in sorted(keep):
            print(f"[sleep_git] KEEP sleep-ветку {branch} (не слита: conflict/"
                  f"false_ready/failed) — данные сохранены")
        self.state["restored"] = tag
        self._save_state(task_id)
        return {"restored_to": tag}

    # ------------------------------------------------------------ 6. report
    def _status_for(self, executed: List[Dict[str, str]],
                    merged: List[Dict[str, str]]) -> Dict[str, str]:
        """Финальный класс статуса каждой ветки (порядок приоритетов):
        merged(ok) > conflict > false_ready > failed > ok (не слита, нет конфликта).
        """
        status_map: Dict[str, str] = {}
        for e in executed:
            status_map[e["branch"]] = e["status"]  # ok|failed
        for m in merged:
            st = m["status"]
            if st == "ok":
                status_map[m["branch"]] = "merged"
            elif st in ("conflict", "false_ready"):
                status_map[m["branch"]] = st
        return status_map

    def report(self) -> Dict[str, Any]:
        """Итог цикла сна (W13-формат): {task, baseline_tag, timestamp,
        simulated, branches[], merged, conflicts[], restored_to, lessons[]}.

        Рефлексия (Дыра-2): каждая ветка несёт commits[], diffstat{},
        changed_files[] против baseline. branch_diffs могут отсутствовать
        (restore-only прогон) — тогда пустые значения.
        """
        task_id = self.state.get("task_id")
        baseline = self.state.get("baseline") or {}
        tag = baseline.get("tag")
        status_map = self._status_for(self.state.get("executed", []),
                                      self.state.get("merged", []))
        branches: List[Dict[str, Any]] = []
        diffs = self.state.get("branch_diffs", {})
        for b in self.state.get("branches", []):
            diff = diffs.get(b, _empty_diff())
            branches.append({
                "name": b,
                "status": status_map.get(b, "created"),
                "commits": diff["commits"],
                "diffstat": diff["diffstat"],
                "changed_files": diff["changed_files"],
            })
        conflicts = self.state.get("conflicts", [])
        lessons = self.state.get("lessons") or [
            {"branch": c["branch"],
             "lesson": f"конфликт: {', '.join(c['files']) or '?'}",
             "target": ".l2_memory"}
            for c in conflicts
        ]
        return {
            "task": task_id,
            "baseline_tag": tag,
            "timestamp": _now_iso(),
            "simulated": False,
            "branches": branches,
            "merged": [m["branch"] for m in self.state.get("merged", [])
                       if m["status"] == "ok"],
            "conflicts": conflicts,
            "restored_to": self.state.get("restored"),
            "lessons": lessons,
        }

    # ------------------------------------------------ W13: запись отчёта сна
    def _l2_remember(self, task_id: str, lesson: Dict[str, Any]) -> str:
        """Запись урока в .l2_memory/<task_id>.json (формат MemoryCirculator.l2_remember).

        Дедупликация по _key = sha256(lesson_text); _admissions накапливаются.
        Возвращает _key. dry_run — ничего не пишет.
        """
        key = hashlib.sha256(lesson.get("lesson_text", "").encode("utf-8")).hexdigest()[:12]
        if self.dry_run:
            return key
        f = self.repo / L2_REL / f"{_safe_token(task_id)}.json"
        data = {"task_id": task_id, "candidate_lessons": []}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {"task_id": task_id, "candidate_lessons": []}
            except (json.JSONDecodeError, OSError):
                data = {"task_id": task_id, "candidate_lessons": []}
        exists = any(l.get("_key") == key for l in data["candidate_lessons"])
        if exists:
            for l in data["candidate_lessons"]:
                if l.get("_key") == key:
                    l["_admissions"] = int(l.get("_admissions", 1)) + 1
        else:
            rec = dict(lesson)
            rec["_key"] = key
            rec["_admissions"] = 1
            data["candidate_lessons"].append(rec)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return key

    def _conflicts_today(self, conflicts: List[Dict[str, Any]]) -> None:
        """Агрегация конфликтов в .runs/sleep_reports/conflicts_<date>.json."""
        if self.dry_run or not conflicts:
            return
        reports_dir = self.repo / REPORTS_REL
        reports_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now().strftime("%Y%m%d")
        f = reports_dir / f"conflicts_{date}.json"
        entries: List[Dict[str, Any]] = []
        if f.exists():
            try:
                entries = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except (json.JSONDecodeError, OSError):
                entries = []
        known = {(e.get("branch"), e.get("target")) for e in entries}
        for c in conflicts:
            if (c.get("branch"), c.get("target")) not in known:
                entries.append(c)
        f.write_text(json.dumps(entries, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    def write_report(self, task_id: Optional[str] = None) -> str:
        """Сохранить отчёт сна в .runs/sleep_reports/<task>.json (W13-T3).

        Побочно: уроки конфликтов -> .l2_memory/<task>.json (L2) и
        .runs/sleep_reports/conflicts_<date>.json. Возвращает путь к отчёту.
        """
        report = self.report()
        tid = task_id or report.get("task") or "sleep"
        if self.dry_run:
            return str(self.repo / REPORTS_REL / f"{tid}.json")
        reports_dir = self.repo / REPORTS_REL
        reports_dir.mkdir(parents=True, exist_ok=True)
        f = reports_dir / f"{tid}.json"
        f.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        # уроки конфликтов -> L2 (совместимо с MemoryCirculator.l2_remember)
        for c in report.get("conflicts", []):
            self._l2_remember(tid, {
                "lesson_text": f"конфликт merge {c['branch']}->{c['target']}: "
                               f"{', '.join(c['files']) or '?'}",
                "reason_codes": ["sleep_merge_conflict"],
                "evidence_refs": [f".runs/sleep_reports/{tid}.json"],
                "branch": c["branch"], "target": c["target"],
                "files": c["files"],
            })
        self._conflicts_today(report.get("conflicts", []))
        return str(f)


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
    # служебные пути цикла сна (.runs/sleep_state, .runs/sleep_markers,
    # .runs/sleep_reports, .runs/session_deltas, .l2_memory)
    # НЕ считаются грязной рабочей копией — иначе повторный run блокируется своим же состоянием.
    ignore = (str(STATE_REL), str(MARKERS_REL), str(REPORTS_REL),
              ".runs/session_deltas", str(L2_REL))
    dirty_lines = [
        ln for ln in sg._git_ro(
            ["status", "--porcelain", "--untracked-files=all"]).stdout.splitlines()
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
    # W13-T1: рефлексия всех веток (commits/diffstat/changed_files) против baseline
    sg.collect_branch_diffs([c["branch"] for c in created if c["created"]])
    # W13-T1: false_ready-ветки отсеиваются в merge_branches (нет изменений)
    sg.merge_branches(ok_branches, target=args.target) if ok_branches else None
    # W13-T1/Дыра-1: conflict/false_ready ВСЕГДА keep, failed — при --keep-failed
    sg.restore_baseline(args.task, keep_failed=args.keep_failed)
    print(json.dumps(sg.report(), ensure_ascii=False, indent=2))
    sg.write_report(args.task)
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
                    "execute -> merge -> restore (W13: рефлексия + keep конфликтов)")
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
                       help="ветка для merge (по умолчанию main -> стабильная "
                            "ветка репо: master/develop/main)")
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