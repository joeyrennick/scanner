from concurrent.futures import ThreadPoolExecutor
import json
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scanner.api.business_records import router
from scanner.config.paths import ApplicationPaths
from scanner.data.browser_records import BrowserRecordStore, RevisionConflict
from scanner.data.ownership import application_lifespan
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.migration.browser import validate_browser_export
from tests.test_migration import browser_bytes


@pytest.fixture
def store(tmp_path):
    return BrowserRecordStore(tmp_path / "business-records.sqlite")


@pytest.mark.parametrize("collection", ["plannedTrades", "candidateEdits", "valuationAssumptions", "browserSettings"])
def test_all_collections_roundtrip_exact_values_and_reopen(store, collection):
    record = validate_browser_export(browser_bytes())["collections"][collection][0]
    assert store.put(collection, record, 0)["revision"] == 1
    assert BrowserRecordStore(store.db_path).list(collection)[0]["record"] == record


def test_stale_concurrent_writes_and_delete_recreate_cannot_overwrite(store):
    record = {"id": "AAPL", "entry": "100", "stop": "95", "target": "115"}
    store.put("candidateEdits", record, 0)
    def write(entry):
        try:
            return store.put("candidateEdits", {**record, "entry": entry}, 1)
        except RevisionConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, ["101", "102"]))
    assert results.count("conflict") == 1
    assert store.delete("candidateEdits", "AAPL", 2)["revision"] == 3
    assert store.get("candidateEdits", "AAPL") == {"record": None, "revision": 3, "updated_at": None}
    with pytest.raises(RevisionConflict):
        store.put("candidateEdits", record, 0)
    assert store.put("candidateEdits", record, 3)["revision"] == 4
    with pytest.raises(RevisionConflict):
        store.delete("candidateEdits", "AAPL", 2)


def test_invalid_records_do_not_change_persisted_records(store):
    record = {"id": "AAPL", "entry": "100", "stop": "95", "target": "115"}
    store.put("candidateEdits", record, 0)
    before = store.list("candidateEdits")
    with pytest.raises(ValueError):
        store.put("candidateEdits", {**record, "api_key": "must-not-be-persisted"}, 1)
    assert store.list("candidateEdits") == before
    assert b"must-not-be-persisted" not in store.db_path.read_bytes()


def test_business_store_cannot_initialize_tables_inside_browser_database(store):
    before = store.db_path.read_bytes()
    with pytest.raises(ValueError, match="application identity"):
        SQLiteScannerResultStore(store.db_path)
    assert store.db_path.read_bytes() == before


def test_versioned_api_rejects_stale_edits_and_id_mismatches(tmp_path, monkeypatch):
    for key, relative in {"SCANNER_DATA_ROOT": "data", "SCANNER_CACHE_ROOT": "cache",
                           "SCANNER_REPORT_ROOT": "data/reports", "SCANNER_LOG_ROOT": "logs"}.items():
        monkeypatch.setenv(key, str(tmp_path / relative))
    app = FastAPI(lifespan=application_lifespan)
    app.include_router(router)
    with TestClient(app) as client:
        url = "/api/v1/business-records/candidateEdits/AAPL"
        record = {"id": "AAPL", "entry": "100", "stop": "95", "target": "115"}
        request = {"record": record, "expected_revision": 0}
        assert client.put(url, json=request).status_code == 200
        assert client.put(url, json=request).status_code == 409
        assert client.put(url, json={**request, "record": {**record, "id": "MSFT"}}).status_code == 422
        assert client.get("/api/v1/business-records/candidateEdits").json()["records"][0]["record"] == record
        assert client.delete(url + "?expected_revision=1").json()["deleted"]
        assert client.get(url).json()["revision"] == 2
        assert client.get("/api/v1/business-records/candidateEdits").json()["records"] == []
        record_with_slash = {**record, "id": "BRK/B"}
        slash_url = "/api/v1/business-records/candidateEdits/" + quote(record_with_slash["id"], safe="")
        assert client.put(slash_url, json={"record": record_with_slash, "expected_revision": 0}).status_code == 200
        assert client.get(slash_url).json()["record"] == record_with_slash
        assert client.delete(slash_url + "?expected_revision=1").json()["deleted"]


def test_migration_status_is_read_only_and_exposes_only_import_identity(tmp_path, monkeypatch):
    for key, relative in {"SCANNER_DATA_ROOT": "data", "SCANNER_CACHE_ROOT": "cache",
                           "SCANNER_REPORT_ROOT": "data/reports", "SCANNER_LOG_ROOT": "logs"}.items():
        monkeypatch.setenv(key, str(tmp_path / relative))
    paths = ApplicationPaths.resolve()
    app = FastAPI(lifespan=application_lifespan)
    app.include_router(router)
    with TestClient(app) as client:
        url = "/api/v1/business-records/migration-status"
        assert client.get(url).json() == {"schema_version": 1, "imported": False}
        assert not paths.browser_database.exists()
        store = BrowserRecordStore(paths.browser_database)
        receipt = {"version": 1, "active_store_imported": True, "import_id": "fixture-import",
                   "browser_source": {"origin": "http://127.0.0.1:5173"},
                   "browser_counts": dict.fromkeys(["plannedTrades", "candidateEdits", "valuationAssumptions", "browserSettings"], 0),
                   "extra_private_metadata": "do-not-expose"}
        receipt_path = paths.data / "import-receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        before = paths.browser_database.read_bytes()
        assert client.get(url).json() == {"schema_version": 1, "imported": True, "import_id": "fixture-import",
                                          "browser_origin": "http://127.0.0.1:5173", "imported_counts": receipt["browser_counts"]}
        assert paths.browser_database.read_bytes() == before
        assert store.list("candidateEdits") == []
        receipt_path.write_text('{broken')
        assert client.get(url).status_code == 409
