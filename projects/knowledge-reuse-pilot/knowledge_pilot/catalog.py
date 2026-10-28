"""Rebuildable SQLite/FTS catalog. Corpus paths are always read-only inputs."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import sqlite3
import stat
import tempfile
import time

from .extract import SUPPORTED, extract, parser_versions, redact
from .lease import FileLease, LeaseBusy
from .paths import checked_output, output_dir


DEFAULT_EXCLUDES = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "graphify-out"}
SECRET_NAMES = {".env", "credentials.json", "secrets.json", "id_rsa", "id_ed25519", ".netrc", ".npmrc", ".pypirc"}


def digest_file(path):
    h = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def within(path, root):
    return path == root or root in path.parents


class Catalog:
    def __init__(self, home, roots, *, exclude_dirs=None, max_file_bytes=41943040,
                 max_text_chars=250000, max_pdf_pages=200):
        self.home = checked_output(home, home)
        self.roots = {name: Path(path).resolve() for name, path in roots.items()}
        self.exclude_dirs = set(exclude_dirs or DEFAULT_EXCLUDES)
        self.max_file_bytes, self.max_text_chars = max_file_bytes, max_text_chars
        self.max_pdf_pages = max_pdf_pages
        self.extractor = f"local-extract/2:{max_text_chars}:{max_pdf_pages}:redact/2:{parser_versions()}"
        output_dir(self.home / "state", self.home)
        self.database = checked_output(self.home / "state/catalog.sqlite", self.home)
        with self.db() as db:
            db.executescript("""
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY, path TEXT UNIQUE, root TEXT, hash TEXT,
                size INTEGER, mtime_ns INTEGER, status TEXT, detail TEXT, seen TEXT, extractor TEXT);
              CREATE TABLE IF NOT EXISTS blobs (
                hash TEXT, extractor TEXT, text TEXT, status TEXT, detail TEXT,
                PRIMARY KEY(hash, extractor));
              CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED, path, text);
              CREATE TABLE IF NOT EXISTS edges (
                source_id TEXT, source_hash TEXT, target TEXT, target_hash TEXT NOT NULL DEFAULT '',
                relation TEXT, origin TEXT, UNIQUE(source_id, source_hash, target, target_hash, relation));
              CREATE TABLE IF NOT EXISTS externals (id TEXT PRIMARY KEY, uri TEXT);
              CREATE TABLE IF NOT EXISTS registrations (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, path TEXT, hash TEXT, status TEXT,
                coverage TEXT, inputs TEXT, gaps TEXT, created REAL);
              CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
              CREATE TABLE IF NOT EXISTS artifact_mentions (path TEXT, hash TEXT, question TEXT,
                PRIMARY KEY(path,hash,question));
            """)
            if "extractor" not in {row["name"] for row in db.execute("PRAGMA table_info(files)")}:
                db.execute("ALTER TABLE files ADD COLUMN extractor TEXT NOT NULL DEFAULT ''")
                db.execute("DELETE FROM search")
                db.execute("INSERT OR REPLACE INTO meta VALUES ('coverage',?)", (json.dumps({"complete": False, "reason": "cache_policy_changed; reindex required"}),))
            if "seq" not in {row["name"] for row in db.execute("PRAGMA table_info(registrations)")}:
                db.executescript("""ALTER TABLE registrations RENAME TO registrations_v1;
                    CREATE TABLE registrations (seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,path TEXT,hash TEXT,status TEXT,coverage TEXT,inputs TEXT,gaps TEXT,created REAL);
                    INSERT INTO registrations (id,path,hash,status,coverage,inputs,gaps,created)
                      SELECT id,path,hash,status,coverage,inputs,gaps,created FROM registrations_v1 ORDER BY rowid;
                    DROP TABLE registrations_v1;""")
            sql = db.execute("SELECT sql FROM sqlite_master WHERE name='edges'").fetchone()[0]
            if "UNIQUE(source_id,source_hash,target,target_hash,relation)" not in re.sub(r"\s+", "", sql):
                db.executescript("""ALTER TABLE edges RENAME TO edges_v1;
                    CREATE TABLE edges (source_id TEXT,source_hash TEXT,target TEXT,target_hash TEXT NOT NULL DEFAULT '',relation TEXT,origin TEXT,UNIQUE(source_id,source_hash,target,target_hash,relation));
                    INSERT OR IGNORE INTO edges SELECT source_id,source_hash,target,COALESCE(target_hash,''),relation,origin FROM edges_v1;
                    DROP TABLE edges_v1;""")

    @contextmanager
    def db(self):
        checked_output(self.database, self.home)
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def allowed(self, value):
        path = Path(value).resolve()
        if within(path, self.home):
            return False
        if path.name.lower() in SECRET_NAMES or path.name.lower().startswith(".env.") or path.suffix.lower() in {".key", ".pem", ".pfx", ".p12"}:
            return False
        return any(within(path, root) and not any(part.lower() in self.exclude_dirs for part in path.relative_to(root).parts[:-1])
                   for root in self.roots.values())

    def managed(self, value):
        base = (self.home / "artifacts/results").resolve()
        return within(base, self.home) and within(Path(value).resolve(), base)

    @staticmethod
    def ident(path):
        return sha256(os.path.normcase(str(path)).encode("utf-8")).hexdigest()[:24]

    def scan(self, progress=None, cancelled=None):
        try:
            with FileLease(self.home / "state/scanner.lease", self.home):
                with self.db() as db:
                    db.execute("INSERT OR REPLACE INTO meta VALUES ('coverage',?)", (json.dumps({"complete": False, "reason": "scan_in_progress"}),))
                return self._scan(progress, cancelled)
        except LeaseBusy:
            return {"status": "blocked", "complete": False, "reason": "another scanner holds the shared CLI/MCP lease"}

    def _scan(self, progress=None, cancelled=None):
        run = str(time.time_ns())
        counts = dict(files=0, extracted=0, unchanged=0, unsupported=0, partial=0,
                      failed=0, oversized=0, needs_ocr=0, excluded=0, parsed=0, missing_roots=[])
        errors = []
        for name, root in self.roots.items():
            if not root.is_dir():
                counts["missing_roots"].append(name)
                continue
            for directory, dirs, files in os.walk(root, followlinks=False, onerror=lambda e: errors.append(str(e))):
                base = Path(directory)
                kept = []
                for child in dirs:
                    path = base / child
                    try:
                        reparse = path.is_symlink() or bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name == "nt" else path.is_symlink()
                        skip = child.lower() in self.exclude_dirs or within(path.resolve(), self.home) or reparse
                    except OSError:
                        skip = True
                    if skip:
                        counts["excluded"] += 1
                    else:
                        kept.append(child)
                dirs[:] = kept
                for filename in files:
                    if cancelled and cancelled():
                        counts["cancelled"] = True
                        return self._finish_scan(counts, errors)
                    path = base / filename
                    low = filename.lower()
                    if low in SECRET_NAMES or low.startswith(".env.") or path.suffix.lower() in {".key", ".pem", ".pfx", ".p12"} or path.is_symlink() or not self.allowed(path):
                        counts["excluded"] += 1
                        continue
                    counts["files"] += 1
                    self._scan_file(path, name, run, counts)
                    if progress and counts["files"] % 100 == 0:
                        progress(dict(counts))
        # Deleted files stay in history, but cannot be returned as current search hits.
        with self.db() as db:
            if not errors and not counts["missing_roots"]:
                db.execute("DELETE FROM search WHERE id IN (SELECT id FROM files WHERE seen != ? AND root != 'pilot-results')", (run,))
                db.execute("UPDATE files SET status='missing' WHERE seen != ? AND root != 'pilot-results'", (run,))
        self._index_links()
        return self._finish_scan(counts, errors)

    def _scan_file(self, path, root, run, counts):
        ident, digest, text = self.ident(path), None, ""
        parser = self.extractor + ":" + path.suffix.lower()
        status, detail, size, mtime = "failed", "", 0, 0
        try:
            before = path.stat()
            size, mtime = before.st_size, before.st_mtime_ns
            if path.suffix.lower() not in SUPPORTED:
                status = "unsupported"
            elif size > self.max_file_bytes:
                status = "oversized"
            else:
                # Parse the exact immutable bytes that were hashed, never a second
                # read from a live corpus path. Cap growth while reading as well.
                with path.open("rb") as stream:
                    data = stream.read(self.max_file_bytes + 1)
                if len(data) > self.max_file_bytes:
                    raise OSError("input grew beyond size policy during snapshot")
                digest = sha256(data).hexdigest()
                with self.db() as db:
                    old = db.execute("SELECT * FROM blobs WHERE hash=? AND extractor=?", (digest, parser)).fetchone()
                if old:
                    text, status, detail = old["text"], old["status"], old["detail"]
                    counts["unchanged"] += 1
                else:
                    directory = output_dir(self.home / "tmp/snapshots", self.home)
                    with tempfile.NamedTemporaryFile(dir=directory, suffix=path.suffix, delete=False) as stream:
                        snapshot = Path(stream.name)
                        stream.write(data)
                    try:
                        result = extract(snapshot, self.max_text_chars, self.max_pdf_pages)
                    finally:
                        snapshot.unlink(missing_ok=True)
                    text, status, detail = result.text, result.status, result.detail
                    counts["parsed"] = counts.get("parsed", 0) + 1
                after = path.stat()
                if (after.st_size, after.st_mtime_ns) != (size, mtime):
                    status, detail, text = "failed", "input changed during extraction", ""
                elif not old:
                    if status == "extracted":
                        counts["extracted"] += 1
                    with self.db() as db:
                        db.execute("INSERT OR REPLACE INTO blobs VALUES (?,?,?,?,?)", (digest, parser, text, status, detail))
        except OSError as exc:
            detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        if status != "extracted":
            counts[status] = counts.get(status, 0) + 1
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO files (id,path,root,hash,size,mtime_ns,status,detail,seen,extractor) VALUES (?,?,?,?,?,?,?,?,?,?)", (ident, str(path), root, digest, size, mtime, status, detail, run, parser))
            db.execute("DELETE FROM search WHERE id=?", (ident,))
            if text:
                db.execute("INSERT INTO search VALUES (?,?,?)", (ident, str(path), text))

    def _finish_scan(self, counts, errors):
        complete = not (errors or counts.get("cancelled") or counts["missing_roots"] or any(counts[k] for k in ("unsupported", "partial", "failed", "oversized", "needs_ocr")))
        result = {**counts, "status": "cancelled" if counts.get("cancelled") else "completed" if complete else "partial",
                  "scan_completed": not counts.get("cancelled", False), "errors": errors[:30], "complete": complete,
                  "excluded_unit": "files_or_pruned_subtrees", "extractor": self.extractor}
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('coverage', ?)", (json.dumps(result),))
        return result

    def _index_links(self):
        from .linking import index_links
        return index_links(self)

    def refresh(self):
        """Migrate cached text/links without re-reading or re-parsing the corpus."""
        changed = 0
        with self.db() as db:
            cursor = db.execute("SELECT rowid,text,hash,extractor FROM blobs")
            for row in cursor:
                cleaned = redact(row["text"])
                if cleaned != row["text"]:
                    db.execute("UPDATE blobs SET text=? WHERE rowid=?", (cleaned, row["rowid"]))
                    db.execute("UPDATE search SET text=? WHERE id IN (SELECT id FROM files WHERE hash=? AND extractor=?)", (cleaned, row["hash"], row["extractor"]))
                    changed += 1
        return {"redacted_cached_blobs": changed, "links": self._index_links()}

    def lookup(self, question, limit=8):
        terms = re.findall(r"[\w]+", question, flags=re.UNICODE)[:16]
        with self.db() as db:
            coverage = db.execute("SELECT value FROM meta WHERE key='coverage'").fetchone()
            rows = []
            if terms:
                query = " OR ".join('"' + term + '"' for term in terms)
                rows = db.execute("SELECT f.*,search.text AS cached_text FROM search JOIN files f ON f.id=search.id WHERE search MATCH ? ORDER BY bm25(search) LIMIT ?", (query, max(10, min(int(limit), 20) * 10))).fetchall()
            report = json.loads(coverage[0]) if coverage else {"complete": False, "reason": "not indexed"}
        from .reuse import apply_reuse
        grouped = {}
        for row in rows:
            item = dict(row)
            cleaned = redact(item.pop("cached_text"))
            positions = [cleaned.casefold().find(term.casefold()) for term in terms]
            offset = max(0, min((pos for pos in positions if pos >= 0), default=0) - 120)
            item["excerpt"] = cleaned[offset:offset + 800]
            key = (item["hash"], item["extractor"]) if item["hash"] else item["id"]
            if key not in grouped:
                item["duplicate_locations"] = []
                grouped[key] = item
            elif len(grouped[key]["duplicate_locations"]) < 5:
                grouped[key]["duplicate_locations"].append(item["path"])
        candidates = list(grouped.values())[:max(1, min(int(limit), 20))]
        answer = {"action": "FOUND_CANDIDATES" if rows else ("NEW_WORK" if report.get("complete") else "INDEX_INCOMPLETE"), "question": question, "candidates": candidates, "coverage": report, "stale_reasons": []}
        return apply_reuse(self, answer)

    def register(self, artifact, *, coverage, inputs, status="draft", gaps=None, preserve_disposition=False):
        from .reuse import register
        return register(self, artifact, coverage=coverage, inputs=inputs, status=status, gaps=gaps,
                        preserve_disposition=preserve_disposition)

    def trace(self, artifact, depth=3):
        from .reuse import trace
        return trace(self, artifact, depth)
