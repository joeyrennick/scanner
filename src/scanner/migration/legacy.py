"""Read-only discovery and SQLite snapshots, without legacy store constructors."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

BUSINESS_TABLES = {"scanner_runs", "scanner_results", "saved_watchlists", "saved_watchlist_items"}
CACHE_TABLES = {"price_bars", "cache_fetches", "fundamental_analysis_cache", "sec_fundamentals_cache"}
KNOWN_TABLES = BUSINESS_TABLES | CACHE_TABLES | {"secrets", "sqlite_sequence"}
REPORT_DIRECTORIES = {"daily_reports", "fundamental_reports", "watchlist_reports"}


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@contextmanager
def read_database(path: Path):
    path = path.resolve(strict=True)
    with path.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise ValueError(f"Not a valid existing SQLite database: {path.name}")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        yield connection
    finally:
        connection.close()


def tables(connection: sqlite3.Connection) -> dict[str, str]:
    return dict(connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"))


def check_database(connection: sqlite3.Connection):
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("SQLite foreign-key check failed")


def record_manifest(connection: sqlite3.Connection, names: set[str]) -> dict:
    result = {}
    schema = tables(connection)
    for name in sorted(names & schema.keys()):
        # Row hashes are sorted, making reconciliation independent of physical row order.
        hashes = []
        for row in connection.execute(f"SELECT * FROM {quote(name)}"):
            encoded = json.dumps(row, ensure_ascii=True, separators=(",", ":"),
                                 default=lambda value: {"bytes": value.hex()}).encode()
            hashes.append(hashlib.sha256(encoded).hexdigest())
        digest = hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()
        result[name] = {"count": len(hashes), "sha256": digest,
                        "schema_sha256": hashlib.sha256(schema[name].encode()).hexdigest()}
    return result


def source_files(root: Path) -> list[dict]:
    root = root.resolve(strict=True)
    result = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Review symlink before backup: {path.relative_to(root)}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        kind = "unclassified"
        if relative.parts[0] == "logs":
            kind = "disposable-log"
        elif relative.name in {"market_data_cache.sqlite-wal", "market_data_cache.sqlite-shm"}:
            kind = "sqlite-bookkeeping"
        elif str(relative) == "market_data_cache.sqlite":
            kind = "mixed-database"
        elif str(relative) == "market_data_cache.key":
            kind = "credential-key"
        elif str(relative) == "scanner_runs.sqlite3" and path.stat().st_size == 0:
            kind = "empty-unused-artifact"
        elif str(relative) in {"watchlist.csv", "trade_journal.csv", "trade_journal_report.html"}:
            kind = "durable-file"
        elif relative.parts[0] in REPORT_DIRECTORIES and path.suffix in {".pdf", ".json", ".html", ".csv"}:
            kind = "durable-report"
        result.append({"path": str(relative), "kind": kind, "bytes": path.stat().st_size,
                       "uid": path.stat().st_uid})
    return result


def inventory(root: Path) -> dict:
    files = source_files(root)
    databases = {}
    for item in files:
        if item["kind"] != "mixed-database":
            continue
        with read_database(root / item["path"]) as connection:
            schema = tables(connection)
            databases[item["path"]] = {
                "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
                "tables": {name: {
                    "kind": ("business" if name in BUSINESS_TABLES else "cache" if name in CACHE_TABLES
                             else "secret" if name == "secrets" else "internal" if name == "sqlite_sequence" else "unclassified"),
                    "count": connection.execute(f"SELECT COUNT(*) FROM {quote(name)}").fetchone()[0],
                    "columns": [row[1] for row in connection.execute(f"PRAGMA table_info({quote(name)})")],
                } for name in sorted(schema)},
            }
    return {"source_root": str(root.resolve()), "files": files, "databases": databases,
            "browser_records": "Original-origin export required; not inspected from browser profile files."}


def require_stopped_source(root: Path):
    """Legacy applications do not yet honor ownership; reject ANY open source file."""
    result = subprocess.run(["/usr/sbin/lsof", "-t", "+D", str(root)], capture_output=True,
                            text=True, timeout=15)
    if result.returncode not in (0, 1) or result.stderr.strip():
        raise ValueError("Could not verify stopped source processes; close scanner processes and retry")
    if result.stdout.strip():
        raise ValueError("Source files are open. Stop the legacy backend, CLI jobs, and database tools before backup")


def snapshot(source: sqlite3.Connection, target: sqlite3.Connection):
    deadline = time.monotonic() + 60

    def progress(_status, _remaining, _total):
        if time.monotonic() > deadline:
            raise TimeoutError("SQLite snapshot timed out; verify source writers are stopped")

    source.backup(target, pages=256, progress=progress, sleep=0.05)
