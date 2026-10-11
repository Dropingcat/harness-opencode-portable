#!/usr/bin/env python3
"""git_session_sync.py — авто-цепляние изменений сессии агента в git + детерминированный аудит.

Канон гл.13 (хуки) + гл.24 (детерминированная проверка). Цикл сна агента вызывает
`sync`; скрипт подхватывает новые текстовые дельты сессий
(session_diff/ses_*.json), складывает их в `.runs/session_deltas/` (append-only) и
коммитит в git-ветку разработки (по умолчанию `main`, создаётся при отсутствии).
Аудитор (`audit_delta`) детерминированно проверяет текст на маркеры несоответствия:
TODO/FIXME/XXX/TEMP/костыль/заглушка/не работает/не уверен/вероятно/скорее всего.

Usage:
    python git_session_sync.py sync [--session-dir <dir>] [--since-minutes 60]
                                   [--branch main] [--no-commit] [--audit]
    python git_session_sync.py audit --file <path>

API:
    collect_text_deltas(session_dir, since_minutes=60) -> [{session_id, text, ts}]
    commit_delta(delta, branch="main") -> {delta_path, committed, commit_hash}
    audit_delta(delta_path) -> {findings: [{marker, line, severity}], count}
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / ".runs"
DELTAS_DIR = RUNS_DIR / "session_deltas"
INDEX_FILE = RUNS_DIR / "session_sync_index.json"
DEFAULT_SESSION_DIR = Path.home() / ".local" / "share" / "opencode" / "storage" / "session_diff"

# (marker, severity) — детерминированная карта аудита (порядок = приоритет вывода).
AUDIT_MARKERS = (
    ("TODO", "info"),
    ("FIXME", "warning"),
    ("XXX", "warning"),
    ("TEMP", "info"),
    ("костыль", "warning"),
    ("заглушка", "warning"),
    ("не работает", "critical"),
    ("не уверен", "warning"),
    ("вероятно", "info"),
    ("скорее всего", "info"),
)


# --------------------------------------------------------------------------
# Индекс обработанных сессий (.runs/session_sync_index.json {session_id: last_msg_id})
# --------------------------------------------------------------------------

def _load_index() -> dict:
    if not INDEX_FILE.exists():
        return {}
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_index(index: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(INDEX_FILE)


def _advance_index(session_id: str, last_msg_id) -> None:
    """Записать курсор последнего обработанного сообщения сессии."""
    if last_msg_id is None:
        return
    index = _load_index()
    index[session_id] = str(last_msg_id)
    _save_index(index)


# --------------------------------------------------------------------------
# 1. collect_text_deltas — сбор новых текстовых дельт сессий
# --------------------------------------------------------------------------

def _msg_id(m: dict, idx: int) -> str:
    info = m.get("info") or {}
    mid = info.get("id") or m.get("id")
    return str(mid) if mid is not None else f"idx:{idx}"


def collect_text_deltas(session_dir, since_minutes: int = 60) -> list:
    """Находит ses_*.json новее since_minutes, извлекает ТЕКСТОВЫЕ parts
    (type=="text") НОВЫХ сообщений role=assistant, соединяет в текст.

    Возвращает [{session_id, text, ts}] — только новые (индекс
    .runs/session_sync_index.json хранит {session_id: last_msg_id}).
    Каждый delta несёт приватный ключ `_last_msg_id` (внутренний курсор для sync).
    """
    session_dir = Path(session_dir)
    if not session_dir.is_dir():
        return []
    cutoff = time.time() - since_minutes * 60.0
    index = _load_index()
    deltas = []

    for path in sorted(session_dir.glob("ses_*.json")):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue  # файл не обновлялся в окне — пропуск

        session_id = path.stem[4:] if path.stem.startswith("ses_") else path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # битый файл — не блокируем остальные

        msgs = data.get("messages", []) if isinstance(data, dict) else data
        if not isinstance(msgs, list):
            continue

        last_seen = index.get(session_id)
        found_last = last_seen is None  # нет в индексе → берём всё
        new_texts: list = []
        last_msg_id = None

        for i, m in enumerate(msgs):
            if not isinstance(m, dict):
                continue
            info = m.get("info") or {}
            if info.get("role") not in (None, "assistant"):
                continue
            mid = _msg_id(m, i)
            if not found_last:
                if mid == last_seen:
                    found_last = True
                continue  # уже обработанное сообщение
            for part in m.get("parts") or []:
                if isinstance(part, dict) and part.get("type") == "text":
                    t = part.get("text")
                    if isinstance(t, str) and t.strip():
                        new_texts.append(t)
            last_msg_id = mid

        text = "\n".join(new_texts).strip()
        if not text:
            continue  # нечего цеплять

        ts = _dt.datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")
        deltas.append({
            "session_id": session_id,
            "text": text,
            "ts": ts,
            "_last_msg_id": last_msg_id,
        })

    return deltas


# --------------------------------------------------------------------------
# 2. commit_delta — запись дельты в .runs/session_deltas + git commit
# --------------------------------------------------------------------------

def _git(args: list, check: bool = True):
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    out = (proc.stdout or "").strip()
    return out or None


def _ensure_branch(branch: str) -> None:
    """Формирует ветку разработки: создаёт branch из текущего HEAD, если нет."""
    if not branch:
        return
    current = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if current == branch:
        return
    exists = _git(["rev-parse", "--verify", "--quiet", branch], check=False) is not None
    if exists:
        _git(["checkout", branch])
    else:
        _git(["checkout", "-b", branch])


def _commit_message(session_id: str, text: str) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    return f"session-sync({session_id}): {one_line[:80]}"


def commit_delta(delta: dict, branch: str = "main") -> dict:
    """Пишет текст дельты в .runs/session_deltas/<session_id>_<ts>.txt (append-only,
    utf-8), затем git add + git commit на ветке branch.

    Возвращает {delta_path, committed, commit_hash}. Если git-операции не удались —
    файл уже записан, committed=False, commit_hash=None, в результате git_error.
    При delta["no_commit"]=True — только запись файла, без git.
    """
    session_id = delta["session_id"]
    text = delta.get("text", "")
    ts = delta.get("ts") or _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    DELTAS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id)) or "session"
    delta_path = DELTAS_DIR / f"{safe_id}_{ts}.txt"

    # append-only: дозаписываем в конец (utf-8)
    with delta_path.open("a", encoding="utf-8") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")

    committed = False
    commit_hash = None
    git_error = None
    if not delta.get("no_commit"):
        try:
            _ensure_branch(branch)
            rel = delta_path.relative_to(REPO_ROOT).as_posix()
            _git(["add", "--", rel])
            _git(["commit", "-m", _commit_message(session_id, text)])
            committed = True
            commit_hash = _git(["rev-parse", "HEAD"])
        except RuntimeError as exc:
            git_error = str(exc)

    result = {
        "delta_path": str(delta_path),
        "committed": committed,
        "commit_hash": commit_hash,
    }
    if git_error:
        result["git_error"] = git_error
    return result


# --------------------------------------------------------------------------
# 3. audit_delta — детерминированная проверка на маркеры несоответствия
# --------------------------------------------------------------------------

def audit_delta(delta_path) -> dict:
    """Читает файл дельты и ищет маркеры несоответствия (case-insensitive).

    Возвращает {findings: [{marker, line, severity}], count}. Нахождение —
    на каждую (строка, маркер) пару; severity из детерминированной карты
    AUDIT_MARKERS. Если файл не читается — single critical finding.
    """
    delta_path = Path(delta_path)
    try:
        text = delta_path.read_text(encoding="utf-8")
    except OSError:
        return {"findings": [{"marker": "<unreadable>", "line": 0, "severity": "critical"}], "count": 1}

    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        ll = line.lower()
        for marker, severity in AUDIT_MARKERS:
            if marker.lower() in ll:
                findings.append({"marker": marker, "line": line_no, "severity": severity})
    return {"findings": findings, "count": len(findings)}


# --------------------------------------------------------------------------
# 4. CLI
# --------------------------------------------------------------------------

def cmd_sync(args) -> int:
    deltas = collect_text_deltas(args.session_dir, args.since_minutes)
    if not deltas:
        print(json.dumps({"status": "noop", "new_deltas": 0}, ensure_ascii=False))
        return 0  # идемпотентно: ничего не коммитим

    results = []
    findings_any = False
    for delta in deltas:
        payload = dict(delta)
        payload["no_commit"] = args.no_commit
        res = commit_delta(payload, branch=args.branch)

        audit = {"findings": [], "count": 0}
        if args.audit and res.get("delta_path"):
            audit = audit_delta(res["delta_path"])
            if audit["count"] > 0:
                findings_any = True

        out = {
            "session_id": delta["session_id"],
            "delta_path": res.get("delta_path"),
            "committed": res.get("committed", False),
            "commit_hash": res.get("commit_hash"),
            "audit": audit,
        }
        if res.get("git_error"):
            out["git_error"] = res["git_error"]
        results.append(out)

        # дельта записана (append-only файл) → курсор можно двигать
        _advance_index(delta["session_id"], delta.get("_last_msg_id"))

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if (args.audit and findings_any) else 0


def cmd_audit(args) -> int:
    res = audit_delta(args.file)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 1 if res["count"] > 0 else 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="git_session_sync.py",
        description="Авто-цепляние изменений сессии агента в git + детерминированный аудит (канон гл.13/24).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="собрать новые дельты сессий и закоммитить")
    p_sync.add_argument("--session-dir", default=str(DEFAULT_SESSION_DIR),
                        help="каталог ses_*.json (по умолчанию ~/.local/share/opencode/storage/session_diff)")
    p_sync.add_argument("--since-minutes", type=int, default=60,
                        help="смотреть только файлы, изменённые за последние N минут")
    p_sync.add_argument("--branch", default="main", help="git-ветка разработки (создаётся при отсутствии)")
    p_sync.add_argument("--no-commit", action="store_true",
                        help="только записать дельты в .runs/session_deltas, без git add/commit")
    p_sync.add_argument("--audit", action="store_true",
                        help="после коммита прогнать audit_delta; exit 1 при findings>0")
    p_sync.set_defaults(func=cmd_sync)

    p_audit = sub.add_parser("audit", help="детерминированно проверить файл дельты")
    p_audit.add_argument("--file", required=True, help="путь к .txt дельте")
    p_audit.set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())