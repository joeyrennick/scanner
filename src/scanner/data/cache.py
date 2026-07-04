from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
import sqlite3

import pandas as pd


PRICE_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "stock_splits",
}


@dataclass(frozen=True)
class CacheFetchRequest:
    provider: str
    ticker: str
    interval: str
    period: str
    start_date: date | None = None
    end_date: date | None = None
    auto_adjust: bool = True


class SQLiteMarketDataCache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def load_history(
        self,
        provider: str,
        ticker: str,
        interval: str = "1d",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        where = [
            "provider = ?",
            "ticker = ?",
            "interval = ?",
        ]
        params: list[object] = [provider, ticker.upper(), interval]

        if start_date is not None:
            where.append("bar_date >= ?")
            params.append(start_date.isoformat())

        if end_date is not None:
            where.append("bar_date <= ?")
            params.append(end_date.isoformat())

        query = f"""
            SELECT bar_date, open, high, low, close, adj_close, volume, dividends, stock_splits
            FROM price_bars
            WHERE {' AND '.join(where)}
            ORDER BY bar_date
        """

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        if not rows:
            return pd.DataFrame()

        history = pd.DataFrame(
            rows,
            columns=[
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Adj Close",
                "Volume",
                "Dividends",
                "Stock Splits",
            ],
        )
        history["Date"] = pd.to_datetime(history["Date"])
        history = history.set_index("Date")
        return history

    def store_history(
        self,
        provider: str,
        ticker: str,
        history: pd.DataFrame,
        interval: str = "1d",
    ) -> int:
        normalized = normalize_price_history(history)

        if normalized.empty:
            return 0

        fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
        rows = []

        for bar_date, row in normalized.iterrows():
            rows.append(
                (
                    provider,
                    ticker.upper(),
                    interval,
                    pd.Timestamp(bar_date).date().isoformat(),
                    _nullable_float(row.get("Open")),
                    _nullable_float(row.get("High")),
                    _nullable_float(row.get("Low")),
                    _nullable_float(row.get("Close")),
                    _nullable_float(row.get("Adj Close")),
                    _nullable_float(row.get("Volume")),
                    _nullable_float(row.get("Dividends")),
                    _nullable_float(row.get("Stock Splits")),
                    fetched_at,
                )
            )

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO price_bars (
                    provider, ticker, interval, bar_date,
                    open, high, low, close, adj_close, volume, dividends, stock_splits,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, ticker, interval, bar_date)
                DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    adj_close = excluded.adj_close,
                    volume = excluded.volume,
                    dividends = excluded.dividends,
                    stock_splits = excluded.stock_splits,
                    fetched_at = excluded.fetched_at
                """,
                rows,
            )

        return len(rows)

    def record_fetch(
        self,
        request: CacheFetchRequest,
        status: str,
        rows_returned: int = 0,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="seconds")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_fetches (
                    provider, ticker, interval, period, start_date, end_date, auto_adjust,
                    last_requested_at, last_success_at, rows_returned, status, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, ticker, interval, period, start_date, end_date, auto_adjust)
                DO UPDATE SET
                    last_requested_at = excluded.last_requested_at,
                    last_success_at = excluded.last_success_at,
                    rows_returned = excluded.rows_returned,
                    status = excluded.status,
                    error_message = excluded.error_message
                """,
                (
                    request.provider,
                    request.ticker.upper(),
                    request.interval,
                    request.period,
                    request.start_date.isoformat() if request.start_date else "",
                    request.end_date.isoformat() if request.end_date else "",
                    int(request.auto_adjust),
                    now,
                    now if status == "success" else None,
                    rows_returned,
                    status,
                    error_message,
                ),
            )

    def has_successful_fetch_today(
        self,
        request: CacheFetchRequest,
        today: date,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT last_success_at
                FROM cache_fetches
                WHERE provider = ?
                  AND ticker = ?
                  AND interval = ?
                  AND period = ?
                  AND start_date = ?
                  AND end_date = ?
                  AND auto_adjust = ?
                  AND status = 'success'
                """,
                (
                    request.provider,
                    request.ticker.upper(),
                    request.interval,
                    request.period,
                    request.start_date.isoformat() if request.start_date else "",
                    request.end_date.isoformat() if request.end_date else "",
                    int(request.auto_adjust),
                ),
            ).fetchone()

        if row is None or row[0] is None:
            return False

        return datetime.fromisoformat(row[0]).date() == today

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS price_bars (
                    provider TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    bar_date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    adj_close REAL,
                    volume REAL,
                    dividends REAL,
                    stock_splits REAL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (provider, ticker, interval, bar_date)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_fetches (
                    provider TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    period TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    auto_adjust INTEGER NOT NULL,
                    last_requested_at TEXT NOT NULL,
                    last_success_at TEXT,
                    rows_returned INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    PRIMARY KEY (
                        provider, ticker, interval, period, start_date, end_date, auto_adjust
                    )
                )
                """
            )

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


def normalize_price_history(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()

    normalized = pd.DataFrame(index=pd.to_datetime(history.index).tz_localize(None))

    for output_column in PRICE_COLUMNS:
        series = _extract_column(history, output_column)

        if series is None:
            normalized[output_column] = pd.NA
        else:
            normalized[output_column] = pd.to_numeric(series, errors="coerce")

    if normalized["Adj Close"].isna().all():
        normalized["Adj Close"] = normalized["Close"]

    return normalized.sort_index()


def _extract_column(history: pd.DataFrame, column_name: str) -> pd.Series | None:
    if column_name in history.columns:
        value = history[column_name]
        return value.iloc[:, 0] if hasattr(value, "columns") else value

    if isinstance(history.columns, pd.MultiIndex):
        for level in range(history.columns.nlevels):
            matches = [
                column
                for column in history.columns
                if len(column) > level and column[level] == column_name
            ]

            if matches:
                value = history[matches[0]]
                return value.iloc[:, 0] if hasattr(value, "columns") else value

    return None


def _nullable_float(value):
    if pd.isna(value):
        return None

    return float(value)
