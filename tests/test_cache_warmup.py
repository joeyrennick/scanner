from datetime import datetime

import pandas as pd

from scanner.config.settings import ScannerSettings
from scanner.context import ScannerContext
from scanner.data.cache import SQLiteMarketDataCache
from scanner.data.providers.cached import CachedMarketDataProvider
from scanner.services.cache_warmup import CacheWarmupConfig, CacheWarmupService


class FakeBatchProvider:
    name = "fake_warmup"

    def __init__(self, histories=None, error: Exception | None = None):
        self.histories = histories or {}
        self.error = error
        self.batch_calls = []

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        raise AssertionError("single-symbol provider path should not be used")

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        self.batch_calls.append((tuple(tickers), period))

        if self.error is not None:
            raise self.error

        return {
            ticker: self.histories.get(ticker, create_history())
            for ticker in tickers
        }


def create_history(start="2026-01-05", days=130):
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


def create_context(tmp_path, provider, now):
    cache = SQLiteMarketDataCache(tmp_path / "market_data.sqlite")
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=cache,
        refresh_overlap_days=10,
        now=now,
    )
    return ScannerContext(
        settings=ScannerSettings(market_data_cache_enabled=True),
        market_data_provider=cached_provider,
    ), cache


def test_cache_warmup_preview_makes_zero_provider_calls(tmp_path):
    provider = FakeBatchProvider()
    context, _cache = create_context(
        tmp_path,
        provider=provider,
        now=lambda: datetime(2026, 7, 6, 10, 0),
    )

    result = CacheWarmupService(context=context).run(
        CacheWarmupConfig(
            tickers=["AAPL", "MSFT"],
            period="6mo",
            cache_only_preview=True,
        )
    )

    assert provider.batch_calls == []
    assert result.cache_only_preview is True
    assert result.provider_symbols_planned == 2
    assert [status.status for status in result.statuses] == [
        "skipped_preview",
        "skipped_preview",
    ]


def test_cache_warmup_batches_cold_cache_requests(tmp_path):
    provider = FakeBatchProvider()
    context, _cache = create_context(
        tmp_path,
        provider=provider,
        now=lambda: datetime(2026, 7, 6, 10, 0),
    )

    result = CacheWarmupService(context=context).run(
        CacheWarmupConfig(
            tickers=["AAPL", "MSFT", "NVDA"],
            period="6mo",
            batch_size=2,
            batch_delay_seconds=0,
        )
    )

    assert provider.batch_calls == [
        (("AAPL", "MSFT"), "6mo"),
        (("NVDA",), "6mo"),
    ]
    assert result.fetched_count == 3
    assert result.provider_batches_attempted == 2
    assert result.provider_calls_attempted == 2


def test_cache_warmup_skips_provider_for_fresh_cache(tmp_path):
    provider = FakeBatchProvider()
    context, cache = create_context(
        tmp_path,
        provider=provider,
        now=lambda: datetime(2026, 7, 6, 10, 0),
    )
    cache.store_history(
        provider=provider.name,
        ticker="AAPL",
        interval="1d",
        history=create_history(start="2026-01-05", days=182),
    )

    result = CacheWarmupService(context=context).run(
        CacheWarmupConfig(tickers=["AAPL"], period="6mo")
    )

    assert provider.batch_calls == []
    assert result.cached_count == 1
    assert result.provider_calls_attempted == 0


def test_cache_warmup_refreshes_only_overlap_for_stale_cache(tmp_path):
    provider = FakeBatchProvider({"AAPL": create_history(start="2026-07-01", days=10)})
    context, cache = create_context(
        tmp_path,
        provider=provider,
        now=lambda: datetime(2026, 7, 10, 10, 0),
    )
    cache.store_history(
        provider=provider.name,
        ticker="AAPL",
        interval="1d",
        history=create_history(start="2026-01-05", days=177),
    )

    result = CacheWarmupService(context=context).run(
        CacheWarmupConfig(tickers=["AAPL"], period="6mo")
    )

    assert provider.batch_calls == [(("AAPL",), "10d")]
    assert result.fetched_count == 1


def test_cache_warmup_stops_on_rate_limit_and_marks_remaining(
    tmp_path,
    monkeypatch,
):
    from scanner.data import market_data

    monkeypatch.setattr(market_data, "MAX_DOWNLOAD_ATTEMPTS", 1)
    provider = FakeBatchProvider(error=RuntimeError("YFRateLimitError: Too Many Requests"))
    context, _cache = create_context(
        tmp_path,
        provider=provider,
        now=lambda: datetime(2026, 7, 6, 10, 0),
    )

    result = CacheWarmupService(context=context).run(
        CacheWarmupConfig(
            tickers=["AAPL", "MSFT", "NVDA"],
            period="6mo",
            batch_size=1,
            batch_delay_seconds=0,
            stop_on_rate_limit=True,
        )
    )

    assert provider.batch_calls == [(("AAPL",), "6mo")]
    assert result.stopped_for_rate_limit is True
    assert result.provider_batches_attempted == 1
    assert [status.status for status in result.statuses] == [
        "skipped_rate_limit",
        "skipped_rate_limit",
        "skipped_rate_limit",
    ]


def test_cache_warmup_treats_empty_batch_as_possible_rate_limit(tmp_path):
    provider = FakeBatchProvider(
        {
            "AAPL": pd.DataFrame(),
            "MSFT": pd.DataFrame(),
            "NVDA": create_history(),
        }
    )
    context, _cache = create_context(
        tmp_path,
        provider=provider,
        now=lambda: datetime(2026, 7, 6, 10, 0),
    )

    result = CacheWarmupService(context=context).run(
        CacheWarmupConfig(
            tickers=["AAPL", "MSFT", "NVDA"],
            period="6mo",
            batch_size=2,
            batch_delay_seconds=0,
            stop_on_rate_limit=True,
        )
    )

    assert provider.batch_calls == [(("AAPL", "MSFT"), "6mo")]
    assert result.stopped_for_rate_limit is True
    assert [status.status for status in result.statuses] == [
        "empty",
        "empty",
        "skipped_rate_limit",
    ]
