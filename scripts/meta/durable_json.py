"""Small locked JSON read/modify/replace primitive (stdlib only)."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import time

try:
    from .daemon_safety import FileLease
except ImportError:
    from daemon_safety import FileLease


class StoreCorruption(ValueError):
    """Stored JSON is malformed or has an unsupported shape."""


@contextmanager
def bounded_lease(path, timeout=5.0):
    """Keep the shared lock inode; always close an acquired kernel handle."""
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
        raise ValueError('lock timeout must be finite and nonnegative')
    lease = FileLease(path)
    deadline = time.monotonic() + timeout
    try:
        while not lease.acquire():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'lock deadline exceeded: {path}')
            time.sleep(min(0.01, remaining))
        yield lease
    finally:
        # FileLease.close can itself fail while unlocking on Windows.
        handle = lease.handle
        try:
            lease.close()
        finally:
            if handle is not None and not handle.closed:
                handle.close()
            lease.handle = None


def _reject_constant(value):
    raise ValueError(f'non-finite JSON number: {value}')


def storage_identity(path):
    """Pin parent/relative spelling; reject leaf aliases replacement would split.

    Requires a stable namespace: this is not protection against concurrent
    external symlink/hardlink creation or renaming of the store/lock files.
    """
    path = Path(path)
    path = path.parent.resolve() / path.name
    try:
        identity = path.lstat()
    except FileNotFoundError:
        return path
    if stat.S_ISLNK(identity.st_mode):
        raise ValueError(f'unsupported storage file symlink: {path}')
    if identity.st_nlink > 1:
        raise ValueError(f'unsupported storage hardlink: {path}')
    return path.resolve()


def read_json(path, default_factory, validate):
    path = storage_identity(path)
    try:
        text = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return default_factory()
    except UnicodeError as exc:
        raise StoreCorruption(f'invalid UTF-8 store: {path}') from exc
    try:
        data = json.loads(text, parse_constant=_reject_constant)
        validate(data)
        return data
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise StoreCorruption(f'invalid JSON store: {path}: {exc}') from exc


def update_json(path, default_factory, validate, mutate, timeout=5.0):
    """Read latest state under the lock; never publish a stale caller cache."""
    path = storage_identity(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with bounded_lease(path.with_name(path.name + '.lock'), timeout):
        data = read_json(path, default_factory, validate)
        mutate(data)
        validate(data)
        text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                             dir=path.parent, prefix=path.name + '.',
                                             suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return data
