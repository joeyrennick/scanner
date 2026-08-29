from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any


SEC_CACHE_SCHEMA_VERSION = 1


class SECFundamentalsCache:
    def __init__(self, db_path: str | Path, ttl_hours: int = 24):
        self.db_path = Path(db_path)
        self.ttl = timedelta(hours=ttl_hours)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sec_fundamentals_cache (
                    ticker TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def get(self, ticker: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT schema_version, created_at, payload_json
                FROM sec_fundamentals_cache
                WHERE ticker = ?
                """,
                (ticker.upper(),),
            ).fetchone()
        if row is None or int(row[0]) != SEC_CACHE_SCHEMA_VERSION:
            return None
        created_at = datetime.fromisoformat(str(row[1]))
        if datetime.now(UTC) - created_at > self.ttl:
            return None
        payload = json.loads(str(row[2]))
        return payload if isinstance(payload, dict) else None

    def set(self, ticker: str, payload: dict[str, Any]) -> None:
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sec_fundamentals_cache (
                    ticker, schema_version, created_at, payload_json
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    created_at = excluded.created_at,
                    payload_json = excluded.payload_json
                """,
                (
                    ticker.upper(),
                    SEC_CACHE_SCHEMA_VERSION,
                    created_at,
                    json.dumps(payload),
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection
