"""One exclusive file lock, on Linux, macOS and Windows.

`fcntl` does not exist on Windows, and it was imported at the top of two
modules, so on Windows nothing started at all — not a feature that failed, the
whole program. portalocker is the same lock through the platform's own call:
`flock` on Unix, `LockFileEx` on Windows.

The semantics here are the ones the two callers already relied on, kept exactly:
an exclusive lock taken without blocking, retried until a deadline, and a clear
error when someone else is holding it. `timeout=0` fails at once instead of
waiting, which is what a scheduled run wants when a previous one is still going.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path

import portalocker
from portalocker.exceptions import BaseLockException


class LockBusy(RuntimeError):
    """Someone else holds the lock, and waiting did not help."""


@contextmanager
def exclusive(path: Path, timeout: float = 0.0, poll: float = 0.05):
    """Hold an exclusive lock on `path` for the duration of the block.

    The lock file is opened, not created and deleted: on Windows a locked file
    cannot be removed, and a lock whose release depends on unlinking is a lock
    that leaks the first time a process is killed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    deadline = time.monotonic() + max(0.0, timeout)
    try:
        while True:
            try:
                portalocker.lock(
                    fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
                break
            except BaseLockException:
                if time.monotonic() >= deadline:
                    raise LockBusy(str(path))
                time.sleep(poll)
        yield
    finally:
        try:
            portalocker.unlock(fh)
        finally:
            fh.close()
