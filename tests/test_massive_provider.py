import time
from threading import Event, Lock

import pandas as pd
import pytest

from scanner.data.market_data import create_market_data_provider
from scanner.data.providers.cached import CachedMarketDataProvider
from scanner.data.providers.massive import MassiveMarketDataProvider, _sector_from_sic
from scanner.security.secret_store import SQLiteSecretStore


class FakeSettings:
    def __init__(self, cache_path):
        self.market_data_cache_path = str(cache_path)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_massive_provider_downloads_daily_history(monkeypatch):
    requests = []

    def fake_get(url, params, headers, timeout):
        requests.append((url, params, headers, timeout))
        return FakeResponse(
            {
                "status": "OK",
                "results": [
                    {
                        "t": 1_780_272_000_000,
                        "o": 100.0,
                        "h": 102.0,
                        "l": 99.0,
                        "c": 101.5,
                        "v": 1_200_000,
                        "vw": 100.9,
                        "n": 12_345,
                    }
                ],
            }
        )

    monkeypatch.setattr("scanner.data.providers.massive.requests.get", fake_get)

    provider = MassiveMarketDataProvider(api_key="test-key")
    history = provider.download_price_data("BRK-B", period="5d")

    assert list(history.columns) == [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "VWAP",
        "Transactions",
        "Adj Close",
        "Dividends",
        "Stock Splits",
    ]
    assert history.iloc[0]["Close"] == 101.5
    assert history.iloc[0]["Adj Close"] == 101.5
    assert isinstance(history.index, pd.DatetimeIndex)
    assert "/v2/aggs/ticker/BRK.B/range/1/day/" in requests[0][0]
    assert requests[0][1]["adjusted"] == "true"
    assert "apiKey" not in requests[0][1]
    assert requests[0][2]["Authorization"] == "Bearer test-key"


def test_massive_provider_uses_encrypted_sqlite_key(monkeypatch, tmp_path):
    db_path = tmp_path / "market_data.sqlite"
    SQLiteSecretStore(db_path).set_secret("massive_api_key", "stored-key")
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.setattr(
        "scanner.data.providers.massive.settings",
        FakeSettings(db_path),
    )

    provider = MassiveMarketDataProvider()

    assert provider.api_key == "stored-key"


def test_massive_provider_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.setattr(
        "scanner.data.providers.massive.settings",
        FakeSettings(tmp_path / "market_data.sqlite"),
    )

    with pytest.raises(RuntimeError, match="MASSIVE_API_KEY"):
        MassiveMarketDataProvider().download_price_data("AAPL", period="5d")


def test_market_data_factory_registers_massive_without_cache():
    provider = create_market_data_provider("massive", cache_enabled=False)

    assert isinstance(provider, MassiveMarketDataProvider)


def test_market_data_factory_registers_polygon_alias_with_cache(tmp_path):
    provider = create_market_data_provider(
        "polygon",
        cache_enabled=True,
        cache_path=str(tmp_path / "cache.sqlite"),
    )

    assert isinstance(provider, CachedMarketDataProvider)
    assert provider.name == "polygon"
    assert isinstance(provider.provider, MassiveMarketDataProvider)


def test_massive_historical_batch_counts_one_provider_call_per_symbol():
    provider = MassiveMarketDataProvider(api_key="test-key")

    assert provider.provider_call_count_for_batch(["AAPL", "MSFT"]) == 2


def test_massive_batch_downloads_concurrently(monkeypatch):
    provider = MassiveMarketDataProvider(api_key="test-key")
    active = 0
    max_active = 0
    lock = Lock()
    overlapping = Event()

    def fake_download(ticker, period="1y"):
        nonlocal active, max_active

        with lock:
            active += 1
            max_active = max(max_active, active)
            if active >= 2:
                overlapping.set()

        assert overlapping.wait(timeout=1)
        time.sleep(0.01)

        with lock:
            active -= 1

        return pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime(["2026-01-01"]))

    monkeypatch.setattr(provider, "download_price_data", fake_download)

    results = provider.download_price_data_batch(["AAPL", "MSFT", "NVDA"], period="5d")

    assert set(results) == {"AAPL", "MSFT", "NVDA"}
    assert max_active >= 2


def test_massive_company_profiles_supply_name_and_sector(monkeypatch):
    def fake_get(url, headers, timeout):
        assert "/v3/reference/tickers/AAPL" in url
        return FakeResponse(
            {"results": {"name": "Apple Inc.", "sic_code": "3571"}}
        )

    monkeypatch.setattr("scanner.data.providers.massive.requests.get", fake_get)
    provider = MassiveMarketDataProvider(api_key="test-key")

    assert provider.download_company_profiles_batch(["AAPL"]) == {
        "AAPL": {"name": "Apple Inc.", "sector": "Information Technology"}
    }
    assert _sector_from_sic("6021") == "Financials"
    assert _sector_from_sic("6531") == "Real Estate"


def test_massive_provider_downloads_fundamental_datasets(monkeypatch):
    calls = []

    def fake_get(url, headers, timeout, params=None):
        calls.append((url, params))
        if "/v3/reference/tickers/" in url:
            return FakeResponse({"results": {"ticker": "AAPL", "name": "Apple"}})
        return FakeResponse({"status": "OK", "results": [{"ticker": "AAPL"}]})

    monkeypatch.setattr("scanner.data.providers.massive.requests.get", fake_get)
    result = MassiveMarketDataProvider(api_key="test-key").download_fundamental_data("AAPL")

    assert result["profile"]["name"] == "Apple"
    assert len(result["income_statements"]) == 1
    assert len(result["balance_sheets"]) == 1
    assert len(result["cash_flow_statements"]) == 1
    assert len(result["ratios"]) == 1
    assert any("/stocks/financials/v1/ratios" in url for url, _params in calls)
