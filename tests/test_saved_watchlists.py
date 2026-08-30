from dataclasses import replace

from fastapi.testclient import TestClient

from scanner.api.app import app
from scanner.data.saved_watchlists import SQLiteSavedWatchlistStore


client = TestClient(app)


def test_saved_watchlist_store_manages_multiple_lists_and_memberships(tmp_path):
    store = SQLiteSavedWatchlistStore(tmp_path / "user_data.sqlite")
    growth = store.create_watchlist("Growth")
    income = store.create_watchlist("Income")

    store.add_item(growth.id, " aapl ", source="candidates", data={"Current Price": 100})
    store.add_item(income.id, "AAPL", source="fundamentals", data={"Risk Level": "low"})
    store.add_item(growth.id, "MSFT", source="daily-scanner")
    store.add_item(growth.id, "AAPL", source="watchlists", data={"Ticker": "AAPL"})

    assert [watchlist.name for watchlist in store.list_watchlists()] == ["Growth", "Income"]
    assert [item.ticker for item in store.get_watchlist(growth.id).items] == ["AAPL", "MSFT"]
    assert store.get_watchlist(growth.id).items[0].data["Current Price"] == 100
    assert store.get_watchlist(income.id).items[0].data == {"Risk Level": "low"}

    assert store.remove_item(growth.id, "AAPL") is True
    assert [item.ticker for item in store.get_watchlist(growth.id).items] == ["MSFT"]
    assert [item.ticker for item in store.get_watchlist(income.id).items] == ["AAPL"]


def test_saved_watchlist_store_renames_and_cascades_delete(tmp_path):
    store = SQLiteSavedWatchlistStore(tmp_path / "user_data.sqlite")
    watchlist = store.create_watchlist("Ideas")
    store.add_item(watchlist.id, "NVDA")

    assert store.rename_watchlist(watchlist.id, "High Conviction").name == "High Conviction"
    assert store.delete_watchlist(watchlist.id) is True
    assert store.get_watchlist(watchlist.id) is None


def test_saved_watchlist_api_crud_and_latest_scanner_enrichment(tmp_path, monkeypatch):
    from scanner.api import app as api_app
    from scanner.data.scanner_results import SQLiteScannerResultStore
    import pandas as pd

    db_path = tmp_path / "market_data.sqlite"
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(api_app.settings, market_data_cache_path=str(db_path)),
    )
    SQLiteScannerResultStore(db_path).save_scan_results(
        pd.DataFrame([
            {
                "Ticker": "AAPL",
                "Current Price": 125,
                "Risk Level": "low",
            }
        ]),
        universe="sp500",
        market_data_provider="massive",
        history_period="1y",
        output_file=str(tmp_path / "watchlist.csv"),
    )

    created = client.post("/api/saved-watchlists", json={"name": "Long Term"})
    assert created.status_code == 200
    watchlist_id = created.json()["id"]

    added = client.post(
        f"/api/saved-watchlists/{watchlist_id}/items",
        json={
            "ticker": "aapl",
            "source": "fundamentals",
            "data": {"Current Price": 100, "Fair Value": 150},
        },
    )
    assert added.status_code == 200
    assert added.json()["ticker"] == "AAPL"

    listing = client.get("/api/saved-watchlists").json()["watchlists"]
    assert listing[0]["tickers"] == ["AAPL"]
    assert listing[0]["item_count"] == 1

    detail = client.get(f"/api/saved-watchlists/{watchlist_id}").json()
    assert detail["items"][0]["data"]["Current Price"] == 125
    assert detail["items"][0]["data"]["Fair Value"] == 150
    assert detail["items"][0]["data"]["Risk Level"] == "low"

    renamed = client.patch(
        f"/api/saved-watchlists/{watchlist_id}",
        json={"name": "Retirement"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Retirement"

    removed = client.delete(f"/api/saved-watchlists/{watchlist_id}/items/AAPL")
    assert removed.json() == {"deleted": True}
    deleted = client.delete(f"/api/saved-watchlists/{watchlist_id}")
    assert deleted.json() == {"deleted": True}


def test_saved_watchlist_api_rejects_duplicate_names(tmp_path, monkeypatch):
    from scanner.api import app as api_app

    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
    )

    assert client.post("/api/saved-watchlists", json={"name": "Ideas"}).status_code == 200
    duplicate = client.post("/api/saved-watchlists", json={"name": "ideas"})
    assert duplicate.status_code == 409


def test_saved_watchlist_report_is_downloadable_and_listed(tmp_path, monkeypatch):
    from scanner.api import app as api_app

    db_path = tmp_path / "market_data.sqlite"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(api_app.settings, market_data_cache_path=str(db_path)),
    )
    store = SQLiteSavedWatchlistStore(db_path)
    watchlist = store.create_watchlist("Long Term Ideas")
    store.add_item(
        watchlist.id,
        "AAPL",
        source="fundamentals",
        data={
            "Company Name": "Apple Inc.",
            "Current Price": 210.5,
            "Fair Value": 240,
            "Margin of Safety": 14.0,
            "Validation Label": "Validated",
            "Quality Label": "Strong",
            "Valuation Label": "Undervalued",
            "Risk Level": "Low",
        },
    )

    created = client.post(f"/api/reports/saved-watchlist/{watchlist.id}")

    assert created.status_code == 200
    report = created.json()["report"]
    assert report["type"] == "saved_watchlist"
    downloaded = client.get(f"/api/reports/{report['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content.startswith(b"%PDF")
    assert report["id"] in {item["id"] for item in client.get("/api/reports").json()}
