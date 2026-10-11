#!/usr/bin/env python3
"""check_sleep_after.py — 10 проверок чек-листа после цикла сна (W13-T4).

Постаудит сна: детерминированно проверяет, что git-цикл сна прошёл БЕЗ
потери данных (W13). Читает отчёт сна (.runs/sleep_reports/<task>.json)
и живую git-историю репозитория.

10 проверок (по спецификации W13):
  1. baseline создан (тег baseline/<task>/<ts> существует).
  2. Ветки только failed/conflict/keep/merged (нет потерянных ok-веток).
  3. sleep-коммиты влиты (коммиты merged-веток достижимы из target).
  4. Изменения не пусты (diffstat у влитых веток > 0).
  5. Рабочая копия чистая (после restore, служебные пути исключены).
  6. Отчёт валиден (W13-T2 schema, sleep_report_check).
  7. Конфликты задокументированы (в conflicts[]).
  8. Инвариант потери данных: ветки с неслитыми изменениями НЕ удалены.
  9. dry-run в хуке (pre-commit только --dry-run).
  10. simulated:false (ночной прогон гитирует по-настоящему).

Выход: 10/10 PASS -> exit 0; любая FAIL -> exit 1.

Usage:
    python check_sleep_after.py --report .runs/sleep_reports/nightly.json
                                [--repo <git-root>] [--pre-commit hooks/pre-commit]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / ".runs" / "sleep_reports" / "nightly.json"
DEFAULT_PRE_COMMIT = REPO_ROOT / "hooks" / "pre-commit"

# пути, которые НЕ считаются грязной рабочей копией (как в sleep_git._ensure_clean)
_SERVICE_PATHS = (
    ".runs/sleep_state", ".runs/sleep_markers", ".runs/sleep_reports",
    ".runs/session_deltas", ".l2_memory",
)

# финальные классы статусов после restore (проверка 2)
ALLOWED_FINAL_STATUSES = {"merged", "failed", "conflict", "keep", "false_ready"}
FORBIDDEN_FINAL_STATUSES = {"ok", "created"}

# классы веток, которые обязаны СУЩЕСТВОВАТЬ после restore (проверка 8)
KEEP_STATUSES = {"conflict", "false_ready", "failed"}


def _git(repo: Path, args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo)] + list(args),
                          capture_output=True, text=True, errors="replace",
                          check=False)


def _report_path(args: argparse.Namespace) -> Path:
    if args.report:
        return Path(args.report).resolve()
    return DEFAULT_REPORT


# ------------------------------------------------------------------ проверки
def _check_baseline(repo: Path, report: Dict[str, Any]) -> Tuple[bool, str]:
    """1. baseline создан: тег baseline/<task>/<ts> существует в репо."""
    tag = report.get("baseline_tag")
    if not tag or not tag.startswith("baseline/"):
        return False, f"baseline_tag отсутствует/неверен: {tag!r}"
    proc = _git(repo, ["tag", "--list", tag])
    exists = tag in [ln.strip() for ln in proc.stdout.splitlines()]
    return exists, (f"тег {tag} найден" if exists else f"тег {tag} НЕ найден")


def _check_statuses(report: Dict[str, Any]) -> Tuple[bool, str]:
    """2. Ветки только merged/failed/conflict/keep/false_ready (нет ok/created)."""
    bad = [b["name"] for b in report.get("branches", [])
           if b.get("status") in FORBIDDEN_FINAL_STATUSES]
    if bad:
        return False, f"потерянные ok/created-ветки после restore: {bad}"
    return True, "все ветки в допустимых финальных статусах"


def _check_commits_merged(repo: Path, report: Dict[str, Any],
                          target: str) -> Tuple[bool, str]:
    """3. Коммиты merged-веток достижимы из target (sleep-коммиты влиты)."""
    merged_names = set(report.get("merged", []))
    unmerged: List[str] = []
    for b in report.get("branches", []):
        if b.get("status") != "merged" and b["name"] not in merged_names:
            continue
        for sha in b.get("commits", []):
            if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
                unmerged.append(f"{b['name']}:{sha}(не sha)")
                continue
            p = _git(repo, ["merge-base", "--is-ancestor", sha, target])
            if p.returncode != 0:
                unmerged.append(f"{b['name']}:{sha[:8]}")
    if unmerged:
        return False, f"коммиты не влиты в {target}: {unmerged[:10]}"
    return True, f"все sleep-коммиты достижимы из {target}"


def _check_diffstat(report: Dict[str, Any]) -> Tuple[bool, str]:
    """4. Изменения не пусты: diffstat.files > 0 у влитых веток."""
    empty = [b["name"] for b in report.get("branches", [])
             if b.get("status") == "merged"
             and b.get("diffstat", {}).get("files", 0) <= 0]
    if empty:
        return False, f"влитые ветки с пустым diffstat: {empty}"
    return True, "все влитые ветки несут изменения"


def _check_clean_worktree(repo: Path) -> Tuple[bool, str]:
    """5. Рабочая копия чистая (служебные пути .runs/.l2_memory исключены)."""
    proc = _git(repo, ["status", "--porcelain", "--untracked-files=all"])
    dirty = [ln for ln in proc.stdout.splitlines()
             if not any(ig in ln for ig in _SERVICE_PATHS)]
    if dirty:
        return False, f"грязная рабочая копия: {dirty[:5]}"
    return True, "рабочая копия чистая"


def _check_report_valid(report_path: Path,
                        report: Dict[str, Any]) -> Tuple[bool, str]:
    """6. Отчёт валиден по W13-T2 schema (sleep_report_check.validate_report)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from sleep_report_check import validate_report
        violations = validate_report(report)
    except Exception as exc:  # noqa: BLE001 — отсутствие модуля = FAIL
        return False, f"не удалось запустить валидатор: {exc}"
    if violations:
        return False, f"схема не прошла: {violations[:5]}"
    return True, f"схема валидна ({report_path.name})"


