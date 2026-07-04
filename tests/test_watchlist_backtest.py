from datetime import date

import pandas as pd
import pytest

from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.backtest_service import BacktestService
from scanner.backtesting.trade import Trade
from scanner.config.settings import ScannerSettings
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


def test_backtest_service_runs_named_universe(monkeypatch):
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
    monkeypatch.setattr(
        "scanner.backtesting.backtest_service.UniverseProvider.get_universe_tickers",
        lambda self, universe: ["DIA", "IBM"],
    )

    result = service.run_universe(
        universe="djia",
        strategy=FakeStrategy(),
        hold_days=5,
    )

    assert result.ticker == "DJIA"
    assert [trade.ticker for trade in result.trades] == ["DIA", "IBM"]


def test_backtest_service_uses_shared_worker_setting(monkeypatch):
    service = BacktestService()
    service.market_data_service.get_history = lambda ticker, period: pd.DataFrame(
        {"Close": [100, 101]},
        index=pd.date_range("2026-01-01", periods=2),
    )

    class FakeStrategy:
        name = "Fake Strategy"

    class FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    class FakeExecutor:
        captured_max_workers = None

        def __init__(self, max_workers):
            FakeExecutor.captured_max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, ticker):
            return FakeFuture(
                BacktestResult(
                    ticker=ticker,
                    strategy_name=FakeStrategy.name,
                    trades=[
                        Trade(
                            ticker=ticker,
                            strategy_name=FakeStrategy.name,
                            entry_date=date(2026, 1, 1),
                            exit_date=date(2026, 1, 2),
                            entry_price=100,
                            exit_price=101,
                        )
                    ],
                )
            )

    monkeypatch.setattr(
        "scanner.backtesting.backtest_service.settings",
        ScannerSettings(max_workers=7),
    )
    monkeypatch.setattr(
        "scanner.backtesting.backtest_service.ThreadPoolExecutor",
        FakeExecutor,
    )
    monkeypatch.setattr(
        "scanner.backtesting.backtest_service.as_completed",
        lambda futures: futures,
    )

    result = service.run_tickers(
        tickers=["AAPL", "MSFT"],
        result_ticker="Watchlist",
        strategy=FakeStrategy(),
        hold_days=5,
    )

    assert FakeExecutor.captured_max_workers == 7
    assert result.ticker == "Watchlist"
