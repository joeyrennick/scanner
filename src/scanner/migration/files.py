"""Private, durable file operations for maintenance journals and staged files."""
import json
import os
from pathlib import Path
from uuid import uuid4


def json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def fsync_directory(path: Path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_new(path: Path, data: bytes):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(path.parent)


def write_marker(path: Path, value: dict):
    temporary = path.with_name(f"marker-{uuid4().hex}.tmp")
    write_new(temporary, json_bytes(value))
    os.replace(temporary, path)
    fsync_directory(path.parent)


def move_new(source: Path, destination: Path):
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Refusing to replace an existing migration target: {destination.name}")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    source.rename(destination)
    fsync_directory(source.parent)
    fsync_directory(destination.parent)
