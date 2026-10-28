"""OS-released exclusion: stale files do not imply an active owner after a crash."""
import os

from .paths import checked_output, output_dir


class LeaseBusy(Exception):
    pass


class FileLease:
    def __init__(self, path, root):
        self.path, self.root, self.fd = checked_output(path, root), root, None

    def __enter__(self):
        output_dir(self.path.parent, self.root)
        self.fd = os.open(checked_output(self.path, self.root), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.fstat(self.fd).st_size == 0:
                os.write(self.fd, b"0")
            os.lseek(self.fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self.fd)
            self.fd = None
            raise LeaseBusy("another process/thread owns the operation") from exc
        return self

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)  # OS releases the byte/flock lock, including on crash.
            self.fd = None
