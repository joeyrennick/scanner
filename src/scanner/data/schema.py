"""Version identities shared by staged migration and runtime repositories."""
import sqlite3

APPLICATION_IDS = {"business": int.from_bytes(b"SSDB", "big"),
                   "browser": int.from_bytes(b"SSBR", "big"),
                   "credential": int.from_bytes(b"SSCR", "big")}
SCHEMA_VERSION = 1

BUSINESS_COLUMNS = {
    "scanner_runs": "id created_at universe market_data_provider history_period output_file settings_snapshot result_count",
    "scanner_results": "run_id row_order ticker triggered_strategies composite_score current_price price_as_of price_source entry_area suggested_stop target_exit stop_distance_percent five_day_range row_json updated_at",
    "saved_watchlists": "id name created_at updated_at",
    "saved_watchlist_items": "watchlist_id ticker source data_json added_at updated_at",
}


def validate_version(database: sqlite3.Connection, kind: str | None = None):
    version = database.execute("PRAGMA user_version").fetchone()[0]
    application_id = database.execute("PRAGMA application_id").fetchone()[0]
    if version == 0 and application_id == 0:
        return  # Existing legacy stores and new empty databases.
    if (version != SCHEMA_VERSION or application_id not in APPLICATION_IDS.values()
            or (kind is not None and application_id != APPLICATION_IDS.get(kind))):
        raise ValueError(f"Unsupported database schema version {version} or application identity; no changes were made")


def migrate_legacy_snapshot(database: sqlite3.Connection, kind: str):
    """Only called on an owned, staged snapshot, never on the selected source."""
    if database.execute("PRAGMA user_version").fetchone()[0] != 0:
        raise ValueError("Staged import requires a supported version 0 legacy snapshot")
    if database.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchone():
        raise ValueError("Unsupported source views or triggers")
    expected = BUSINESS_COLUMNS if kind == "business" else {
        "secrets": "name encrypted_value created_at updated_at",
    }
    actual = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if actual - {"sqlite_sequence"} != expected.keys():
        raise ValueError("Unsupported legacy table layout; review before import")
    for name, columns in expected.items():
        if [row[1] for row in database.execute(f'PRAGMA table_info("{name}")')] != columns.split():
            raise ValueError(f"Unsupported legacy columns for {name}; review before import")
    database.execute(f"PRAGMA application_id={APPLICATION_IDS[kind]}")
    database.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
