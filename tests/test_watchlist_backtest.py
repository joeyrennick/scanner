from datetime import date

import pandas as pd
import pytest

from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.backtest_service import BacktestService
from scanner.backtesting.trade import Trade
from scanner.backtesting.watchlist_loader import load_watchlist_tickers


def write_watchlist(tmp_path, content: str):
    watchlist_path = tmp_path / "watchlist.csv"
    watchlist_path.write_text(content, encoding="utf-8")
    return watchlist_path


def test_load_watchlist_tickers_filters_by_strategy_column(tmp_path):
    watchlist_path = write_watchlist(
        tmp_path,
        "\n".join(
            [
                "Ticker,Pullback Strategy,Breakout Strategy",
                "aapl,YES,NO",
                "msft,NO,YES",
                "AAPL,YES,NO",
                "nvda,YES,YES",
            ]
        ),
    )

    tickers = load_watchlist_tickers(
        watchlist_path,
        strategy_name="Pullback Strategy",
    )

    assert tickers == ["AAPL", "NVDA"]


def test_load_watchlist_tickers_can_include_all_watchlist_tickers(tmp_path):
    watchlist_path = write_watchlist(
        tmp_path,
        "\n".join(
            [
                "Ticker,Pullback Strategy",
                "AAPL,YES",
                "MSFT,NO",
                " ,YES",
                "AAPL,YES",
            ]
        ),
    )

    tickers = load_watchlist_tickers(
        watchlist_path,
        strategy_name="Pullback Strategy",
        include_all=True,
    )

    assert tickers == ["AAPL", "MSFT"]


def test_load_watchlist_tickers_requires_ticker_column(tmp_path):
    watchlist_path = write_watchlist(
        tmp_path,
        "\n".join(
            [
                "Symbol,Pullback Strategy",
                "AAPL,YES",
            ]
        ),
    )

    with pytest.raises(ValueError, match="Ticker"):
        load_watchlist_tickers(watchlist_path, strategy_name="Pullback Strategy")


def test_load_watchlist_tickers_requires_strategy_column_by_default(tmp_path):
    watchlist_path = write_watchlist(
        tmp_path,
        "\n".join(
            [
                "Ticker,Breakout Strategy",
                "AAPL,YES",
            ]
        ),
    )

    with pytest.raises(ValueError, match="--watchlist-all"):
        load_watchlist_tickers(watchlist_path, strategy_name="Pullback Strategy")


def test_load_watchlist_tickers_rejects_empty_filtered_list(tmp_path):
    watchlist_path = write_watchlist(
        tmp_path,
        "\n".join(
            [
                "Ticker,Pullback Strategy",
                "AAPL,NO",
            ]
        ),
    )

    with pytest.raises(ValueError, match="valid tickers"):
        load_watchlist_tickers(watchlist_path, strategy_name="Pullback Strategy")


def test_backtest_service_runs_supplied_ticker_list(monkeypatch):
    service = BacktestService()
    service.market_data_service.get_history = lambda ticker, period: pd.DataFrame(
        {"Close": [100, 101]},
        index=pd.date_range("2026-01-01", periods=2),
    )

    class FakeStrategy:
        name = "Fake Strategy"

    class FakeBacktester:
        def run(self, ticker, history, strategy, relative_strength, hold_days):
            return BacktestResult(
                ticker=ticker,
                strategy_name=strategy.name,
                trades=[
                    Trade(
                        ticker=ticker,
                        strategy_name=strategy.name,
                        entry_date=date(2026, 1, 1),
                        exit_date=date(2026, 1, 2),
                        entry_price=100,
                        exit_price=101,
                    )
                ],
            )

    monkeypatch.setattr(
        "scanner.backtesting.backtest_service.calculate_relative_strength",
        lambda history, benchmark: 1,
    )
    monkeypatch.setattr(
        "scanner.backtesting.backtest_service.Backtester",
        FakeBacktester,
    )

    result = service.run_tickers(
        tickers=["AAPL", "MSFT"],
        result_ticker="Watchlist",
        strategy=FakeStrategy(),
        hold_days=5,
    )

    assert result.ticker == "Watchlist"
    assert [trade.ticker for trade in result.trades] == ["AAPL", "MSFT"]
