"""Pilot-owned output paths: reject escapes/reparse points BEFORE any I/O."""
from pathlib import Path
import os
import stat
import uuid


def checked_output(path, root):
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    if not path.is_relative_to(root):
        raise ValueError("output escapes the approved pilot directory")
    for part in [*reversed(path.parents), path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise ValueError("output path contains a symbolic link or reparse point")
    return path


def output_dir(path, root):
    path = checked_output(path, root)
    path.mkdir(parents=True, exist_ok=True)
    return checked_output(path, root)


def write_text(path, text, root):
    path = checked_output(path, root)
    data = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return 0
    output_dir(path.parent, root)
    temporary = checked_output(path.parent / f".pilot-{uuid.uuid4().hex}.tmp", root)
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        checked_output(path, root)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return 1
