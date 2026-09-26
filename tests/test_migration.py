from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from scanner.migration.backup import create_backup, verify_backup
from scanner.migration.browser import validate_browser_export
from scanner.migration.legacy import inventory, read_database, snapshot
from scanner.migration.ownership import DataRootInUse, DataRootOwnership
from scanner.security.secret_store import SQLiteSecretStore

PASSPHRASE = "test fixture recovery passphrase only"


def source_fingerprint(root):
    """Check records/schema/files while allowing SQLite's documented WAL bookkeeping."""
    files = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in root.rglob("*") if path.is_file()
             and not path.name.endswith((".sqlite", "-wal", "-shm"))}
    database_path = root / "market_data_cache.sqlite"
    try:
        with read_database(database_path) as database:
            logical = "\n".join(database.iterdump())
            logical += str(database.execute("PRAGMA user_version").fetchone())
            files["database-records-and-schema"] = hashlib.sha256(logical.encode()).hexdigest()
    except (ValueError, sqlite3.Error):
        files["invalid-database-bytes"] = hashlib.sha256(database_path.read_bytes()).hexdigest()
    return files


def browser_bytes(collections=None):
    collections = collections or {
        "plannedTrades": [{"id": "AAPL", "ticker": "AAPL", "strategy": "breakout",
                           "plannedAt": "2026-09-11", "entry": "100", "stop": "95", "target": "115", "status": "planned"}],
        "candidateEdits": [{"id": "AAPL", "entry": "101", "stop": "96", "target": "117"}],
        "valuationAssumptions": [{"id": "AAPL", "assumptions": {"discount_rate": 0.1}}],
        "browserSettings": [{"id": "swing-scanner.market-data-settings.v2", "values": {"primaryProvider": "massive"}}],
    }
    payload = json.dumps({"source": {"origin": "http://127.0.0.1:5173", "exportId": "test-export",
                                     "exportedAt": "2026-09-11T12:00:00.000Z", "writePauseConfirmed": True},
                          "counts": {name: len(rows) for name, rows in collections.items()}, "collections": collections})
    return json.dumps({"format": "swing-scanner.browser-export", "version": 1,
                       "payloadJson": payload, "sha256": hashlib.sha256(payload.encode()).hexdigest()}).encode()


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    root = tmp_path / "legacy"
    root.mkdir()
    db_path = root / "market_data_cache.sqlite"
    with closing(sqlite3.connect(db_path)) as database:
        database.execute("PRAGMA journal_mode=WAL")
        database.executescript("""
            CREATE TABLE scanner_runs (id INTEGER PRIMARY KEY, result_count INTEGER NOT NULL);
            CREATE TABLE scanner_results (run_id INTEGER REFERENCES scanner_runs(id), row_order INTEGER, ticker TEXT);
            CREATE TABLE saved_watchlists (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE saved_watchlist_items (watchlist_id INTEGER REFERENCES saved_watchlists(id), ticker TEXT);
            CREATE TABLE price_bars (ticker TEXT, close REAL);
            INSERT INTO scanner_runs VALUES (1, 1);
            INSERT INTO scanner_results VALUES (1, 0, 'AAPL');
            INSERT INTO saved_watchlists VALUES (1, 'Fixture watchlist');
            INSERT INTO saved_watchlist_items VALUES (1, 'AAPL');
            INSERT INTO price_bars VALUES ('AAPL', 100);
        """)
    SQLiteSecretStore(db_path).set_secret("massive_api_key", "fixture-provider-secret")
    (root / "watchlist.csv").write_text("Ticker\nAAPL\n")
    (root / "watchlist_reports").mkdir()
    (root / "watchlist_reports/report.pdf").write_bytes(b"fixture-report")
    (root / "logs").mkdir()
    (root / "logs/debug.log").write_text("disposable")
    export = tmp_path / "browser.json"
    export.write_bytes(browser_bytes())
    # Dedicated tests cover lsof; this isolates deterministic snapshot tests from host processes.
    monkeypatch.setattr("scanner.migration.backup.require_stopped_source", lambda _root: None)
    return root, export


def capture(legacy, destination):
    root, export = legacy
    return create_backup(root, destination, export, PASSPHRASE, source_writers_stopped=True)


def test_inventory_is_read_only_and_does_not_create_keys(legacy):
    root, _ = legacy
    files = source_fingerprint(root)
    result = inventory(root)
    assert result["databases"]["market_data_cache.sqlite"]["tables"]["secrets"]["count"] == 1
    assert "fixture-provider-secret" not in json.dumps(result)
    assert source_fingerprint(root) == files


