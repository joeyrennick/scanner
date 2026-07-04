from datetime import datetime

import pandas as pd

from scanner.data.cache import CacheFetchRequest, SQLiteMarketDataCache
from scanner.data.providers.cached import CachedMarketDataProvider


class FakeProvider:
    name = "fake"

    def __init__(self, history):
        self.history = history
        self.calls = []

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        self.calls.append((ticker, period))
        return self.history


def create_history(start="2026-06-01", days=30):
    dates = pd.date_range(start, periods=days, freq="D")
    closes = [100 + index for index in range(days)]

    return pd.DataFrame(
        {
            "Open": closes,
            "High": [price + 1 for price in closes],
            "Low": [price - 1 for price in closes],
            "Close": closes,
            "Adj Close": closes,
            "Volume": [1_000_000] * days,
        },
        index=dates,
    )


def test_sqlite_cache_round_trips_price_history(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    history = create_history(days=3)

    rows_stored = cache.store_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        history=history,
    )
    loaded = cache.load_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
    )

    assert rows_stored == 3
    assert list(loaded["Close"]) == [100.0, 101.0, 102.0]
    assert list(loaded["Volume"]) == [1_000_000.0, 1_000_000.0, 1_000_000.0]


def test_cached_provider_fetches_and_stores_on_cache_miss(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    provider = FakeProvider(create_history(start="2026-06-01", days=40))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    result = cached_provider.download_price_data("AAPL", period="1mo")

    assert len(provider.calls) == 1
    assert result.empty is False
    assert cached_provider.stats.misses == 1
    assert cached_provider.stats.provider_calls == 1


def test_cached_provider_skips_provider_call_on_fresh_cache_hit(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    history = create_history(start="2026-06-01", days=40)
    provider = FakeProvider(history)
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    first = cached_provider.download_price_data("AAPL", period="1mo")
    second = cached_provider.download_price_data("AAPL", period="1mo")

    assert first.equals(second)
    assert len(provider.calls) == 1
    assert cached_provider.stats.hits == 1
    assert cached_provider.stats.misses == 1


def test_cached_provider_accepts_next_trading_day_start_after_non_trading_start(
    tmp_path,
):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    cache.store_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        history=create_history(start="2021-07-06", days=1254),
    )
    cache.record_fetch(
        request=CacheFetchRequest(
            provider="fake",
            ticker="AAPL",
            interval="1d",
            period="5y",
            start_date=datetime(2021, 7, 4).date(),
        ),
        status="success",
        rows_returned=1254,
    )
    provider = FakeProvider(create_history(start="2021-07-06", days=1254))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    result = cached_provider.download_price_data("AAPL", period="5y")

    assert result.empty is False
    assert provider.calls == []
    assert cached_provider.stats.hits == 1


def test_cached_provider_force_refresh_calls_provider_again(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    provider = FakeProvider(create_history(start="2026-06-01", days=40))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        force_refresh=True,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    cached_provider.download_price_data("AAPL", period="1mo")
    cached_provider.download_price_data("AAPL", period="1mo")

    assert len(provider.calls) == 2
    assert cached_provider.stats.hits == 0
    assert cached_provider.stats.misses == 2


def test_cached_provider_fetches_full_period_when_cache_does_not_cover_start(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    cache.store_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        history=create_history(start="2026-06-10", days=20),
    )
    provider = FakeProvider(create_history(start="2026-06-04", days=30))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    cached_provider.download_price_data("AAPL", period="1mo")

    assert provider.calls == [("AAPL", "1mo")]
    assert cached_provider.stats.misses == 1


def test_cached_provider_refreshes_overlap_window_when_cache_is_stale(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    cache.store_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        history=create_history(start="2026-06-04", days=25),
    )
    provider = FakeProvider(create_history(start="2026-06-24", days=10))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        refresh_overlap_days=10,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    result = cached_provider.download_price_data("AAPL", period="1mo")

    assert provider.calls == [("AAPL", "10d")]
    assert result.index.min().date().isoformat() == "2026-06-04"
    assert result.index.max().date().isoformat() == "2026-07-03"
    assert cached_provider.stats.misses == 1
