"""Durable job records with atomic single-flight admission and bounded workers."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3
import threading
import time
import uuid

from .paths import checked_output, output_dir


def owner_alive(pid):
    if pid == os.getpid():
        return True
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # access denied is NOT proof of death
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Jobs:
    def __init__(self, home, workers=2):
        self.home = checked_output(home, home)
        directory = output_dir(self.home / "state", self.home)
        self.path = checked_output(directory / "jobs.sqlite", self.home)
        self.semaphore = threading.BoundedSemaphore(max(1, min(workers, 4)))
        self.events = {}
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, key TEXT, name TEXT, payload TEXT,
                status TEXT, progress TEXT, result TEXT, error TEXT,
                cancel INTEGER, owner INTEGER, created REAL, updated REAL)""")

    @contextmanager
    def db(self):
        checked_output(self.path, self.home)
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def submit(self, name, payload, revision, handler, *, reuse_completed=True, retry_failed=False,
               identity=None, validate_result=None):
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        computation = json.dumps(identity, sort_keys=True, ensure_ascii=False) if identity is not None else body
        key = sha256(f"jobs/2\0{name}\0{computation}\0{revision}".encode("utf-8")).hexdigest()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM jobs WHERE key=? ORDER BY rowid DESC LIMIT 1", (key,)).fetchone()
            if prior:
                if prior["status"] in {"queued", "running", "cancel_requested"} and not owner_alive(prior["owner"]):
                    db.execute("UPDATE jobs SET status='interrupted',result=NULL,error='worker exited; explicit retry required' WHERE id=?", (prior["id"],))
                    prior = db.execute("SELECT * FROM jobs WHERE id=?", (prior["id"],)).fetchone()
                active = prior["status"] in {"queued", "running", "cancel_requested"}
                complete = prior["status"] == "completed" and reuse_completed
                if complete and validate_result is not None:
                    complete = validate_result(json.loads(prior["result"]))
                failed = prior["status"] in {"failed", "interrupted", "blocked", "partial"} and not retry_failed
                if active or complete or failed:
                    return {"id": prior["id"], "status": prior["status"], "reused": True}
            ident, now = uuid.uuid4().hex, time.time()
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (ident, key, name, body, "queued", "{}", None, None, 0, os.getpid(), now, now))
        event = threading.Event()
        self.events[ident] = event
        threading.Thread(target=self._execute, args=(ident, payload, handler, event), daemon=True, name=f"pilot-{name}-{ident[:6]}").start()
        return {"id": ident, "status": "queued", "reused": False}

    def _update(self, ident, **fields):
        if not fields:
            return
        allowed = {"status", "progress", "result", "error", "cancel"}
        if not set(fields).issubset(allowed):
            raise ValueError("invalid job field")
        fields["updated"] = time.time()
        with self.db() as db:
            db.execute("UPDATE jobs SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?", (*fields.values(), ident))

    def _cancelled(self, ident):
        with self.db() as db:
            row = db.execute("SELECT cancel FROM jobs WHERE id=?", (ident,)).fetchone()
        return not row or bool(row[0])

    def _execute(self, ident, payload, handler, event):
        try:
            with self.semaphore:
                if self._cancelled(ident):
                    self._update(ident, status="cancelled")
                    return
                self._update(ident, status="running")
                progress = lambda data: self._update(ident, progress=json.dumps(data, ensure_ascii=False))
                result = handler(payload, progress, lambda: self._cancelled(ident))
                outcome = result.get("status") if isinstance(result, dict) else None
                status = outcome if outcome in {"partial", "blocked", "failed", "cancelled"} else "completed"
                self._update(ident, status="cancelled" if self._cancelled(ident) else status, result=json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            self._update(ident, status="failed", error=f"{type(exc).__name__}: {str(exc)[:1000]}")
        finally:
            event.set()

    def get(self, ident):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
        if not row:
            return {"id": ident, "status": "not_found"}
        out = dict(row)
        if out["status"] in {"queued", "running", "cancel_requested"} and not owner_alive(out["owner"]):
            self._update(ident, status="interrupted", result=None, error="worker exited; explicit retry required")
            out.update(status="interrupted", result=None, error="worker exited; explicit retry required")
        for name in ("payload", "progress", "result"):
            out[name] = json.loads(out[name]) if out[name] is not None else None
        return out

    def cancel(self, ident):
        with self.db() as db:
            db.execute("UPDATE jobs SET cancel=1,status=?,updated=? WHERE id=? AND status IN ('queued','running')",
                       ("cancel_requested", time.time(), ident))
        return self.get(ident)

    def wait(self, ident, timeout=30):
        event = self.events.get(ident)
        if event:
            event.wait(timeout)
        return self.get(ident)

    def active(self, question):
        with self.db() as db:
            rows = db.execute("SELECT id,payload FROM jobs WHERE status IN ('queued','running','cancel_requested')").fetchall()
        current = [self.get(row["id"]) for row in rows if json.loads(row["payload"]).get("question") == question]
        return [{"id": row["id"], "name": row["name"], "status": row["status"]} for row in current if row["status"] in {"queued", "running", "cancel_requested"}]
