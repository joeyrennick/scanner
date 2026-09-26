from contextlib import closing
from dataclasses import replace
import gc
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pandas as pd
import pytest

from scanner.config.paths import ApplicationPaths
from scanner.data.browser_records import BrowserRecordStore
from scanner.data.ownership import acquire_root
from scanner.data.saved_watchlists import SQLiteSavedWatchlistStore
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.migration import activation
from scanner.migration.backup import create_backup, verify_backup
from scanner.migration.importer import import_backup, preview_import
from scanner.migration.legacy import BUSINESS_TABLES, read_database, record_manifest
from scanner.migration.ownership import DataRootInUse, DataRootOwnership
from scanner.security.secret_store import SQLiteSecretStore
from tests.test_migration import PASSPHRASE, browser_bytes, source_fingerprint


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / "legacy"
    database = root / "market_data_cache.sqlite"
    scans = SQLiteScannerResultStore(database)
    scans.save_scan_results(pd.DataFrame([{"Ticker": "AAPL", "Entry Area": 100.0}]),
                            universe="sp500", market_data_provider="massive", history_period="1y",
                            output_file="output/watchlist.csv")
    lists = SQLiteSavedWatchlistStore(database)
    watchlist = lists.create_watchlist("Imported watchlist")
    lists.add_item(watchlist.id, "AAPL", data={"Current Price": 100})
    SQLiteSecretStore(database).set_secret("massive_api_key", "fixture-secret-value")
    del scans, lists
    gc.collect()
    (root / "watchlist.csv").write_text("Ticker\nAAPL\n")
    (root / "watchlist_reports").mkdir()
    (root / "watchlist_reports/example.pdf").write_bytes(b"fixture saved PDF")
    export = tmp_path / "browser.json"
    export.write_bytes(browser_bytes())
    for module in ("backup", "importer"):
        monkeypatch.setattr(f"scanner.migration.{module}.require_stopped_source", lambda _root: None)
    backup, verification = tmp_path / "backup", tmp_path / "verification"
    create_backup(root, backup, export, PASSPHRASE, source_writers_stopped=True)
    verify_backup(backup, verification, PASSPHRASE)
    for name, relative in {"SCANNER_DATA_ROOT": "application", "SCANNER_CACHE_ROOT": "cache",
                           "SCANNER_REPORT_ROOT": "application/reports", "SCANNER_LOG_ROOT": "logs"}.items():
        monkeypatch.setenv(name, str(tmp_path / relative))
    return root, backup, verification, ApplicationPaths.resolve()


def run_import(prepared, passphrase=PASSPHRASE):
    _, backup, verification, paths = prepared
    return import_backup(backup, verification, paths, passphrase,
                         source_writers_stopped=True, browser_edits_paused=True)


def test_preview_leaves_destination_and_original_records_untouched(prepared):
    source, backup, verification, paths = prepared
    original = source_fingerprint(source)
    preview = preview_import(backup, verification, paths)
    assert preview["action"] == "first-import"
    assert preview["browser_counts"]["plannedTrades"] == 1
    assert not preview["replaces_existing_data"]
    assert not paths.root.exists()
    assert source_fingerprint(source) == original


def test_import_reconciles_and_reopens_without_legacy_source_or_cache(prepared, tmp_path):
    source, backup, verification, paths = prepared
    original = source_fingerprint(source)
    receipt = run_import(prepared)
    assert receipt["active_store_imported"]
    assert not receipt["already_imported"]
    assert not (paths.root / "migration-pending.json").exists()
    assert source_fingerprint(source) == original
    source.rename(tmp_path / "preserved-source-not-at-original-location")
    assert SQLiteScannerResultStore(paths.database).latest_run().rows[0]["Ticker"] == "AAPL"
    assert SQLiteSavedWatchlistStore(paths.database).list_watchlists()[0].items[0].ticker == "AAPL"
    assert SQLiteSecretStore(paths.credential_database).get_secret("massive_api_key") == "fixture-secret-value"
    records = BrowserRecordStore(paths.browser_database).list("plannedTrades")
    assert records[0]["record"]["entry"] == "100"
    assert records[0]["revision"] == 1
    assert not paths.cache.exists()
    assert (paths.reports / "watchlist_reports/example.pdf").read_bytes() == b"fixture saved PDF"
    assert paths.credential_database.with_suffix(".key").stat().st_mode & 0o777 == 0o600
    assert (paths.root / "configuration/scanner-settings.json").is_file()
    with read_database(paths.database) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 1
        assert record_manifest(database, BUSINESS_TABLES) == receipt["business_records"]


