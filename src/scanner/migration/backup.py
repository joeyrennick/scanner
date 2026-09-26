"""Coordinated backups and isolated restore verification, never active-store import."""
from __future__ import annotations

import base64
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from scanner.migration.browser import MAX_BROWSER_BYTES, validate_browser_export
from scanner.migration.legacy import (
    BUSINESS_TABLES, CACHE_TABLES, KNOWN_TABLES, check_database, quote,
    read_database, record_manifest, require_stopped_source, sha256_file, snapshot,
    source_files, tables,
)
from scanner.migration.ownership import DataRootOwnership, root_identity
from scanner.security.secret_store import MASTER_KEY_BYTES, _decrypt
from scanner.config.settings import settings
from scanner.config.application import effective_sec_identity

ARCHIVE_HEADER = b"SCANNER-RECOVERY-1\x00"
MAX_RECOVERY_BYTES = 16 * 1024 * 1024


def _json(value) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def _fsync_directory(path: Path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_new(path: Path, data: bytes):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(path.parent)


def _write_marker(path: Path, value: dict):
    staged = path.with_name(f"restore-{uuid4().hex}.tmp")
    _write_new(staged, _json(value))
    os.replace(staged, path)
    _fsync_directory(path.parent)


def _cipher(passphrase: str, salt: bytes) -> Fernet:
    if len(passphrase) < 16 or len(passphrase) > 1024:
        raise ValueError("Use a recovery passphrase of 16–1024 characters, saved separately from the backup")
    key = Argon2id(salt=salt, length=32, iterations=3, lanes=4, memory_cost=65536).derive(passphrase.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def _encrypt_recovery(payload: dict, passphrase: str) -> bytes:
    salt = os.urandom(16)
    plaintext = _json(payload)
    if len(plaintext) > MAX_RECOVERY_BYTES // 2:
        raise ValueError("Credential recovery payload exceeds the supported limit")
    return ARCHIVE_HEADER + salt + _cipher(passphrase, salt).encrypt(plaintext)


def _decrypt_recovery(raw: bytes, passphrase: str) -> dict:
    if len(raw) > MAX_RECOVERY_BYTES or not raw.startswith(ARCHIVE_HEADER):
        raise ValueError("Unsupported credential recovery archive")
    offset = len(ARCHIVE_HEADER)
    try:
        payload = json.loads(_cipher(passphrase, raw[offset:offset + 16]).decrypt(raw[offset + 16:]))
    except (InvalidToken, ValueError):
        raise ValueError("Credential archive could not be authenticated; check the recovery passphrase") from None
    if set(payload) != {"version", "database", "key"} or payload["version"] != 1:
        raise ValueError("Unsupported credential recovery payload")
    return payload


def _validate_credentials(payload: dict) -> int:
    key = base64.b64decode(payload["key"], altchars=b"-_", validate=True)
    if len(key) != MASTER_KEY_BYTES:
        raise ValueError("The original credential key is invalid; no replacement key was created")
    with closing(sqlite3.connect(":memory:")) as database:
        database.deserialize(base64.b64decode(payload["database"], validate=True))
        database.execute("PRAGMA trusted_schema=OFF")
        if set(tables(database)) != {"secrets"}:
            raise ValueError("Credential recovery database contains unexpected tables")
        check_database(database)
        rows = database.execute("SELECT encrypted_value FROM secrets").fetchall()
        for (encrypted,) in rows:
            _decrypt(encrypted, key)  # Validate only; never return/log secret values or call providers.
        return len(rows)


def _credential_projection(database: sqlite3.Connection, key_path: Path) -> dict | None:
    if "secrets" not in tables(database):
        return None
    rows = database.execute("SELECT * FROM secrets").fetchall()
    if not rows:
        return None
    # The key must already exist. Never instantiate SQLiteSecretStore on a source.
    if not key_path.is_file() or key_path.is_symlink() or key_path.stat().st_size > 1024:
        raise ValueError("The matching legacy credential key is missing or invalid")
    with closing(sqlite3.connect(":memory:")) as secret_database:
        secret_database.execute(tables(database)["secrets"])
        secret_database.executemany("INSERT INTO secrets VALUES (?, ?, ?, ?)", rows)
        secret_database.commit()
        payload = {"version": 1, "database": base64.b64encode(secret_database.serialize()).decode(),
                   "key": key_path.read_text().strip()}
    _validate_credentials(payload)
    return payload


def _disjoint(left: Path, right: Path):
    left = Path(root_identity(left))
    right = Path(root_identity(right))
    if left == right or left in right.parents or right in left.parents:
        raise ValueError("Source, backup, and restore roots must be separate, non-nested directories")


def create_backup(source_root: Path, destination: Path, browser_export: Path,
                  passphrase: str, *, source_writers_stopped: bool) -> dict:
    if not source_writers_stopped:
        raise ValueError("Stop source writers and keep browser editing paused before backup")
    source_root = source_root.resolve(strict=True)
    destination = destination.resolve()
    _disjoint(source_root, destination)
    if browser_export.stat().st_size > MAX_BROWSER_BYTES * 2:
        raise ValueError("Browser export is too large")
    browser_raw = browser_export.read_bytes()
    browser = validate_browser_export(browser_raw)
    with DataRootOwnership(source_root), DataRootOwnership(destination):
        require_stopped_source(source_root)
        items = source_files(source_root)
        unknown = [item["path"] for item in items if item["kind"] == "unclassified"]
        if unknown:
            raise ValueError("Classify these source files before backup: " + ", ".join(unknown))
        db_path = source_root / "market_data_cache.sqlite"
        durable_items = [item for item in items if item["kind"] in {"durable-file", "durable-report"}]
        original_hashes = {item["path"]: sha256_file(source_root / item["path"]) for item in durable_items}
        key_path = db_path.with_suffix(".key")
        key_digest = sha256_file(key_path) if key_path.is_file() else None
        with read_database(db_path) as source, closing(sqlite3.connect(":memory:")) as database:
            snapshot(source, database)
            schema = tables(database)
            version = database.execute("PRAGMA user_version").fetchone()[0]
            if set(schema) - KNOWN_TABLES or version != 0:
                raise ValueError("Unsupported legacy schema; review it before migration")
            if database.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchone():
                raise ValueError("Review source views/triggers before backup")
            check_database(database)
            business_records = record_manifest(database, BUSINESS_TABLES)
            original_records = record_manifest(database, BUSINESS_TABLES | {"secrets"})
            credentials = _credential_projection(database, key_path)
            archive = _encrypt_recovery(credentials, passphrase) if credentials else None
            # Work only in the SQLite snapshot. VACUUM removes secret/cache free pages.
            database.execute("PRAGMA foreign_keys=OFF")
            for name in sorted((CACHE_TABLES | {"secrets"}) & schema.keys()):
                database.execute(f"DROP TABLE {quote(name)}")
            database.commit()
            database.execute("VACUUM")
            check_database(database)
            if record_manifest(database, BUSINESS_TABLES) != business_records:
                raise ValueError("Business record reconciliation failed")
            # Exclusive creation preserves any previous backup, including a partial one.
            destination.mkdir(mode=0o700)
            _write_new(destination / "data/business.sqlite", database.serialize())
        _write_new(destination / "browser-export.json", browser_raw)
        # These typed settings contain no provider keys. This captures the backup
        # process configuration; historical run-specific settings remain in SQLite.
        _write_new(destination / "configuration/scanner-settings.json", _json({
            "version": 1, "source": "backup-process-effective-settings",
            "settings": {**asdict(settings), "sec_user_agent": effective_sec_identity(settings.sec_user_agent).user_agent},
        }))
        if archive:
            _write_new(destination / "credential-recovery.enc", archive)
        for item in durable_items:
            relative = item["path"]
            _write_new(destination / "legacy-files" / relative, (source_root / relative).read_bytes())
            if sha256_file(destination / "legacy-files" / relative) != original_hashes[relative]:
                raise ValueError("Source files changed during backup; keep writers stopped and retry")
        with read_database(db_path) as source:
            if record_manifest(source, BUSINESS_TABLES | {"secrets"}) != original_records:
                raise ValueError("Source records changed during backup; stop writers and retry")
        # Opening a WAL database read-only may create/recreate its SHM/WAL
        # bookkeeping. Logical rows/schema are reconciled above; these transient
        # files are not evidence of a source writer or durable data changes.
        def stable_inventory(entries):
            return [item for item in entries if item["kind"] != "sqlite-bookkeeping"]

        if stable_inventory(source_files(source_root)) != stable_inventory(items) or any(
            sha256_file(source_root / relative) != digest for relative, digest in original_hashes.items()
        ) or (sha256_file(key_path) if key_path.is_file() else None) != key_digest:
            raise ValueError("Source inventory changed during backup; stop writers and retry")
        require_stopped_source(source_root)
        files = {str(path.relative_to(destination)): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
                 for path in sorted(destination.rglob("*")) if path.is_file()}
        manifest = {
            "format": "swing-scanner.legacy-backup", "version": 1, "backup_id": uuid4().hex,
            "created_at": datetime.now(UTC).isoformat(), "source_root": str(source_root),
            "source_user_version": version, "source_files": items, "files": files,
            "business_records": business_records, "browser_source": browser["source"],
            "browser_counts": browser["counts"], "credential_count": _validate_credentials(credentials) if credentials else 0,
            "status": "captured-awaiting-isolated-restore",
        }
        # Written last: partial captures have no usable manifest.
        _write_new(destination / "manifest.json", _json(manifest))
        return manifest


def verify_backup(backup_root: Path, restore_root: Path, passphrase: str) -> dict:
    backup_root = backup_root.resolve(strict=True)
    restore_root = restore_root.resolve()
    _disjoint(backup_root, restore_root)
    with DataRootOwnership(backup_root), DataRootOwnership(restore_root) as owner:
        if restore_root.exists():
            raise ValueError("Restore verification requires a new, unused root; existing data is never overwritten")
        manifest_path = backup_root / "manifest.json"
        if manifest_path.stat().st_size > 5 * 1024 * 1024 or manifest_path.is_symlink():
            raise ValueError("Invalid backup manifest")
        manifest = json.loads(manifest_path.read_bytes())
        if manifest.get("format") != "swing-scanner.legacy-backup" or manifest.get("version") != 1:
            raise ValueError("Unsupported backup format")
        _disjoint(Path(manifest["source_root"]).resolve(), restore_root)
        files = manifest["files"]
        if not isinstance(files, dict) or len(files) > 10000:
            raise ValueError("Invalid backup file manifest")
        for relative, expected in files.items():
            path = PurePosixPath(relative)
            if (path.is_absolute() or ".." in path.parts or not path.parts or "\\" in relative
                    or str(path) != relative or relative == "manifest.json"):
                raise ValueError("Unsafe path in backup manifest")
            candidate = backup_root / relative
            if any(part.is_symlink() for part in [candidate, *candidate.parents] if part != backup_root.parent):
                raise ValueError("Symlinks are not allowed in backups")
            if candidate.stat().st_size != expected["bytes"] or sha256_file(candidate) != expected["sha256"]:
                raise ValueError("Backup file checksum mismatch")
        actual_files = {str(path.relative_to(backup_root)) for path in backup_root.rglob("*") if path.is_file()}
        if actual_files != set(files) | {"manifest.json"} or not {"data/business.sqlite", "browser-export.json"} <= files.keys():
            raise ValueError("Backup contains missing or unexpected files")
        browser = validate_browser_export((backup_root / "browser-export.json").read_bytes())
        if browser["counts"] != manifest["browser_counts"] or browser["source"] != manifest["browser_source"]:
            raise ValueError("Browser reconciliation failed")
        credential_count = 0
        if "credential-recovery.enc" in files:
            credential_count = _validate_credentials(_decrypt_recovery(
                (backup_root / "credential-recovery.enc").read_bytes(), passphrase))
        if credential_count != manifest["credential_count"]:
            raise ValueError("Credential count mismatch")
        marker = {"backup_id": manifest["backup_id"], "state": "restoring",
                  "companion_enabled": False, "pairing_reset_required": True}
        _write_marker(owner.restore_marker, marker)
        restore_root.mkdir(mode=0o700)
        for relative in files:
            if relative == "credential-recovery.enc":
                continue  # Decrypted credential recovery material stays in memory.
            _write_new(restore_root / relative, (backup_root / relative).read_bytes())
            if sha256_file(restore_root / relative) != files[relative]["sha256"]:
                raise ValueError("Restored file checksum mismatch")
        with read_database(restore_root / "data/business.sqlite") as database:
            check_database(database)
            if set(tables(database)) - (BUSINESS_TABLES | {"sqlite_sequence"}):
                raise ValueError("Restored business database contains unexpected tables")
            if record_manifest(database, BUSINESS_TABLES) != manifest["business_records"]:
                raise ValueError("Restored business records do not reconcile")
            if database.execute("PRAGMA user_version").fetchone()[0] != manifest["source_user_version"]:
                raise ValueError("Restored database version mismatch")
        # A real SQLite restore of browser records, preserving source and stable IDs.
        with closing(sqlite3.connect(restore_root / "data/browser-records.sqlite")) as database:
            database.execute("PRAGMA user_version=1")
            database.execute("CREATE TABLE browser_records (origin TEXT NOT NULL, collection TEXT NOT NULL, "
                             "record_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(origin, collection, record_id))")
            for collection, records in browser["collections"].items():
                for record in records:
                    database.execute("INSERT INTO browser_records VALUES (?, ?, ?, ?)",
                                     (browser["source"]["origin"], collection, record["id"], _json(record).decode()))
            database.commit()
            check_database(database)
        os.chmod(restore_root / "data/browser-records.sqlite", 0o600)
        with read_database(restore_root / "data/browser-records.sqlite") as database:
            for collection, records in browser["collections"].items():
                restored = [json.loads(row[0]) for row in database.execute(
                    "SELECT payload_json FROM browser_records WHERE collection=? ORDER BY record_id", (collection,))]
                if restored != sorted(records, key=lambda row: row["id"]):
                    raise ValueError("Restored browser records do not reconcile")
        verification = {"backup_id": manifest["backup_id"], "verified_at": datetime.now(UTC).isoformat(),
                        "business_records": manifest["business_records"], "browser_counts": browser["counts"],
                        "credentials_decrypted": credential_count, "files_verified": len(files),
                        "active_store_imported": False}
        _write_new(restore_root / "verification.json", _json(verification))
        _write_marker(owner.restore_marker, {**marker, "state": "verified-isolated-restore"})
        return verification
