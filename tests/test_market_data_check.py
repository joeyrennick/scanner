import pandas as pd
import pytest

import scanner.data.market_data as market_data
from scanner.data.providers.yahoo import _split_batch_history
from scanner.data.providers.yahoo import YahooMarketDataProvider


def test_check_market_data_connectivity_reports_success():
    history = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.to_datetime(["2026-07-01", "2026-07-02"]),
    )

    class FakeProvider:
        def download_price_data(self, ticker, period="5d"):
            return history

    result = market_data.check_market_data_connectivity(
        ticker="SPY",
        period="5d",
        provider=FakeProvider(),
    )

    assert result.ticker == "SPY"
    assert result.period == "5d"
    assert result.rows == 2
    assert result.first_timestamp.startswith("2026-07-01")
    assert result.last_timestamp.startswith("2026-07-02")


def test_check_market_data_connectivity_rejects_empty_history():
    class FakeProvider:
        def download_price_data(self, ticker, period="5d"):
            return pd.DataFrame()

    with pytest.raises(RuntimeError, match="No rows returned"):
        market_data.check_market_data_connectivity(
            ticker="SPY",
            period="5d",
            provider=FakeProvider(),
        )


def test_download_price_data_retries_on_rate_limit(monkeypatch):
    history = pd.DataFrame(
        {"Close": [100.0]},
        index=pd.to_datetime(["2026-07-03"]),
    )
    calls = []

    class FakeProvider:
        def download_price_data(self, ticker, period="5d"):
            calls.append((ticker, period))
            if len(calls) < 3:
                raise RuntimeError("429 Too Many Requests")
            return history

    monkeypatch.setattr(market_data.time, "sleep", lambda *_: None)
    monkeypatch.setattr(market_data.random, "uniform", lambda *_: 0)

    result = market_data.download_price_data(
        "SPY",
        period="5d",
        provider=FakeProvider(),
    )

    assert result.equals(history)
    assert len(calls) == 3


def test_download_price_data_uses_configured_provider():
    history = pd.DataFrame(
        {"Close": [123.0]},
        index=pd.to_datetime(["2026-07-03"]),
    )

    class FakeProvider:
        def download_price_data(self, ticker, period="5d"):
            return history

    market_data.register_market_data_provider("fake", lambda: FakeProvider())

    try:
        market_data.configure_market_data_cache(enabled=False)
        market_data.configure_market_data_provider("fake")
        result = market_data.download_price_data("SPY", period="5d")
    finally:
        market_data.configure_market_data_provider("yahoo")
        market_data.configure_market_data_cache(enabled=True, force_refresh=False)

    assert result.equals(history)


def test_download_price_data_uses_configured_cache(tmp_path):
    recent_dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=2)
    history = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.0, 101.0],
            "Volume": [1_000_000, 1_000_000],
        },
        index=recent_dates,
    )
    calls = []

    class FakeProvider:
        name = "fake_cache"

        def download_price_data(self, ticker, period="5d"):
            calls.append((ticker, period))
            return history

    market_data.register_market_data_provider("fake_cache", lambda: FakeProvider())

    try:
        market_data.configure_market_data_provider("fake_cache")
        market_data.configure_market_data_cache(
            enabled=True,
            force_refresh=False,
            cache_path=str(tmp_path / "cache.sqlite"),
        )

        first = market_data.download_price_data("SPY", period="5d")
        second = market_data.download_price_data("SPY", period="5d")
    finally:
        market_data.configure_market_data_provider("yahoo")
        market_data.configure_market_data_cache(
            enabled=True,
            force_refresh=False,
            cache_path="output/market_data_cache.sqlite",
        )

    assert first.equals(second)
    assert len(calls) == 1


def test_get_market_data_provider_is_cached(monkeypatch):
    created_sessions = []

    def fake_new_session():
        session = object()
        created_sessions.append(session)
        return session

    provider = YahooMarketDataProvider()
    monkeypatch.setattr("scanner.data.providers.yahoo.new_session", fake_new_session)

    first = provider._session()
    second = provider._session()

    assert first is second
    assert len(created_sessions) == 1


def test_split_batch_history_extracts_ticker_frames():
    index = pd.to_datetime(["2026-07-02", "2026-07-03"])
    history = pd.DataFrame(
        {
            ("AAPL", "Close"): [100.0, 101.0],
            ("AAPL", "Volume"): [1_000_000, 1_100_000],
            ("MSFT", "Close"): [200.0, 201.0],
            ("MSFT", "Volume"): [2_000_000, 2_100_000],
        },
        index=index,
    )

    result = _split_batch_history(history, ["AAPL", "MSFT"])

    assert list(result["AAPL"]["Close"]) == [100.0, 101.0]
    assert list(result["MSFT"]["Close"]) == [200.0, 201.0]