def test_reimport_is_noop_and_does_not_undo_later_edits(prepared):
    _, backup, verification, paths = prepared
    receipt = run_import(prepared)
    store = BrowserRecordStore(paths.browser_database)
    record = store.list("plannedTrades")[0]["record"]
    store.put("plannedTrades", {**record, "entry": "999"}, 1)
    del store
    gc.collect()
    assert preview_import(backup, verification, paths)["action"] == "already-imported"
    repeated = run_import(prepared, "not needed on a completed retry")
    assert repeated["already_imported"]
    assert repeated["import_id"] == receipt["import_id"]
    assert BrowserRecordStore(paths.browser_database).list("plannedTrades")[0]["record"]["entry"] == "999"


def test_existing_destination_is_not_replaced(prepared):
    _, _, _, paths = prepared
    paths.data.mkdir(parents=True)
    sentinel = paths.data / "existing-user-file"
    sentinel.write_bytes(b"keep original")
    with pytest.raises(ValueError, match="unused destination"):
        run_import(prepared)
    assert sentinel.read_bytes() == b"keep original"
    assert not (paths.root / ".migration").exists()


@pytest.mark.parametrize("problem", ["wrong-passphrase", "changed-source", "changed-secret", "changed-schema", "missing-key", "tampered-backup", "wrong-evidence", "missing-evidence"])
def test_invalid_imports_leave_destination_unused(prepared, problem):
    source, backup, verification, paths = prepared
    phrase = PASSPHRASE
    if problem == "wrong-passphrase":
        phrase = "wrong saved recovery phrase"
    elif problem == "changed-source":
        (source / "watchlist.csv").write_text("Ticker\nMSFT\n")
    elif problem == "changed-secret":
        SQLiteSecretStore(source / "market_data_cache.sqlite").set_secret("massive_api_key", "changed-fixture")
    elif problem == "changed-schema":
        with closing(sqlite3.connect(source / "market_data_cache.sqlite")) as database:
            database.execute("PRAGMA user_version=999")
    elif problem == "missing-key":
        (source / "market_data_cache.key").unlink()
    elif problem == "tampered-backup":
        (backup / "credential-recovery.enc").write_bytes(b"tampered archive")
    elif problem == "wrong-evidence":
        evidence = json.loads((verification / "verification.json").read_bytes())
        evidence["backup_id"] = "different"
        (verification / "verification.json").write_text(json.dumps(evidence))
    elif problem == "missing-evidence":
        (verification / "verification.json").unlink()
    before = source_fingerprint(source)
    with pytest.raises((ValueError, FileNotFoundError)):
        run_import(prepared, phrase)
    assert source_fingerprint(source) == before
    assert not paths.root.exists()


def test_custom_report_root_is_refused_without_writes(prepared):
    _, backup, verification, paths = prepared
    with pytest.raises(ValueError, match="custom report activation"):
        preview_import(backup, verification, replace(paths, reports=paths.root.parent / "custom-reports"))
    assert not paths.root.exists()


def test_owned_root_prevents_preview_or_import(prepared):
    _, backup, verification, paths = prepared
    with DataRootOwnership(paths.root):
        with pytest.raises(DataRootInUse):
            preview_import(backup, verification, paths)
        with pytest.raises(DataRootInUse):
            run_import(prepared)
    assert not paths.root.exists()


@pytest.mark.parametrize("boundary", ["journal-written", "activated-data", "activated-reports", "activated-credentials",
                                      "activated-configuration", "before-commit", "after-commit", "gate-retired"])
