from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


class FundamentalAnalysisCache:
    def __init__(self, db_path: str | Path, ttl_hours: int = 6):
        self.db_path = Path(db_path)
        self.ttl = timedelta(hours=ttl_hours)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fundamental_analysis_cache (
                    cache_key TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def get(self, ticker: str, assumptions: dict[str, Any]) -> dict[str, Any] | None:
        key = _key(ticker, assumptions)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_at, payload_json FROM fundamental_analysis_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        created_at = datetime.fromisoformat(row[0])
        if datetime.now(UTC) - created_at > self.ttl:
            return None
        payload = json.loads(row[1])
        payload["cache"] = {"status": "hit", "created_at": row[0]}
        return payload

    def set(self, ticker: str, assumptions: dict[str, Any], payload: dict[str, Any]) -> None:
        key = _key(ticker, assumptions)
        created_at = datetime.now(UTC).isoformat()
        stored = dict(payload)
        stored["cache"] = {"status": "miss", "created_at": created_at}
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fundamental_analysis_cache (cache_key, ticker, created_at, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    created_at = excluded.created_at,
                    payload_json = excluded.payload_json
                """,
                (key, ticker, created_at, json.dumps(stored)),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def _key(ticker: str, assumptions: dict[str, Any]) -> str:
    serialized = json.dumps(assumptions, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    return f"{ticker.upper()}:{digest}"
