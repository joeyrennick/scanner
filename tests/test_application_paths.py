import gc
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Event

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scanner.config.paths import ApplicationPaths
from scanner.config.settings import ScannerSettings
from scanner.data.cache import SQLiteMarketDataCache
from scanner.data.ownership import acquire_root, application_lifespan, connect
from scanner.data.saved_watchlists import SQLiteSavedWatchlistStore
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.fundamentals.cache import FundamentalAnalysisCache
from scanner.fundamentals.sec_cache import SECFundamentalsCache
from scanner.migration.ownership import DataRootInUse, DataRootOwnership
from scanner.security.secret_store import SQLiteSecretStore


@pytest.fixture
def paths(tmp_path, monkeypatch):
    for name, relative in {
        "SCANNER_DATA_ROOT": "Application Support/Swing Scanner",
        "SCANNER_CACHE_ROOT": "Caches/Swing Scanner",
        "SCANNER_REPORT_ROOT": "Application Support/Swing Scanner/reports",
        "SCANNER_LOG_ROOT": "Logs/Swing Scanner",
    }.items():
        monkeypatch.setenv(name, str(tmp_path / relative))
    return ApplicationPaths.resolve()


def test_paths_are_absolute_cwd_independent_and_resolution_creates_nothing(paths, tmp_path, monkeypatch):
    initial = set(tmp_path.rglob("*"))
    monkeypatch.chdir(tmp_path)
    assert ApplicationPaths.resolve() == paths
    assert set(tmp_path.rglob("*")) == initial
    defaults = ScannerSettings()
    assert defaults.output_file == str(paths.latest_watchlist)
    assert defaults.business_database_path == str(paths.database)
    assert defaults.credential_database_path == str(paths.credential_database)
    assert defaults.market_data_cache_path == str(paths.market_database)
    assert len({defaults.business_database_path, defaults.credential_database_path,
                defaults.market_data_cache_path}) == 3


@pytest.mark.parametrize("name", ["SCANNER_DATA_ROOT", "SCANNER_CACHE_ROOT", "SCANNER_REPORT_ROOT", "SCANNER_LOG_ROOT"])
def test_relative_overrides_are_rejected(paths, monkeypatch, name):
    monkeypatch.setenv(name, "relative/output")
    with pytest.raises(ValueError, match="absolute path"):
        ApplicationPaths.resolve()


@pytest.mark.parametrize("relative", ["", "cache", "../", "../SWING SCANNER/cache"])
def test_cache_cannot_overlap_durable_data_including_case_aliases(paths, monkeypatch, relative):
    monkeypatch.setenv("SCANNER_CACHE_ROOT", str(paths.root / relative))
    with pytest.raises(ValueError, match="separate"):
        ApplicationPaths.resolve()


def test_all_managed_locations_and_aliases_share_one_owner(paths, tmp_path):
    for path in (paths.database, paths.market_database, paths.credential_database,
                 paths.reports / "report.pdf", paths.logs / "job.log",
                 paths.cache.parent / "SWING SCANNER/market/test.sqlite"):
        assert paths.ownership_root(path) == paths.root
    assert paths.ownership_root(tmp_path / "legacy/mixed.sqlite") == tmp_path / "legacy"


STORES = [SQLiteMarketDataCache, SQLiteSavedWatchlistStore, SQLiteScannerResultStore,
          FundamentalAnalysisCache, SECFundamentalsCache, SQLiteSecretStore]


@pytest.mark.parametrize("factory", STORES)
def test_every_store_locks_before_creating_database_or_parent(paths, factory):
    with DataRootOwnership(paths.root):
        with pytest.raises(DataRootInUse):
            factory(paths.database)
    assert not paths.data.exists()


@pytest.mark.parametrize("factory", STORES)
def test_future_schema_is_not_modified(paths, factory):
    paths.data.mkdir(parents=True)
    with sqlite3.connect(paths.database) as database:
        database.execute("CREATE TABLE future_record (id INTEGER)")
        database.execute("PRAGMA user_version=999")
    before = paths.database.read_bytes()
    with pytest.raises(ValueError, match="Unsupported database schema version 999"):
        factory(paths.database)
    assert paths.database.read_bytes() == before


def test_stores_share_process_lease_and_keep_it_until_last_connection_closes(paths):
    first = SQLiteScannerResultStore(paths.database)
    second = SQLiteSavedWatchlistStore(paths.database)
    assert first._ownership is second._ownership
    connection = connect(paths.database)
    del first, second
    gc.collect()
    with pytest.raises(DataRootInUse):
        with DataRootOwnership(paths.root):
            pass
    connection.close()
    with DataRootOwnership(paths.root):
        pass


def test_connection_context_closes_handle_and_releases_lease(paths):
    paths.data.mkdir(parents=True)
    with connect(paths.database) as database:
        database.execute("CREATE TABLE example (id INTEGER)")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        database.execute("SELECT 1")
    with DataRootOwnership(paths.root):
        pass


def test_recovery_markers_prevent_runtime_startup(paths):
    with DataRootOwnership(paths.root) as owner:
        owner.restore_marker.write_text('{"state":"restoring"}')
    with pytest.raises(RuntimeError, match="recovery marker"):
        acquire_root(paths.root)
    assert not paths.data.exists()


def test_pending_migration_cannot_silently_create_an_empty_active_store(paths):
    paths.root.mkdir(parents=True)
    (paths.root / "migration-pending.json").write_text('{"state":"awaiting-staged-import"}')
    with pytest.raises(RuntimeError, match="Legacy migration is pending"):
        SQLiteScannerResultStore(paths.database)
    assert not paths.data.exists()


def test_server_owns_root_between_requests_and_blocks_second_process(paths):
    app = FastAPI(lifespan=application_lifespan)
    with TestClient(app):
        result = subprocess.run(
            [sys.executable, "-c", "from scanner.data.ownership import acquire_root; "
             "from scanner.config.paths import ApplicationPaths; lease=acquire_root(ApplicationPaths.resolve().root)"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
        assert "Data root is in use" in result.stderr
    with DataRootOwnership(paths.root):
        pass


def test_cli_stops_before_any_database_access_when_root_is_owned(paths):
    cli = Path(__file__).resolve().parents[1] / "src/main.py"
    with DataRootOwnership(paths.root):
        result = subprocess.run([sys.executable, str(cli), "--help"],
                                capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert "Data root is in use" in result.stderr
    assert not paths.database.exists()


def test_background_job_retains_root_after_server_shutdown(paths):
    from scanner.api.jobs import JobRegistry
    entered, finish = Event(), Event()
    registry = JobRegistry(max_workers=1)
    def work(_progress, _cancel):
        entered.set()
        assert finish.wait(10)
        return {}
    try:
        with TestClient(FastAPI(lifespan=application_lifespan)):
            registry.start("ownership-test", work)
            assert entered.wait(5)
        with pytest.raises(DataRootInUse):
            with DataRootOwnership(paths.root):
                pass
    finally:
        finish.set()
        registry._executor.shutdown(wait=True)
    with DataRootOwnership(paths.root):
        pass


def test_isolated_roots_can_be_owned_independently(paths, tmp_path):
    lease = acquire_root(paths.root)
    with DataRootOwnership(tmp_path / "independent-root"):
        assert lease.pid == os.getpid()