def test_process_death_at_activation_boundaries_recovers_before_runtime_access(prepared, monkeypatch, boundary):
    source, backup, verification, paths = prepared
    original = source_fingerprint(source)
    script = """
import os, sys
from pathlib import Path
from scanner.config.paths import ApplicationPaths
from scanner.migration import activation, importer
importer.require_stopped_source = lambda root: None
def checkpoint(name):
    if name == sys.argv[3]: os._exit(93)
activation.checkpoint = checkpoint
importer.import_backup(Path(sys.argv[1]), Path(sys.argv[2]), ApplicationPaths.resolve(),
    'test fixture recovery passphrase only', source_writers_stopped=True, browser_edits_paused=True)
"""
    result = subprocess.run([sys.executable, "-c", script, str(backup), str(verification), boundary],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 93, result.stderr
    assert "fixture-secret-value" not in result.stdout + result.stderr
    if boundary in {"after-commit", "gate-retired"}:
        lease = acquire_root(paths.root)  # Recovery finishes before ownership is returned.
        assert not (paths.root / "migration-pending.json").exists()
        del lease
    else:
        with pytest.raises(RuntimeError, match="Legacy migration is pending"):
            acquire_root(paths.root)
        assert all(not (paths.root / slot).exists() for slot in activation.SLOTS)
        assert (paths.root / "migration-pending.json").is_file()
        run_import(prepared)
    assert BrowserRecordStore(paths.browser_database).list("plannedTrades")[0]["record"]["id"] == "AAPL"
    assert source_fingerprint(source) == original
    owner = DataRootOwnership(paths.root)
    assert not (owner.control_directory / "activation.json").exists()
    assert (owner.control_directory / "companion-state.json").is_file()


def test_ordinary_activation_error_rolls_back_and_retains_stage(prepared, monkeypatch):
    _, _, _, paths = prepared
    def fail(name):
        if name == "activated-reports":
            raise OSError("fixture interrupted filesystem operation")
    monkeypatch.setattr(activation, "checkpoint", fail)
    with pytest.raises(OSError, match="fixture interrupted"):
        run_import(prepared)
    assert not paths.data.exists()
    assert len(list((paths.root / ".migration/stages").iterdir())) == 1
    monkeypatch.setattr(activation, "checkpoint", lambda _name: None)
    assert run_import(prepared)["active_store_imported"]


def test_tampered_partial_activation_blocks_runtime_without_overwriting_it(prepared, monkeypatch):
    _, _, _, paths = prepared
    class SimulatedTermination(BaseException):
        pass
    def crash(name):
        if name == "activated-data":
            raise SimulatedTermination()
    monkeypatch.setattr(activation, "checkpoint", crash)
    with pytest.raises(SimulatedTermination):
        run_import(prepared)
    sentinel = paths.data / "unknown-user-file"
    sentinel.write_text("Do not delete")
    with pytest.raises(ValueError, match="changed before recovery"):
        acquire_root(paths.root)
    assert sentinel.read_text() == "Do not delete"
    assert (DataRootOwnership(paths.root).control_directory / "activation.json").exists()


def test_recovery_itself_can_be_interrupted_and_retried(prepared, monkeypatch):
    _, _, _, paths = prepared
    class SimulatedTermination(BaseException):
        pass
    def crash(name):
        if name in {"activated-credentials", "rollback-credentials"}:
            raise SimulatedTermination()
    monkeypatch.setattr(activation, "checkpoint", crash)
    with pytest.raises(SimulatedTermination):
        run_import(prepared)
    with pytest.raises(SimulatedTermination):
        acquire_root(paths.root)
    monkeypatch.setattr(activation, "checkpoint", lambda _name: None)
    with pytest.raises(RuntimeError, match="Legacy migration is pending"):
        acquire_root(paths.root)
    assert all(not (paths.root / slot).exists() for slot in activation.SLOTS)
    assert run_import(prepared)["active_store_imported"]


def test_actual_cache_deletion_keeps_imported_records_and_reports(prepared):
    from scanner.data.cache import SQLiteMarketDataCache
    _, _, _, paths = prepared
    run_import(prepared)
    # Populate and evict only a fixture's disposable cache, not a user directory.
    cache = SQLiteMarketDataCache(paths.market_database)
    del cache
    gc.collect()
    paths.market_database.unlink()
    assert SQLiteScannerResultStore(paths.database).latest_run().rows[0]["Ticker"] == "AAPL"
    assert len(BrowserRecordStore(paths.browser_database).list("plannedTrades")) == 1
    assert (paths.reports / "watchlist_reports/example.pdf").is_file()


def test_cli_requires_local_confirmation_without_exposing_passphrase(prepared, monkeypatch, capsys):
    from scanner.migration.__main__ import main
    _, backup, verification, paths = prepared
    monkeypatch.setattr("sys.argv", ["scanner.migration", "import", "--backup", str(backup),
                                    "--verification-root", str(verification), "--source-writers-stopped", "--browser-edits-paused"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "IMPORT")
    monkeypatch.setattr("getpass.getpass", lambda _prompt: PASSPHRASE)
    main()
    output = capsys.readouterr()
    assert PASSPHRASE not in output.out + output.err
    assert "fixture-secret-value" not in output.out + output.err
    assert (paths.data / "import-receipt.json").is_file()
