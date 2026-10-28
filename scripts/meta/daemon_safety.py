"""Fail-closed execution gate and OS-owned daemon lifecycle (no PID-only trust)."""
import json
import os
import time
from pathlib import Path


def execute_verified(branches, executor=None, verifier=None):
    """Only an explicitly installed independent verifier may authorize recovery.

    verifier(branches, result) must check real merge/test evidence, not merely
    echo the executor's boolean. No production verifier is installed by default.
    """
    blocked = {'merged': False, 'status': 'blocked',
               'result': 'verified executor and merge evidence required'}
    if (not callable(executor) or not callable(verifier) or executor is verifier
            or not isinstance(branches, list) or not branches
            or not all(isinstance(branch, str) and branch.strip() for branch in branches)):
        return blocked
    try:
        result = executor(branches)
        if (isinstance(result, dict) and result.get('merged') is True
                and isinstance(result.get('evidence'), dict) and result['evidence']
                and verifier(branches, result) is True):
            return {'merged': True, 'status': 'merged',
                    'result': str(result.get('result', 'verified merge')),
                    'evidence': result['evidence']}
    except Exception as exc:
        return {**blocked, 'result': f'execution/verification failed: {type(exc).__name__}'}
    return blocked


class FileLease:
    """Exclusive kernel lock; keep the file/handle, never unlink lock files."""
    def __init__(self, path):
        self.path = Path(path)
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                if not handle.read(1):
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        except BaseException:
            # The local handle is not yet published to self.handle.
            handle.close()
            raise
        self.handle = handle
        return True

    def close(self):
        if self.handle is not None:
            if os.name == 'nt':
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            self.handle.close()
            self.handle = None


class DaemonLease:
    def __init__(self, state_dir, orchestrator):
        self.state_dir = Path(state_dir).resolve()
        self.orchestrator = orchestrator
        self.lock = FileLease(self.state_dir / f'{orchestrator}_daemon.lock')
        self.identity_file = self.state_dir / f'{orchestrator}_daemon.identity.json'

    def heartbeat(self, token):
        if self.lock.handle is None:
            raise RuntimeError('daemon lease not owned')
        identity = {'pid': os.getpid(), 'token': token,
                    'script': str(Path(__file__).with_name('meta_daemon.py').resolve()),
                    'state_dir': str(self.state_dir), 'orchestrator': self.orchestrator,
                    'heartbeat': time.time()}
        temporary = self.identity_file.with_suffix('.tmp')
        temporary.write_text(json.dumps(identity), encoding='utf-8')
        temporary.replace(self.identity_file)

    def live(self, max_age, token=None):
        probe = FileLease(self.lock.path)
        if probe.acquire():
            probe.close()
            return False
        try:
            identity = json.loads(self.identity_file.read_text(encoding='utf-8'))
            age = time.time() - identity['heartbeat']
            return (identity['orchestrator'] == self.orchestrator
                    and identity['state_dir'] == str(self.state_dir)
                    and identity['script'] == str(Path(__file__).with_name('meta_daemon.py').resolve())
                    and isinstance(identity['pid'], int) and identity['pid'] > 0
                    and bool(identity['token'])
                    and (token is None or identity['token'] == token)
                    and 0 <= age <= max_age)
        except (OSError, ValueError, KeyError, TypeError):
            return False