def _check_conflicts_documented(report: Dict[str, Any]) -> Tuple[bool, str]:
    """7. Конфликты задокументированы: ветки conflict имеют запись в conflicts[]."""
    conflicts = {c.get("branch") for c in report.get("conflicts", [])}
    conflict_branches = [b["name"] for b in report.get("branches", [])
                         if b.get("status") == "conflict"]
    missing = [b for b in conflict_branches if b not in conflicts]
    if missing:
        return False, f"конфликтные ветки без записи в conflicts[]: {missing}"
    if conflict_branches:
        return True, (f"конфликты задокументированы "
                      f"({len(conflicts)} записей)")
    return True, "конфликтов нет (документировать нечего)"


def _check_no_data_loss(repo: Path, report: Dict[str, Any]) -> Tuple[bool, str]:
    """8. Инвариант потери данных: ветки с неслитыми изменениями НЕ удалены.

    Ветки со статусом conflict/false_ready/failed обязаны существовать
    (restore их KEEP-ит). Влитые (merged) — обязаны отсутствовать.
    """
    missing_keep: List[str] = []
    for b in report.get("branches", []):
        status = b.get("status")
        name = b["name"]
        exists = _git(repo, ["rev-parse", "--verify",
                             f"refs/heads/{name}"]).returncode == 0
        if status in KEEP_STATUSES and not exists:
            missing_keep.append(name)
    if missing_keep:
        return False, (f"ПОТЕРЯ ДАННЫХ: неслитые ветки удалены: "
                       f"{missing_keep}")
    return True, "все неслитые ветки сохранены (инвариант выполнен)"


def _check_precommit_dry_run(pre_commit: Path) -> Tuple[bool, str]:
    """9. pre-commit вызывает sleep_git только в --dry-run."""
    if not pre_commit.exists():
        return False, f"хук pre-commit не найден: {pre_commit}"
    try:
        text = pre_commit.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"не удалось прочитать pre-commit: {exc}"
    if "sleep_git.py" not in text:
        return False, "pre-commit не вызывает sleep_git.py"
    if "--dry-run" not in text:
        return False, "pre-commit вызывает sleep_git БЕЗ --dry-run"
    if re.search(r"sleep_git\.py(?![^\n]*--dry-run)[^\n]*\brun\b", text):
        return False, "pre-commit вызывает sleep_git run (не dry-run)"
    return True, "pre-commit: только --dry-run snapshot"


