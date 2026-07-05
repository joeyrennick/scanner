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


class FakeBatchProvider:
    name = "fake"

    def __init__(self, histories):
        self.histories = histories
        self.batch_calls = []

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        raise AssertionError("single-symbol provider path should not be used")

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        self.batch_calls.append((tuple(tickers), period))
        return {
            ticker: self.histories.get(ticker, pd.DataFrame())
            for ticker in tickers
        }


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


def test_sqlite_cache_overview_reports_refresh_staleness(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    history = create_history(start="2026-07-01", days=3)
    cache.store_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        history=history,
    )
    cache.store_history(
        provider="fake",
        ticker="MSFT",
        interval="1d",
        history=history,
    )
    cache.record_fetch(
        request=CacheFetchRequest(
            provider="fake",
            ticker="AAPL",
            interval="1d",
            period="5d",
            start_date=datetime(2026, 6, 29).date(),
        ),
        status="success",
        rows_returned=3,
    )

    overview = cache.overview(
        provider="fake",
        today=datetime(2026, 7, 6).date(),
    )

    assert overview.provider == "fake"
    assert overview.cached_tickers == 2
    assert overview.cached_bars == 6
    assert overview.earliest_bar_date.isoformat() == "2026-07-01"
    assert overview.latest_bar_date.isoformat() == "2026-07-03"
    assert overview.last_successful_refresh is not None
    assert overview.days_since_refresh == (
        datetime(2026, 7, 6).date() - overview.last_successful_refresh.date()
    ).days


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


def test_sqlite_cache_prunes_price_bars_before_cutoff(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    cache.store_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        history=create_history(start="2020-01-01", days=10),
    )

    deleted_rows = cache.prune_price_bars_before(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        cutoff_date=datetime(2020, 1, 6).date(),
    )
    loaded = cache.load_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
    )

    assert deleted_rows == 5
    assert loaded.index.min().date().isoformat() == "2020-01-06"


def test_cached_provider_enforces_retention_after_single_fetch(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    provider = FakeProvider(create_history(start="2020-07-01", days=2200))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        retention_years=5,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    result = cached_provider.download_price_data("AAPL", period="10y")

    assert result.index.min().date().isoformat() == "2021-07-04"
    assert cache.load_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
    ).index.min().date().isoformat() == "2021-07-04"


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
        history=create_history(start="2021-07-06", days=1825),
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
        rows_returned=1825,
    )
    provider = FakeProvider(create_history(start="2021-07-06", days=1825))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    result = cached_provider.download_price_data("AAPL", period="5y")

    assert result.empty is False
    assert provider.calls == []
    assert cached_provider.stats.hits == 1


def test_cached_provider_accepts_recent_latest_bar_across_market_holiday(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    cache.store_history(
        provider="fake",
        ticker="AAPL",
        interval="1d",
        history=create_history(start="2025-07-07", days=361),
    )
    provider = FakeProvider(create_history(start="2025-07-07", days=361))
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    result = cached_provider.download_price_data("AAPL", period="1y")

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


def test_cached_provider_batch_fetches_multiple_tickers_in_one_provider_call(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    provider = FakeBatchProvider(
        {
            "AAPL": create_history(start="2026-06-01", days=40),
            "MSFT": create_history(start="2026-06-01", days=40),
        }
    )
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    first = cached_provider.download_price_data_batch(
        ["AAPL", "MSFT"],
        period="1mo",
    )
    second = cached_provider.download_price_data_batch(
        ["AAPL", "MSFT"],
        period="1mo",
    )

    assert provider.batch_calls == [(("AAPL", "MSFT"), "1mo")]
    assert set(first) == {"AAPL", "MSFT"}
    assert first["AAPL"].empty is False
    assert second["MSFT"].empty is False
    assert cached_provider.stats.provider_calls == 1
    assert cached_provider.stats.hits == 2


def test_cached_provider_enforces_retention_after_batch_fetch(tmp_path):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    provider = FakeBatchProvider(
        {
            "AAPL": create_history(start="2020-07-01", days=2200),
            "MSFT": create_history(start="2020-07-01", days=2200),
        }
    )
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        retention_years=5,
        now=lambda: datetime(2026, 7, 4, 10, 0),
    )

    result = cached_provider.download_price_data_batch(
        ["AAPL", "MSFT"],
        period="10y",
    )

    assert result["AAPL"].index.min().date().isoformat() == "2021-07-04"
    assert result["MSFT"].index.min().date().isoformat() == "2021-07-04"
