import pandas as pd

from scanner.config.settings import ScannerSettings
from scanner.data.cache import SQLiteMarketDataCache
from scanner.services.market_data_service import MarketDataService


def test_cache_only_market_data_service_reads_sqlite_without_provider(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "market_data.sqlite"
    history = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1_000_000, 1_100_000],
        },
        index=pd.date_range("2026-07-01", periods=2),
    )
    SQLiteMarketDataCache(db_path).store_history(
        provider="yahoo",
        ticker="AAPL",
        history=history,
    )
    monkeypatch.setattr(
        "scanner.services.market_data_service.settings",
        ScannerSettings(market_data_cache_path=str(db_path)),
    )

    def fail_provider_call(*args, **kwargs):
        raise AssertionError("provider should not be called in cache-only mode")

    monkeypatch.setattr(
        "scanner.services.market_data_service.download_price_data",
        fail_provider_call,
    )

    result = MarketDataService(cache_only=True).get_history("AAPL", period="1y")

    assert len(result) == 2
    assert "MA20" in result.columns
    assert "ATR14" in result.columns


def test_cache_only_market_data_service_returns_empty_on_cache_miss(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "market_data.sqlite"
    SQLiteMarketDataCache(db_path)
    monkeypatch.setattr(
        "scanner.services.market_data_service.settings",
        ScannerSettings(market_data_cache_path=str(db_path)),
    )

    def fail_provider_call(*args, **kwargs):
        raise AssertionError("provider should not be called in cache-only mode")

    monkeypatch.setattr(
        "scanner.services.market_data_service.download_price_data",
        fail_provider_call,
    )

    result = MarketDataService(cache_only=True).get_history("MSFT", period="1y")

    assert result.empty