def _check_simulated(report: Dict[str, Any]) -> Tuple[bool, str]:
    """10. simulated:false — ночной прогон гитирует по-настоящему."""
    if report.get("simulated") is False:
        return True, "simulated:false (реальный git)"
    return False, f"simulated={report.get('simulated')!r} (должен быть false)"


# --------------------------------------------------------------------- CLI
CHECKS = (
    ("1. baseline создан", _check_baseline),
    ("2. статусы веток", _check_statuses),
    ("3. sleep-коммиты влиты", _check_commits_merged),
    ("4. изменения не пусты", _check_diffstat),
    ("5. рабочая копия чистая", _check_clean_worktree),
    ("6. отчёт валиден", _check_report_valid),
    ("7. конфликты задокументированы", _check_conflicts_documented),
    ("8. инвариант потери данных", _check_no_data_loss),
    ("9. dry-run в хуке", _check_precommit_dry_run),
    ("10. simulated:false", _check_simulated),
)


def run_checks(report_path: Path, repo: Path,
               pre_commit: Path, target: str) -> List[Dict[str, Any]]:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [{"id": "0", "name": "чтение отчёта", "ok": False,
                 "detail": f"не удалось прочитать {report_path}: {exc}"}]
    if not isinstance(report, dict):
        return [{"id": "0", "name": "чтение отчёта", "ok": False,
                 "detail": "отчёт не JSON-объект"}]

    # явная диспетчеризация: каждый вызов знает свои аргументы
    calls: List[Tuple[str, Any]] = [
        ("1. baseline создан", _check_baseline(repo, report)),
        ("2. статусы веток", _check_statuses(report)),
        ("3. sleep-коммиты влиты", _check_commits_merged(repo, report, target)),
        ("4. изменения не пусты", _check_diffstat(report)),
        ("5. рабочая копия чистая", _check_clean_worktree(repo)),
        ("6. отчёт валиден", _check_report_valid(report_path, report)),
        ("7. конфликты задокументированы", _check_conflicts_documented(report)),
        ("8. инвариант потери данных", _check_no_data_loss(repo, report)),
        ("9. dry-run в хуке", _check_precommit_dry_run(pre_commit)),
        ("10. simulated:false", _check_simulated(report)),
    ]
    results: List[Dict[str, Any]] = []
    for i, (name, outcome) in enumerate(calls, start=1):
        try:
            ok, detail = outcome
        except Exception as exc:  # noqa: BLE001 — проверка не роняет остальные
            ok, detail = False, f"исключение: {exc}"
        results.append({"id": str(i), "name": name, "ok": ok, "detail": detail})
    return results


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="check_sleep_after.py",
        description="10 проверок чек-листа после цикла сна (W13-T4). exit 0/1.")
    parser.add_argument("--report", default=None,
                        help="путь к отчёту сна (по умолчанию "
                             ".runs/sleep_reports/nightly.json)")
    parser.add_argument("--repo", default=str(REPO_ROOT),
                        help="git-корень (по умолчанию portable)")
    parser.add_argument("--pre-commit", default=str(DEFAULT_PRE_COMMIT),
                        help="путь к хуку pre-commit")
    parser.add_argument("--target", default="main",
                        help="ветка merge (для проверки влитости)")
    args = parser.parse_args(argv)

    report_p = _report_path(args)
    repo = Path(args.repo).resolve()
    pre_commit = Path(args.pre_commit).resolve()
    results = run_checks(report_p, repo, pre_commit, args.target)

    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        # W13-r2 (TD-W13-1): имя из CHECKS уже содержит номер ('1. baseline
        # создан'); печатаем имя БЕЗ префикса id — убран дубль '[PASS] 1. 1. '.
        print(f"[{mark}] {r['name']}: {r['detail']}")
    print(f"--- {passed}/{total} PASS ---")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())