def test_coordinated_backup_restore_preserves_records_and_excludes_secrets_and_caches(legacy, tmp_path):
    root, _ = legacy
    original = source_fingerprint(root)
    destination = tmp_path / "backup"
    manifest = capture(legacy, destination)
    assert manifest["business_records"]["scanner_results"]["count"] == 1
    assert manifest["credential_count"] == 1
    with read_database(destination / "data/business.sqlite") as db:
        assert db.execute("SELECT ticker FROM scanner_results").fetchone() == ("AAPL",)
        assert not db.execute("SELECT name FROM sqlite_master WHERE name IN ('secrets', 'price_bars')").fetchall()
    business_bytes = (destination / "data/business.sqlite").read_bytes()
    assert b"fixture-provider-secret" not in business_bytes
    assert b"massive_api_key" not in business_bytes
    assert not (destination / "legacy-files/logs").exists()
    assert not list(destination.rglob("*.key"))
    configuration = json.loads((destination / "configuration/scanner-settings.json").read_bytes())
    from scanner.config.settings import settings
    assert configuration["settings"]["market_data_cache_path"] == settings.market_data_cache_path
    assert "fixture-provider-secret" not in json.dumps(configuration)
    result = verify_backup(destination, tmp_path / "restored", PASSPHRASE)
    assert result["credentials_decrypted"] == 1
    assert result["browser_counts"]["plannedTrades"] == 1
    assert (tmp_path / "restored/legacy-files/watchlist_reports/report.pdf").read_bytes() == b"fixture-report"
    with read_database(tmp_path / "restored/data/browser-records.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM browser_records").fetchone() == (4,)
    marker = DataRootOwnership(tmp_path / "restored").restore_marker
    state = json.loads(marker.read_bytes())
    assert state["companion_enabled"] is False
    assert state["pairing_reset_required"] is True
    assert state["state"] == "verified-isolated-restore"
    assert source_fingerprint(root) == original
    assert all(path.stat().st_mode & 0o077 == 0 for path in destination.rglob("*") if path.is_file())


