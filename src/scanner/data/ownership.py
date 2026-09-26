"""Shared in-process leases over the cross-process data-root ownership lock."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
import sqlite3
import threading
import weakref

from scanner.config.paths import ApplicationPaths
from scanner.migration.ownership import DataRootOwnership, root_identity

_mutex = threading.RLock()
_leases: weakref.WeakValueDictionary[str, OwnershipLease] = weakref.WeakValueDictionary()


class OwnershipLease:
    def __init__(self, root: Path):
        self.pid = os.getpid()
        self.guard = DataRootOwnership(root)
        self.guard.__enter__()
        try:
            from scanner.migration.activation import recover_activation_locked
            recover_activation_locked(self.guard)
        except BaseException:
            self.guard.__exit__()
            raise
        if self.guard.restore_marker.exists():
            self.guard.__exit__()
            raise RuntimeError("Data root has a recovery marker; complete reviewed activation before starting the runtime")
        if (self.guard.root / "migration-pending.json").exists():
            self.guard.__exit__()
            raise RuntimeError(
                "Legacy migration is pending. Complete the verified staged import before starting the scanner; "
                "do not remove migration-pending.json to bypass this check."
            )

    def __del__(self):
        guard = getattr(self, "guard", None)
        if guard is not None:
            guard.__exit__()


def acquire_root(root: Path) -> OwnershipLease:
    key = root_identity(root)
    with _mutex:
        lease = _leases.get(key)
        if lease is not None and lease.pid != os.getpid():
            # A forked process must not use its parent's SQLite ownership/handles.
            raise RuntimeError("Database access after fork requires a new independent backend process")
        if lease is None:
            lease = OwnershipLease(root)
            _leases[key] = lease
        return lease


def acquire_database(path: str | Path) -> OwnershipLease:
    return acquire_root(ApplicationPaths.resolve().ownership_root(path))


class OwnedConnection(sqlite3.Connection):
    """Close handles deterministically at context exit, retaining ownership until close."""
    ownership: OwnershipLease | None = None

    def close(self):
        try:
            super().close()
        finally:
            self.ownership = None

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect(path: str | Path, *, timeout: float = 30, kind: str | None = None) -> OwnedConnection:
    ownership = acquire_database(path)
    connection = sqlite3.connect(path, timeout=timeout, factory=OwnedConnection)
    connection.ownership = ownership
    try:
        from scanner.data.schema import validate_version
        validate_version(connection, kind)
    except BaseException:
        connection.close()
        raise
    return connection


@asynccontextmanager
async def application_lifespan(_app):
    """Hold the root even between requests and while background jobs run."""
    ownership = acquire_root(ApplicationPaths.resolve().root)
    try:
        yield
    finally:
        del ownership


def owned_application(function):
    """CLI lifetime guard, acquired before constructors or output writes."""
    @wraps(function)
    def run(*args, **kwargs):
        ownership = acquire_root(ApplicationPaths.resolve().root)
        try:
            return function(*args, **kwargs)
        finally:
            del ownership
    return run
