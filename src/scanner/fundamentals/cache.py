from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from scanner.data.ownership import acquire_database, connect
import sqlite3
from typing import Any

CACHE_SCHEMA_VERSION = 6


class FundamentalAnalysisCache:
    def __init__(self, db_path: str | Path, ttl_hours: int = 6):
        self.db_path = Path(db_path)
        self._ownership = acquire_database(self.db_path)
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

    def latest_risks(self, tickers: list[str]) -> dict[str, dict[str, Any]]:
        normalized = sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})
        if not normalized:
            return {}

        rows = []
        with self._connect() as connection:
            for start in range(0, len(normalized), 500):
                chunk = normalized[start : start + 500]
                placeholders = ",".join("?" for _ in chunk)
                rows.extend(
                    connection.execute(
                        f"""
                        SELECT ticker, created_at, payload_json
                        FROM fundamental_analysis_cache
                        WHERE ticker IN ({placeholders})
                        ORDER BY created_at DESC
                        """,
                        chunk,
                    ).fetchall()
                )

        risks: dict[str, dict[str, Any]] = {}
        now = datetime.now(UTC)
        for ticker, created_at_value, payload_json in sorted(
            rows,
            key=lambda row: row[1],
            reverse=True,
        ):
            normalized_ticker = str(ticker).upper()
            if normalized_ticker in risks:
                continue
            created_at = datetime.fromisoformat(created_at_value)
            if now - created_at > self.ttl:
                continue
            risk = json.loads(payload_json).get("risk") or {}
            label = str(risk.get("label") or "").strip().lower()
            score = risk.get("score")
            if label in {"low", "moderate", "high"} and isinstance(score, (int, float)):
                risks[normalized_ticker] = {"label": label, "score": score}
        return risks

    def latest_validations(self, tickers: list[str]) -> dict[str, dict[str, Any]]:
        normalized = sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})
        if not normalized:
            return {}

        rows = []
        with self._connect() as connection:
            for start in range(0, len(normalized), 500):
                chunk = normalized[start : start + 500]
                placeholders = ",".join("?" for _ in chunk)
                rows.extend(
                    connection.execute(
                        f"""
                        SELECT ticker, created_at, payload_json
                        FROM fundamental_analysis_cache
                        WHERE ticker IN ({placeholders})
                        ORDER BY created_at DESC
                        """,
                        chunk,
                    ).fetchall()
                )

        validations: dict[str, dict[str, Any]] = {}
        now = datetime.now(UTC)
        for ticker, created_at_value, payload_json in sorted(
            rows,
            key=lambda row: row[1],
            reverse=True,
        ):
            normalized_ticker = str(ticker).upper()
            if normalized_ticker in validations:
                continue
            created_at = datetime.fromisoformat(created_at_value)
            if now - created_at > self.ttl:
                continue
            validation = json.loads(payload_json).get("validation") or {}
            status = str(validation.get("status") or "").strip().lower()
            score = validation.get("score")
            if status in {"validated", "needs_review", "rejected"}:
                validations[normalized_ticker] = {
                    "status": status,
                    "label": validation.get("label") or status.replace("_", " ").title(),
                    "score": score,
                    "reasons": list(validation.get("reasons") or []),
                    "model": validation.get("model") or "unknown",
                }
        return validations

    def _connect(self) -> sqlite3.Connection:
        return connect(self.db_path, kind="cache")


def _key(ticker: str, assumptions: dict[str, Any]) -> str:
    serialized = json.dumps(assumptions, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    return f"v{CACHE_SCHEMA_VERSION}:{ticker.upper()}:{digest}"