def test_repeated_backup_and_restore_never_replace_existing_data(legacy, tmp_path):
    destination = tmp_path / "backup"
    capture(legacy, destination)
    before = (destination / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        capture(legacy, destination)
    assert (destination / "manifest.json").read_bytes() == before
    verify_backup(destination, tmp_path / "restored", PASSPHRASE)
    with pytest.raises(ValueError, match="unused root"):
        verify_backup(destination, tmp_path / "restored", PASSPHRASE)
    assert verify_backup(destination, tmp_path / "second-restore", PASSPHRASE)["credentials_decrypted"] == 1


@pytest.mark.parametrize("problem", ["missing-key", "wrong-key", "bad-db", "future-schema", "unknown-table", "unknown-file", "symlink"])
def test_invalid_sources_are_not_initialized_or_activated(legacy, tmp_path, problem):
    root, _ = legacy
    if problem == "missing-key":
        (root / "market_data_cache.key").unlink()
    elif problem == "wrong-key":
        (root / "market_data_cache.key").write_text("invalid")
    elif problem == "bad-db":
        (root / "market_data_cache.sqlite").write_bytes(b"invalid")
    elif problem in {"future-schema", "unknown-table"}:
        with closing(sqlite3.connect(root / "market_data_cache.sqlite")) as db:
            db.execute("PRAGMA user_version=99" if problem == "future-schema" else "CREATE TABLE unknown(id INTEGER)")
            db.commit()
    elif problem == "unknown-file":
        (root / "unknown.json").write_text("{}")
    else:
        (root / "alias").symlink_to(root / "watchlist.csv")
    before = source_fingerprint(root)
    with pytest.raises((ValueError, sqlite3.Error)):
        capture(legacy, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()
    assert source_fingerprint(root) == before
    if problem == "missing-key":
        assert not (root / "market_data_cache.key").exists()


@pytest.mark.parametrize("problem", ["wrong-passphrase", "tampered-file", "traversal", "missing-file"])
def test_invalid_backups_do_not_create_restore_roots(legacy, tmp_path, problem):
    backup = tmp_path / "backup"
    capture(legacy, backup)
    if problem == "tampered-file":
        (backup / "legacy-files/watchlist.csv").write_text("modified")
    elif problem == "missing-file":
        (backup / "browser-export.json").unlink()
    elif problem == "traversal":
        manifest = json.loads((backup / "manifest.json").read_bytes())
        manifest["files"]["../outside"] = {"sha256": "", "bytes": 0}
        (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        verify_backup(backup, tmp_path / "restore", "wrong passphrase of sufficient length" if problem == "wrong-passphrase" else PASSPHRASE)
    assert not (tmp_path / "restore").exists()


def test_interrupted_restore_leaves_durable_external_marker_and_backup_intact(legacy, tmp_path, monkeypatch):
    from scanner.migration import backup as module
    backup = tmp_path / "backup"
    capture(legacy, backup)
    manifest = (backup / "manifest.json").read_bytes()
    write_new = module._write_new

    def interrupt(path, data):
        if path.name == "business.sqlite":
            raise OSError("simulated interruption")
        write_new(path, data)

    monkeypatch.setattr(module, "_write_new", interrupt)
    with pytest.raises(OSError, match="interruption"):
        verify_backup(backup, tmp_path / "restore", PASSPHRASE)
    marker = DataRootOwnership(tmp_path / "restore").restore_marker
    assert json.loads(marker.read_bytes())["state"] == "restoring"
    assert (backup / "manifest.json").read_bytes() == manifest


def test_write_pause_and_non_nested_roots_required(legacy, tmp_path):
    root, export = legacy
    with pytest.raises(ValueError, match="Stop source writers"):
        create_backup(root, tmp_path / "backup", export, PASSPHRASE, source_writers_stopped=False)
    with pytest.raises(ValueError, match="non-nested"):
        capture(legacy, root / "backup")


def test_ownership_excludes_processes_and_aliases_and_survives_root_replacement(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with DataRootOwnership(root) as owner:
        with pytest.raises(DataRootInUse):
            with DataRootOwnership(alias):
                pass
        result = subprocess.run([sys.executable, "-c", "from scanner.migration.ownership import DataRootOwnership; "
                                 "import sys; DataRootOwnership(sys.argv[1]).__enter__()", str(root)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode != 0
        assert "Data root is in use" in result.stderr
        root.rename(tmp_path / "old-data")
        root.mkdir()
        with pytest.raises(DataRootInUse):
            with DataRootOwnership(root):
                pass
    assert owner.lock_path.exists()
    with DataRootOwnership(root):
        pass


def test_source_in_use_detection():
    from scanner.migration.legacy import require_stopped_source
    from unittest.mock import patch
    with patch("scanner.migration.legacy.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "123\n", "")):
        with pytest.raises(ValueError, match="Source files are open"):
            require_stopped_source(Path("/source"))


def test_case_aliases_cannot_bypass_ownership(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    with DataRootOwnership(root):
        with pytest.raises(DataRootInUse):
            with DataRootOwnership(tmp_path / "DATA"):
                pass


def test_maintenance_acquires_ownership_before_database_access(legacy, tmp_path):
    root, _ = legacy
    with DataRootOwnership(root):
        with pytest.raises(DataRootInUse):
            capture(legacy, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_missing_source_database_is_not_created(tmp_path):
    source = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        with read_database(source):
            pass
    assert not source.exists()


def test_backup_cli_can_verify_with_separately_reentered_passphrase(legacy, tmp_path, monkeypatch, capsys):
    from scanner.migration.__main__ import main
    root, export = legacy
    entered = iter([PASSPHRASE, PASSPHRASE, PASSPHRASE])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(entered))
    monkeypatch.setattr("sys.argv", ["scanner.migration", "backup", "--source-root", str(root),
                                    "--destination", str(tmp_path / "backup"), "--browser-export", str(export),
                                    "--source-writers-stopped", "--verify-root", str(tmp_path / "restore")])
    main()
    output = capsys.readouterr().out
    assert "Restore verification passed" in output
    assert PASSPHRASE not in output
    assert "fixture-provider-secret" not in output
    assert (tmp_path / "restore/verification.json").is_file()


def test_cli_failed_recovery_retains_backup_and_does_not_create_restore(legacy, tmp_path, monkeypatch, capsys):
    from scanner.migration.__main__ import main
    root, export = legacy
    entered = iter([PASSPHRASE, PASSPHRASE, "wrong recovery passphrase"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(entered))
    monkeypatch.setattr("sys.argv", ["scanner.migration", "backup", "--source-root", str(root),
                                    "--destination", str(tmp_path / "backup"), "--browser-export", str(export),
                                    "--source-writers-stopped", "--verify-root", str(tmp_path / "restore")])
    with pytest.raises(SystemExit):
        main()
    output = capsys.readouterr()
    assert PASSPHRASE not in output.out + output.err
    assert (tmp_path / "backup/manifest.json").is_file()
    assert not (tmp_path / "restore").exists()


def test_sqlite_backup_includes_committed_wal_records(tmp_path):
    path = tmp_path / "wal.sqlite"
    with closing(sqlite3.connect(path)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE sample(id INTEGER)")
        writer.execute("INSERT INTO sample VALUES (1)")
        writer.commit()
        assert path.with_name(path.name + "-wal").exists()
        with read_database(path) as source, closing(sqlite3.connect(":memory:")) as target:
            snapshot(source, target)
            assert target.execute("SELECT * FROM sample").fetchall() == [(1,)]


@pytest.mark.parametrize("problem", ["checksum", "unknown-fields", "duplicate", "nonfinite", "count"])
def test_browser_export_rejects_invalid_data(problem):
    raw = browser_bytes()
    envelope = json.loads(raw)
    payload = json.loads(envelope["payloadJson"])
    if problem == "unknown-fields":
        payload["collections"]["plannedTrades"][0]["api_key"] = "never-allow"
    elif problem == "duplicate":
        payload["collections"]["plannedTrades"] *= 2
        payload["counts"]["plannedTrades"] = 2
    elif problem == "nonfinite":
        payload["collections"]["valuationAssumptions"][0]["assumptions"]["rate"] = float("nan")
    elif problem == "count":
        payload["counts"]["plannedTrades"] = 99
    envelope["payloadJson"] = json.dumps(payload)
    envelope["sha256"] = "wrong" if problem == "checksum" else hashlib.sha256(envelope["payloadJson"].encode()).hexdigest()
    with pytest.raises(ValueError):
        validate_browser_export(json.dumps(envelope).encode())
