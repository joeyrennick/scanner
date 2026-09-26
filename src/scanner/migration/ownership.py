"""OS-backed ownership outside a data root that may be replaced during restore."""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import unicodedata


class DataRootInUse(RuntimeError):
    pass


def root_identity(root: Path) -> str:
    # macOS realpath resolves symlinks but does not normalize filename casing.
    # Conservatively serialize case-only aliases even on case-sensitive volumes.
    return unicodedata.normalize("NFC", str(root.resolve())).casefold()


class DataRootOwnership:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if self.root == self.root.parent:
            raise ValueError("A filesystem root cannot be an application data root")
        digest = hashlib.sha256(root_identity(self.root).encode()).hexdigest()
        self.control_directory = self.root.parent / ".scanner-ownership" / digest
        self.lock_path = self.control_directory / "owner.lock"
        self.restore_marker = self.control_directory / "restore.json"
        self._fd: int | None = None

    def __enter__(self):
        if self._fd is not None:
            raise RuntimeError("Ownership is already held by this handle")
        self.control_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise DataRootInUse(
                f"Data root is in use: {self.root}. Stop its owner or choose an isolated root."
            ) from None
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def __exit__(self, *_):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        # Never unlink the lock: replacement would allow two live owners.
