import pandas as pd
import pytest

from yfinance.exceptions import YFRateLimitError

import scanner.data.market_data as market_data
from scanner.data.market_data import (
    check_market_data_connectivity,
    download_price_data,
)


def test_check_market_data_connectivity_reports_success(monkeypatch):
    history = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.to_datetime(["2026-07-01", "2026-07-02"]),
    )

    monkeypatch.setattr(
        "scanner.data.market_data.download_price_data",
        lambda ticker, period="5d": history,
    )

    result = check_market_data_connectivity(ticker="SPY", period="5d")

    assert result.ticker == "SPY"
    assert result.period == "5d"
    assert result.rows == 2
    assert result.first_timestamp.startswith("2026-07-01")
    assert result.last_timestamp.startswith("2026-07-02")


def test_check_market_data_connectivity_rejects_empty_history(monkeypatch):
    monkeypatch.setattr(
        "scanner.data.market_data.download_price_data",
        lambda ticker, period="5d": pd.DataFrame(),
    )

    with pytest.raises(RuntimeError, match="No rows returned"):
        check_market_data_connectivity(ticker="SPY", period="5d")


def test_download_price_data_retries_on_rate_limit(monkeypatch):
    history = pd.DataFrame(
        {"Close": [100.0]},
        index=pd.to_datetime(["2026-07-03"]),
    )
    calls = []

    def fake_download(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) < 3:
            raise YFRateLimitError()
        return history

    monkeypatch.setattr(market_data.yf, "download", fake_download)
    monkeypatch.setattr(market_data.time, "sleep", lambda *_: None)
    monkeypatch.setattr(market_data.random, "uniform", lambda *_: 0)
    market_data.get_market_data_session.cache_clear()
    monkeypatch.setattr(
        market_data,
        "get_market_data_session",
        lambda: object(),
    )

    result = download_price_data("SPY", period="5d")

    assert result.equals(history)
    assert len(calls) == 3


def test_get_market_data_session_is_cached(monkeypatch):
    created_sessions = []

    def fake_new_session():
        session = object()
        created_sessions.append(session)
        return session

    market_data.get_market_data_session.cache_clear()
    monkeypatch.setattr(market_data, "new_session", fake_new_session)

    first = market_data.get_market_data_session()
    second = market_data.get_market_data_session()

    assert first is second
    assert len(created_sessions) == 1
