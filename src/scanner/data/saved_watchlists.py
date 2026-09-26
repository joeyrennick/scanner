from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from scanner.data.ownership import acquire_database, connect
import sqlite3
from typing import Any


@dataclass(frozen=True)
class SavedWatchlistItem:
    ticker: str
    source: str | None
    data: dict[str, Any]
    added_at: str
    updated_at: str


@dataclass(frozen=True)
class SavedWatchlist:
    id: int
    name: str
    created_at: str
    updated_at: str
    items: list[SavedWatchlistItem]


class SQLiteSavedWatchlistStore:
    """Persistent user-managed watchlists, separate from generated scanner runs."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ownership = acquire_database(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_watchlists(self) -> list[SavedWatchlist]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, created_at, updated_at
                FROM saved_watchlists
                ORDER BY name COLLATE NOCASE, id
                """
            ).fetchall()
            return [self._watchlist_from_row(connection, row) for row in rows]

    def get_watchlist(self, watchlist_id: int) -> SavedWatchlist | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, created_at, updated_at
                FROM saved_watchlists
                WHERE id = ?
                """,
                (watchlist_id,),
            ).fetchone()
            return self._watchlist_from_row(connection, row) if row else None

    def create_watchlist(self, name: str) -> SavedWatchlist:
        normalized_name = _normalize_name(name)
        now = _now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO saved_watchlists (name, created_at, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (normalized_name, now, now),
                )
                watchlist_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError(f"A watchlist named '{normalized_name}' already exists") from error
        watchlist = self.get_watchlist(watchlist_id)
        if watchlist is None:  # pragma: no cover - guards against external DB corruption
            raise RuntimeError("Unable to load the newly created watchlist")
        return watchlist

    def rename_watchlist(self, watchlist_id: int, name: str) -> SavedWatchlist:
        normalized_name = _normalize_name(name)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE saved_watchlists
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (normalized_name, _now(), watchlist_id),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Saved watchlist not found: {watchlist_id}")
        except sqlite3.IntegrityError as error:
            raise ValueError(f"A watchlist named '{normalized_name}' already exists") from error
        watchlist = self.get_watchlist(watchlist_id)
        if watchlist is None:  # pragma: no cover
            raise RuntimeError("Unable to load the renamed watchlist")
        return watchlist

    def delete_watchlist(self, watchlist_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM saved_watchlists WHERE id = ?",
                (watchlist_id,),
            )
            return cursor.rowcount > 0

    def add_item(
        self,
        watchlist_id: int,
        ticker: str,
        *,
        source: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> SavedWatchlistItem:
        normalized_ticker = _normalize_ticker(ticker)
        normalized_source = source.strip() if isinstance(source, str) and source.strip() else None
        now = _now()
        with self._connect() as connection:
            if not self._watchlist_exists(connection, watchlist_id):
                raise LookupError(f"Saved watchlist not found: {watchlist_id}")
            existing = connection.execute(
                """
                SELECT data_json
                FROM saved_watchlist_items
                WHERE watchlist_id = ? AND ticker = ?
                """,
                (watchlist_id, normalized_ticker),
            ).fetchone()
            existing_data: dict[str, Any] = {}
            if existing:
                try:
                    decoded = json.loads(existing[0])
                    if isinstance(decoded, dict):
                        existing_data = decoded
                except (TypeError, json.JSONDecodeError):
                    pass
            merged_data = {**existing_data, **(data or {})}
            connection.execute(
                """
                INSERT INTO saved_watchlist_items (
                    watchlist_id, ticker, source, data_json, added_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(watchlist_id, ticker) DO UPDATE SET
                    source = COALESCE(excluded.source, saved_watchlist_items.source),
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at
                """,
                (
                    watchlist_id,
                    normalized_ticker,
                    normalized_source,
                    json.dumps(merged_data, sort_keys=True),
                    now,
                    now,
                ),
            )
            connection.execute(
                "UPDATE saved_watchlists SET updated_at = ? WHERE id = ?",
                (now, watchlist_id),
            )
            row = connection.execute(
                """
                SELECT ticker, source, data_json, added_at, updated_at
                FROM saved_watchlist_items
                WHERE watchlist_id = ? AND ticker = ?
                """,
                (watchlist_id, normalized_ticker),
            ).fetchone()
        return _item_from_row(row)

    def remove_item(self, watchlist_id: int, ticker: str) -> bool:
        normalized_ticker = _normalize_ticker(ticker)
        with self._connect() as connection:
            if not self._watchlist_exists(connection, watchlist_id):
                raise LookupError(f"Saved watchlist not found: {watchlist_id}")
            cursor = connection.execute(
                """
                DELETE FROM saved_watchlist_items
                WHERE watchlist_id = ? AND ticker = ?
                """,
                (watchlist_id, normalized_ticker),
            )
            if cursor.rowcount > 0:
                connection.execute(
                    "UPDATE saved_watchlists SET updated_at = ? WHERE id = ?",
                    (_now(), watchlist_id),
                )
            return cursor.rowcount > 0

    def _watchlist_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row | tuple[Any, ...],
    ) -> SavedWatchlist:
        items = connection.execute(
            """
            SELECT ticker, source, data_json, added_at, updated_at
            FROM saved_watchlist_items
            WHERE watchlist_id = ?
            ORDER BY added_at, ticker
            """,
            (int(row[0]),),
        ).fetchall()
        return SavedWatchlist(
            id=int(row[0]),
            name=str(row[1]),
            created_at=str(row[2]),
            updated_at=str(row[3]),
            items=[_item_from_row(item) for item in items],
        )

    @staticmethod
    def _watchlist_exists(connection: sqlite3.Connection, watchlist_id: int) -> bool:
        return connection.execute(
            "SELECT 1 FROM saved_watchlists WHERE id = ?",
            (watchlist_id,),
        ).fetchone() is not None

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_watchlist_items (
                    watchlist_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL COLLATE NOCASE,
                    source TEXT,
                    data_json TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (watchlist_id, ticker),
                    FOREIGN KEY (watchlist_id) REFERENCES saved_watchlists(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_saved_watchlist_items_ticker
                ON saved_watchlist_items(ticker)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = connect(self.db_path, timeout=30, kind="business")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _item_from_row(row: sqlite3.Row | tuple[Any, ...]) -> SavedWatchlistItem:
    try:
        data = json.loads(row[2])
    except (TypeError, json.JSONDecodeError):
        data = {}
    return SavedWatchlistItem(
        ticker=str(row[0]).upper(),
        source=str(row[1]) if row[1] is not None else None,
        data=data if isinstance(data, dict) else {},
        added_at=str(row[3]),
        updated_at=str(row[4]),
    )


def _normalize_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("Watchlist name is required")
    if len(normalized) > 80:
        raise ValueError("Watchlist name must be 80 characters or fewer")
    return normalized


def _normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("Ticker is required")
    if len(normalized) > 20 or not all(character.isalnum() or character in ".-" for character in normalized):
        raise ValueError(f"Invalid ticker: {normalized}")
    return normalized


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
