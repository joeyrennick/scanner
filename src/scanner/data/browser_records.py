"""Durable browser business records; original localStorage is never modified here."""
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3

from scanner.data.ownership import acquire_database, connect
from scanner.data.schema import APPLICATION_IDS, SCHEMA_VERSION, validate_version
from scanner.migration.browser import COLLECTIONS, validate_browser_export


class RevisionConflict(ValueError):
    pass


def validate_record(collection: str, record: dict):
    if collection not in COLLECTIONS:
        raise ValueError("Unsupported business collection")
    payload = {"source": {"origin": "http://record-validation.invalid", "exportId": "validation",
                          "exportedAt": "validation", "writePauseConfirmed": True},
               "collections": {name: [record] if name == collection else [] for name in COLLECTIONS},
               "counts": {name: int(name == collection) for name in COLLECTIONS}}
    serialized = json.dumps(payload, allow_nan=False)
    validate_browser_export(json.dumps({"format": "swing-scanner.browser-export", "version": 1,
                                       "payloadJson": serialized,
                                       "sha256": hashlib.sha256(serialized.encode()).hexdigest()}).encode())


def initialize_browser_schema(database: sqlite3.Connection):
    validate_version(database, "browser")
    if database.execute("PRAGMA user_version").fetchone()[0] == 0:
        if database.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
            raise ValueError("Browser repository requires an empty database or supported schema")
        database.execute("CREATE TABLE business_records (collection TEXT NOT NULL, record_id TEXT NOT NULL, "
                         "payload_json TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision > 0), "
                         "updated_at TEXT NOT NULL, source_origin TEXT, PRIMARY KEY(collection, record_id))")
        # Tombstones keep revisions monotonic across delete/re-create (no ABA overwrite).
        database.execute("CREATE TABLE record_revisions (collection TEXT NOT NULL, record_id TEXT NOT NULL, "
                         "revision INTEGER NOT NULL, PRIMARY KEY(collection, record_id))")
        database.execute(f"PRAGMA application_id={APPLICATION_IDS['browser']}")
        database.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    expected = {"business_records", "record_revisions"}
    actual = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if actual != expected:
        raise ValueError("Unsupported browser repository schema")


def import_browser_snapshot(database: sqlite3.Connection, browser: dict):
    initialize_browser_schema(database)
    for collection, records in browser["collections"].items():
        for record in records:
            validate_record(collection, record)
            database.execute("INSERT INTO business_records VALUES (?, ?, ?, 1, ?, ?)",
                             (collection, record["id"], json.dumps(record, sort_keys=True, allow_nan=False),
                              browser["source"]["exportedAt"], browser["source"]["origin"]))
            database.execute("INSERT INTO record_revisions VALUES (?, ?, 1)", (collection, record["id"]))


class BrowserRecordStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ownership = acquire_database(self.db_path)
        self.db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._connect() as database:
            initialize_browser_schema(database)

    def _connect(self):
        return connect(self.db_path, kind="browser")

    def list(self, collection: str) -> list[dict]:
        if collection not in COLLECTIONS:
            raise ValueError("Unsupported business collection")
        with self._connect() as database:
            return [{"record": json.loads(row[0]), "revision": row[1], "updated_at": row[2]}
                    for row in database.execute("SELECT payload_json, revision, updated_at FROM business_records "
                                                "WHERE collection=? ORDER BY record_id", (collection,))]

    def put(self, collection: str, record: dict, expected_revision: int) -> dict:
        validate_record(collection, record)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Expected revision must be a nonnegative integer")
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            current = database.execute("SELECT revision FROM record_revisions WHERE collection=? AND record_id=?",
                                       (collection, record["id"])).fetchone()
            if (current[0] if current else 0) != expected_revision:
                raise RevisionConflict("Record changed; refresh before saving")
            revision, now = expected_revision + 1, datetime.now(UTC).isoformat()
            database.execute("INSERT INTO business_records VALUES (?, ?, ?, ?, ?, NULL) "
                             "ON CONFLICT(collection,record_id) DO UPDATE SET payload_json=excluded.payload_json, "
                             "revision=excluded.revision, updated_at=excluded.updated_at",
                             (collection, record["id"], json.dumps(record, sort_keys=True, allow_nan=False), revision, now))
            database.execute("INSERT INTO record_revisions VALUES (?, ?, ?) ON CONFLICT(collection,record_id) "
                             "DO UPDATE SET revision=excluded.revision", (collection, record["id"], revision))
        return {"record": record, "revision": revision, "updated_at": now}

    def get(self, collection: str, record_id: str) -> dict:
        if collection not in COLLECTIONS:
            raise ValueError("Unsupported business collection")
        with self._connect() as database:
            row = database.execute("SELECT payload_json, revision, updated_at FROM business_records "
                                   "WHERE collection=? AND record_id=?", (collection, record_id)).fetchone()
            if row:
                return {"record": json.loads(row[0]), "revision": row[1], "updated_at": row[2]}
            tombstone = database.execute("SELECT revision FROM record_revisions WHERE collection=? AND record_id=?",
                                         (collection, record_id)).fetchone()
            return {"record": None, "revision": tombstone[0] if tombstone else 0, "updated_at": None}

    def delete(self, collection: str, record_id: str, expected_revision: int) -> dict:
        if collection not in COLLECTIONS or type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("A supported collection and positive expected revision are required")
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            row = database.execute("SELECT revision FROM business_records WHERE collection=? AND record_id=?",
                                   (collection, record_id)).fetchone()
            if row is None or row[0] != expected_revision:
                raise RevisionConflict("Record changed or deleted; refresh before deleting")
            database.execute("DELETE FROM business_records WHERE collection=? AND record_id=?", (collection, record_id))
            database.execute("UPDATE record_revisions SET revision=? WHERE collection=? AND record_id=?",
                             (expected_revision + 1, collection, record_id))
        return {"deleted": True, "revision": expected_revision + 1}
