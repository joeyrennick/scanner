import pandas as pd
import pytest

from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtest_statistics import BacktestStatistics
from scanner.backtesting.trade import Trade
from scanner.backtesting.walk_forward import WalkForwardTester


class FakeResult:
    def __init__(self, strategy_name: str, trades: list[Trade]):
        self.strategy_name = strategy_name
        self.trades = trades

    @property
    def statistics(self):
        return BacktestStatistics(self.trades)


class RecordingBacktestService:
    def __init__(self):
        self.calls = []

    def run(
        self,
        ticker,
        universe,
        strategy,
        tickers=None,
        result_ticker=None,
        config=None,
        hold_days=None,
    ):
        self.calls.append(
            {
                "ticker": ticker,
                "universe": universe,
                "strategy_config": strategy.config,
                "config": config,
                "tickers": tickers,
                "result_ticker": result_ticker,
                "hold_days": hold_days,
            }
        )

        winning_return = config.hold_days + strategy.config.min_relative_volume
        return FakeResult(
            strategy_name=strategy.name,
            trades=[
                Trade(
                    ticker="AAA",
                    strategy_name=strategy.name,
                    entry_date=pd.Timestamp("2026-01-01").date(),
                    exit_date=pd.Timestamp("2026-01-02").date(),
                    entry_price=100,
                    exit_price=100 + winning_return,
                ),
                Trade(
                    ticker="AAA",
                    strategy_name=strategy.name,
                    entry_date=pd.Timestamp("2026-01-03").date(),
                    exit_date=pd.Timestamp("2026-01-04").date(),
                    entry_price=100,
                    exit_price=99,
                ),
            ],
        )


def test_build_windows_creates_complete_rolling_train_test_windows():
    windows = WalkForwardTester(RecordingBacktestService()).build_windows(
        start_date="2026-01-01",
        end_date="2026-06-30",
        train_months=3,
        test_months=1,
        step_months=1,
    )

    assert len(windows) == 3
    assert windows[0].train_start.date().isoformat() == "2026-01-01"
    assert windows[0].train_end.date().isoformat() == "2026-03-31"
    assert windows[0].test_start.date().isoformat() == "2026-04-01"
    assert windows[0].test_end.date().isoformat() == "2026-04-30"
    assert windows[2].train_start.date().isoformat() == "2026-03-01"
    assert windows[2].test_end.date().isoformat() == "2026-06-30"


def test_build_windows_rejects_ranges_without_complete_windows():
    with pytest.raises(ValueError, match="No complete walk-forward windows"):
        WalkForwardTester(RecordingBacktestService()).build_windows(
            start_date="2026-01-01",
            end_date="2026-03-31",
            train_months=3,
            test_months=1,
        )


def test_walk_forward_optimizes_training_window_and_tests_forward_window():
    service = RecordingBacktestService()
    tester = WalkForwardTester(service)

    results = tester.run(
        ticker="AAPL",
        universe=None,
        strategy_name="pullback",
        base_config=BacktestConfig(history_period="1y", min_history_days=63),
        start_date="2026-01-01",
        end_date="2026-06-30",
        train_months=3,
        test_months=1,
        step_months=1,
        hold_days=[3, 7],
        strategy_parameters={"min_relative_volume": [1.0]},
    )

    assert len(results) == 3
    assert len(service.calls) == 9

    first_training_call = service.calls[0]
    first_forward_call = service.calls[2]

    assert first_training_call["config"].signal_start_date.isoformat() == "2026-01-01"
    assert first_training_call["config"].signal_end_date.isoformat() == "2026-03-31"
    assert first_forward_call["config"].signal_start_date.isoformat() == "2026-04-01"
    assert first_forward_call["config"].signal_end_date.isoformat() == "2026-04-30"

    first_result = results[0].to_dict()
    assert first_result["Selected Hold Days"] == 7
    assert first_result["Forward Trades"] == 2
    assert first_result["Selected Strategy Param: min_relative_volume"] == 1.0


def test_walk_forward_summary_and_export(tmp_path):
    service = RecordingBacktestService()
    tester = WalkForwardTester(service)
    results = tester.run(
        ticker="AAPL",
        universe=None,
        strategy_name="pullback",
        base_config=BacktestConfig(history_period="1y", min_history_days=63),
        start_date="2026-01-01",
        end_date="2026-04-30",
        train_months=3,
        test_months=1,
        hold_days=[3],
        strategy_parameters={"min_relative_volume": [1.0]},
    )
    output_path = tmp_path / "walk_forward.csv"

    summary = tester.summary(results)
    tester.export_results(results, output_path)

    assert summary.windows == 1
    assert summary.forward_windows_with_trades == 1
    assert summary.profitable_forward_windows == 1

    exported = pd.read_csv(output_path)
    assert list(exported.columns) == [
        "Train Start",
        "Train End",
        "Test Start",
        "Test End",
        "Selected Hold Days",
        "Selected Min History Days",
        "Selected Allow Overlap",
        "Training Trades",
        "Training Expectancy",
        "Training Profit Factor",
        "Forward Trades",
        "Forward Win Rate",
        "Forward Average Return",
        "Forward Expectancy",
        "Forward Profit Factor",
        "Forward Best Trade",
        "Forward Worst Trade",
        "Selected Strategy Param: min_relative_volume",
    ]
