from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from scanner.data.ownership import acquire_database, connect
import sqlite3
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ScannerRun:
    id: int
    created_at: str
    universe: str
    market_data_provider: str
    history_period: str
    output_file: str
    result_count: int
    rows: list[dict[str, Any]]


class SQLiteScannerResultStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ownership = acquire_database(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save_scan_results(
        self,
        dataframe: pd.DataFrame,
        *,
        universe: str,
        market_data_provider: str,
        history_period: str,
        output_file: str,
        settings_snapshot: dict[str, Any] | None = None,
    ) -> int:
        rows = _records_from_dataframe(dataframe)
        created_at = _now()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO scanner_runs (
                    created_at, universe, market_data_provider, history_period,
                    output_file, settings_snapshot, result_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    universe,
                    market_data_provider,
                    history_period,
                    output_file,
                    _json_dumps(settings_snapshot or {}),
                    len(rows),
                ),
            )
            run_id = int(cursor.lastrowid)
            self._insert_rows(connection, run_id, rows)

        return run_id

    def latest_run(self) -> ScannerRun | None:
        with self._connect() as connection:
            run = connection.execute(
                """
                SELECT id, created_at, universe, market_data_provider, history_period,
                       output_file, result_count
                FROM scanner_runs
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()

            if run is None:
                return None

            rows = self._load_rows(connection, int(run[0]))

        return ScannerRun(
            id=int(run[0]),
            created_at=str(run[1]),
            universe=str(run[2]),
            market_data_provider=str(run[3]),
            history_period=str(run[4]),
            output_file=str(run[5]),
            result_count=int(run[6]),
            rows=rows,
        )

    def get_run(self, run_id: int) -> ScannerRun | None:
        with self._connect() as connection:
            run = connection.execute(
                """
                SELECT id, created_at, universe, market_data_provider, history_period,
                       output_file, result_count
                FROM scanner_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

            if run is None:
                return None

            rows = self._load_rows(connection, int(run[0]))

        return ScannerRun(
            id=int(run[0]),
            created_at=str(run[1]),
            universe=str(run[2]),
            market_data_provider=str(run[3]),
            history_period=str(run[4]),
            output_file=str(run[5]),
            result_count=int(run[6]),
            rows=rows,
        )

    def update_trade_levels(
        self,
        *,
        run_id: int,
        ticker: str,
        entry_area: float | None = None,
        suggested_stop: float | None = None,
        target_exit: float | None = None,
        reset: bool = False,
    ) -> dict[str, Any]:
        run = self.get_run(run_id)

        if run is None:
            raise ValueError(f"Scanner run not found: {run_id}")

        normalized_ticker = ticker.upper()
        matching_row = next(
            (
                row
                for row in run.rows
                if _string_value(row.get("Ticker")).upper() == normalized_ticker
            ),
            None,
        )

        if matching_row is None:
            raise ValueError(f"Ticker not found in scanner run: {normalized_ticker}")

        updated = dict(matching_row)
        _preserve_original_trade_levels(updated)

        if reset:
            _restore_original_trade_levels(updated)
        else:
            if entry_area is not None:
                updated["Entry Area"] = round(float(entry_area), 2)
            if suggested_stop is not None:
                updated["Suggested Stop"] = round(float(suggested_stop), 2)
            if target_exit is not None:
                updated["Target/Exit"] = round(float(target_exit), 2)
                updated["Suggested Exit"] = round(float(target_exit), 2)
            updated["Trade Levels Edited"] = "YES"

        self.update_rows_by_ticker(run_id=run_id, rows=[updated])
        return updated

    def update_rows_by_ticker(
        self,
        *,
        run_id: int,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not rows:
            return []

        refreshed_by_ticker = {
            _string_value(row.get("Ticker")).upper(): row
            for row in rows
            if _string_value(row.get("Ticker"))
        }

        with self._connect() as connection:
            existing_rows = self._load_rows(connection, run_id)

            if not existing_rows:
                merged_rows = rows
            else:
                seen = set()
                merged_rows = []

                for existing in existing_rows:
                    ticker = _string_value(existing.get("Ticker")).upper()
                    refreshed = refreshed_by_ticker.get(ticker)
                    if refreshed is None:
                        merged_rows.append(existing)
                    else:
                        merged_rows.append({**existing, **refreshed})
                        seen.add(ticker)

                for ticker, refreshed in refreshed_by_ticker.items():
                    if ticker not in seen:
                        merged_rows.append(refreshed)

            connection.execute("DELETE FROM scanner_results WHERE run_id = ?", (run_id,))
            self._insert_rows(connection, run_id, merged_rows)
            connection.execute(
                """
                UPDATE scanner_runs
                SET result_count = ?
                WHERE id = ?
                """,
                (len(merged_rows), run_id),
            )

        return merged_rows

    def _load_rows(
        self,
        connection: sqlite3.Connection,
        run_id: int,
    ) -> list[dict[str, Any]]:
        records = connection.execute(
            """
            SELECT row_json
            FROM scanner_results
            WHERE run_id = ?
            ORDER BY row_order
            """,
            (run_id,),
        ).fetchall()
        return [json.loads(record[0]) for record in records]

    def _insert_rows(
        self,
        connection: sqlite3.Connection,
        run_id: int,
        rows: list[dict[str, Any]],
    ) -> None:
        now = _now()
        connection.executemany(
            """
            INSERT INTO scanner_results (
                run_id, row_order, ticker, triggered_strategies, composite_score,
                current_price, price_as_of, price_source, entry_area,
                suggested_stop, target_exit, stop_distance_percent, five_day_range,
                row_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    index,
                    _string_value(row.get("Ticker")).upper(),
                    _string_value(row.get("Triggered Strategies")),
                    _float_value(row.get("Composite Score")),
                    _float_value(row.get("Current Price"))
                    or _float_value(row.get("Price")),
                    _string_value(row.get("Price As Of")),
                    _string_value(row.get("Price Source")),
                    _float_value(row.get("Entry Area")),
                    _float_value(row.get("Suggested Stop"))
                    or _float_value(row.get("Stop 2ATR")),
                    _float_value(row.get("Target/Exit"))
                    or _float_value(row.get("Suggested Exit")),
                    _float_value(row.get("Stop Distance %")),
                    _float_value(row.get("5D Range")),
                    _json_dumps(row),
                    now,
                )
                for index, row in enumerate(rows)
            ],
        )

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scanner_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    universe TEXT NOT NULL,
                    market_data_provider TEXT NOT NULL,
                    history_period TEXT NOT NULL,
                    output_file TEXT NOT NULL,
                    settings_snapshot TEXT NOT NULL,
                    result_count INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scanner_results (
                    run_id INTEGER NOT NULL,
                    row_order INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    triggered_strategies TEXT,
                    composite_score REAL,
                    current_price REAL,
                    price_as_of TEXT,
                    price_source TEXT,
                    entry_area REAL,
                    suggested_stop REAL,
                    target_exit REAL,
                    stop_distance_percent REAL,
                    five_day_range REAL,
                    row_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, row_order),
                    FOREIGN KEY (run_id) REFERENCES scanner_runs(id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_scanner_results_run_ticker
                ON scanner_results(run_id, ticker)
                """
            )

    def _connect(self):
        connection = connect(self.db_path, timeout=30, kind="business")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


def _records_from_dataframe(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    if dataframe.empty:
        return []

    safe_dataframe = dataframe.astype(object).where(pd.notna(dataframe), None)
    return [
        {str(key): _json_safe(value) for key, value in record.items()}
        for record in safe_dataframe.to_dict(orient="records")
    ]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]

    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()

    if isinstance(value, float):
        return value if pd.notna(value) else None

    if hasattr(value, "item"):
        return _json_safe(value.item())

    if pd.isna(value):
        return None

    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _float_value(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if pd.notna(value) else None

    if not isinstance(value, str):
        return None

    try:
        parsed = float(value.replace("$", "").replace(",", "").replace("%", ""))
    except ValueError:
        return None

    return parsed if pd.notna(parsed) else None


def _string_value(value: Any) -> str:
    if value is None:
        return ""

    return str(value)


def _preserve_original_trade_levels(row: dict[str, Any]) -> None:
    if "Original Entry Area" not in row:
        row["Original Entry Area"] = (
            _float_value(row.get("Entry Area")) or _float_value(row.get("Price"))
        )
    if "Original Suggested Stop" not in row:
        row["Original Suggested Stop"] = (
            _float_value(row.get("Suggested Stop")) or _float_value(row.get("Stop 2ATR"))
        )
    if "Original Target/Exit" not in row:
        row["Original Target/Exit"] = (
            _float_value(row.get("Target/Exit")) or _float_value(row.get("Suggested Exit"))
        )


def _restore_original_trade_levels(row: dict[str, Any]) -> None:
    original_entry = _float_value(row.get("Original Entry Area"))
    original_stop = _float_value(row.get("Original Suggested Stop"))
    original_target = _float_value(row.get("Original Target/Exit"))

    if original_entry is not None:
        row["Entry Area"] = round(original_entry, 2)
    if original_stop is not None:
        row["Suggested Stop"] = round(original_stop, 2)
    if original_target is not None:
        row["Target/Exit"] = round(original_target, 2)
        row["Suggested Exit"] = round(original_target, 2)

    row["Trade Levels Edited"] = "NO"
