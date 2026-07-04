import pandas as pd
import pytest

from scanner.data.cache import SQLiteMarketDataCache
from scanner.services import price_filter
from scanner.services.price_filter import filter_tickers_by_price


def test_price_filter_uses_recent_cached_close_without_provider_call(
    tmp_path,
    monkeypatch,
):
    cache_path = tmp_path / "market_data.sqlite"
    cache = SQLiteMarketDataCache(cache_path)
    cache.store_history(
        provider="fake",
        ticker="AAPL",
        history=pd.DataFrame(
            {"Close": [42.0]},
            index=pd.to_datetime(["2026-07-03"]),
        ),
    )

    def fail_download(*_args, **_kwargs):
        raise AssertionError("provider should not be called")

    monkeypatch.setattr(price_filter, "download_price_data_batch", fail_download)

    result = filter_tickers_by_price(
        tickers=["AAPL"],
        min_price=20,
        max_price=50,
        provider_name="fake",
        cache_path=str(cache_path),
        max_cached_price_age_days=9999,
        max_workers=1,
    )

    assert result.tickers == ["AAPL"]
    assert result.decisions[0].source == "cache"
    assert result.decisions[0].price == 42.0


def test_price_filter_fetches_sample_when_price_is_not_cached(
    tmp_path,
    monkeypatch,
):
    calls = []

    def fake_download(tickers, period):
        calls.append((tuple(tickers), period))
        return {
            ticker: pd.DataFrame(
                {"Close": [35.0]},
                index=pd.to_datetime(["2026-07-03"]),
            )
            for ticker in tickers
        }

    monkeypatch.setattr(price_filter, "download_price_data_batch", fake_download)

    result = filter_tickers_by_price(
        tickers=["MSFT"],
        min_price=20,
        max_price=50,
        provider_name="fake",
        cache_path=str(tmp_path / "market_data.sqlite"),
        sample_period="5d",
        batch_size=1,
    )

    assert calls == [(("MSFT",), "5d")]
    assert result.tickers == ["MSFT"]
    assert result.decisions[0].source == "provider"


def test_price_filter_skips_out_of_range_tickers(tmp_path, monkeypatch):
    prices = {
        "LOW": 12.0,
        "MID": 35.0,
        "HIGH": 72.0,
    }

    def fake_download(tickers, period):
        return {
            ticker: pd.DataFrame(
                {"Close": [prices[ticker]]},
                index=pd.to_datetime(["2026-07-03"]),
            )
            for ticker in tickers
        }

    monkeypatch.setattr(price_filter, "download_price_data_batch", fake_download)

    result = filter_tickers_by_price(
        tickers=["LOW", "MID", "HIGH"],
        min_price=20,
        max_price=50,
        provider_name="fake",
        cache_path=str(tmp_path / "market_data.sqlite"),
        batch_size=3,
    )

    assert result.tickers == ["MID"]
    assert result.checked_count == 3
    assert result.skipped_count == 2


def test_price_filter_limits_uncached_provider_calls(tmp_path, monkeypatch):
    calls = []

    def fake_download(tickers, period):
        calls.append((tuple(tickers), period))
        return {
            ticker: pd.DataFrame(
                {"Close": [35.0]},
                index=pd.to_datetime(["2026-07-03"]),
            )
            for ticker in tickers
        }

    monkeypatch.setattr(price_filter, "download_price_data_batch", fake_download)

    result = filter_tickers_by_price(
        tickers=["AAPL", "MSFT", "NVDA"],
        min_price=20,
        max_price=50,
        provider_name="fake",
        cache_path=str(tmp_path / "market_data.sqlite"),
        batch_size=1,
        max_provider_calls=2,
    )

    assert calls == [(("AAPL",), "5d"), (("MSFT",), "5d")]
    assert result.tickers == ["AAPL", "MSFT"]
    assert result.provider_calls_attempted == 2
    assert result.decisions[2].source == "not_checked"
    assert result.decisions[2].reason == "Provider symbol limit reached"


def test_price_filter_stops_after_rate_limit(tmp_path, monkeypatch):
    calls = []

    def fake_download(tickers, period):
        calls.append((tuple(tickers), period))
        if "AAPL" in tickers:
            raise RuntimeError("YFRateLimitError: Too Many Requests")

        return {
            ticker: pd.DataFrame(
                {"Close": [35.0]},
                index=pd.to_datetime(["2026-07-03"]),
            )
            for ticker in tickers
        }

    monkeypatch.setattr(price_filter, "download_price_data_batch", fake_download)

    result = filter_tickers_by_price(
        tickers=["AAPL", "MSFT", "NVDA"],
        min_price=20,
        max_price=50,
        provider_name="fake",
        cache_path=str(tmp_path / "market_data.sqlite"),
        batch_size=1,
        max_provider_calls=3,
    )

    assert calls == [(("AAPL",), "5d")]
    assert result.tickers == []
    assert result.provider_calls_attempted == 1
    assert result.stopped_for_rate_limit is True
    assert result.decisions[1].reason == "Stopped after provider rate limit"


def test_price_filter_limits_provider_batches(tmp_path, monkeypatch):
    calls = []

    def fake_download(tickers, period):
        calls.append((tuple(tickers), period))
        return {
            ticker: pd.DataFrame(
                {"Close": [35.0]},
                index=pd.to_datetime(["2026-07-03"]),
            )
            for ticker in tickers
        }

    monkeypatch.setattr(price_filter, "download_price_data_batch", fake_download)

    result = filter_tickers_by_price(
        tickers=["AAPL", "MSFT", "NVDA", "TSLA", "AMD"],
        min_price=20,
        max_price=50,
        provider_name="fake",
        cache_path=str(tmp_path / "market_data.sqlite"),
        batch_size=2,
        max_provider_calls=None,
        max_provider_batches=2,
    )

    assert calls == [
        (("AAPL", "MSFT"), "5d"),
        (("NVDA", "TSLA"), "5d"),
    ]
    assert result.tickers == ["AAPL", "MSFT", "NVDA", "TSLA"]
    assert result.provider_batches_attempted == 2
    assert result.decisions[4].source == "not_checked"
    assert result.decisions[4].reason == "Provider batch limit reached"


def test_price_filter_stops_when_entire_batch_returns_no_prices(tmp_path, monkeypatch):
    calls = []

    def fake_download(tickers, period):
        calls.append((tuple(tickers), period))
        return {ticker: pd.DataFrame() for ticker in tickers}

    monkeypatch.setattr(price_filter, "download_price_data_batch", fake_download)

    result = filter_tickers_by_price(
        tickers=["AAPL", "MSFT", "NVDA", "TSLA"],
        min_price=20,
        max_price=50,
        provider_name="fake",
        cache_path=str(tmp_path / "market_data.sqlite"),
        batch_size=2,
        max_provider_calls=None,
        max_provider_batches=2,
    )

    assert calls == [(("AAPL", "MSFT"), "5d")]
    assert result.provider_batches_attempted == 1
    assert result.stopped_for_rate_limit is True
    assert result.decisions[2].reason == "Stopped after provider rate limit"


def test_price_filter_rejects_invalid_range(tmp_path):
    with pytest.raises(ValueError, match="min_price"):
        filter_tickers_by_price(
            tickers=["AAPL"],
            min_price=50,
            max_price=20,
            cache_path=str(tmp_path / "market_data.sqlite"),
        )
