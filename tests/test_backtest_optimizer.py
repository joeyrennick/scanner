import pandas as pd
import pytest

from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtest_optimizer import BacktestOptimizer
from scanner.backtesting.trade import Trade


class FakeResult:
    def __init__(self, strategy_name: str, trades: list[Trade]):
        self.strategy_name = strategy_name
        self.trades = trades

    @property
    def statistics(self):
        from scanner.backtesting.backtest_statistics import BacktestStatistics

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
                "tickers": tickers,
                "result_ticker": result_ticker,
                "config": config,
                "hold_days": hold_days,
            }
        )

        return FakeResult(
            strategy_name=strategy.name,
            trades=_trades_for_config(config, strategy.config),
        )


def _trades_for_config(config, strategy_config):
    winning_return = (
        config.hold_days
        + int(config.allow_overlapping_trades)
        + strategy_config.min_relative_volume
    )
    losing_return = -1.0

    return [
        Trade(
            ticker="AAA",
            strategy_name="Pullback Strategy",
            entry_date=pd.Timestamp("2026-01-01").date(),
            exit_date=pd.Timestamp("2026-01-02").date(),
            entry_price=100,
            exit_price=100 + winning_return,
        ),
        Trade(
            ticker="AAA",
            strategy_name="Pullback Strategy",
            entry_date=pd.Timestamp("2026-01-03").date(),
            exit_date=pd.Timestamp("2026-01-04").date(),
            entry_price=100,
            exit_price=100 + losing_return,
        ),
    ]


def test_build_candidates_expands_backtest_and_strategy_parameters():
    optimizer = BacktestOptimizer(RecordingBacktestService())

    candidates = optimizer.build_candidates(
        strategy_name="pullback",
        base_config=BacktestConfig(hold_days=5, min_history_days=252),
        hold_days=[3, 5],
        min_history_days=[126],
        allow_overlapping_trades=[True, False],
        strategy_parameters={
            "max_distance_from_ma20": [0.03, 0.05],
            "min_relative_volume": [1.0, 1.5],
        },
    )

    assert len(candidates) == 16
    assert candidates[0].parameters == {
        "hold_days": 3,
        "min_history_days": 126,
        "allow_overlapping_trades": True,
        "entry_reset_policy": "none",
        "max_distance_from_ma20": 0.03,
        "min_relative_volume": 1.0,
    }


def test_sweep_parameters_ranks_results_and_passes_config_to_service():
    service = RecordingBacktestService()
    optimizer = BacktestOptimizer(service)

    results = optimizer.sweep_parameters(
        ticker="AAPL",
        universe=None,
        strategy_name="pullback",
        base_config=BacktestConfig(hold_days=5, min_history_days=252),
        hold_days=[3, 7],
        min_history_days=[126],
        allow_overlapping_trades=[False, True],
        entry_reset_policies=["none", "signal_off"],
        strategy_parameters={"min_relative_volume": [1.0, 1.5]},
        sort_by="expectancy",
    )

    assert len(results) == 16
    assert len(service.calls) == 16

    best = results[0]
    assert best.candidate.backtest_config.hold_days == 7
    assert best.candidate.backtest_config.allow_overlapping_trades is True
    assert best.candidate.strategy_parameters["min_relative_volume"] == 1.5
    assert best.candidate.backtest_config.entry_reset_policy in {
        "none",
        "signal_off",
    }
    assert best.to_dict()["Profit Factor"] > 1


def test_sweep_filters_by_minimum_trade_count():
    service = RecordingBacktestService()
    optimizer = BacktestOptimizer(service)

    results = optimizer.sweep_parameters(
        ticker="AAPL",
        universe=None,
        strategy_name="pullback",
        base_config=BacktestConfig(),
        min_trades=3,
    )

    assert results == []


def test_sweep_rejects_unknown_strategy_parameter():
    optimizer = BacktestOptimizer(RecordingBacktestService())

    with pytest.raises(ValueError, match="Unknown strategy sweep parameter"):
        optimizer.build_candidates(
            strategy_name="pullback",
            base_config=BacktestConfig(),
            strategy_parameters={"unknown": [1]},
        )


def test_export_results_writes_ranked_sweep_csv(tmp_path):
    optimizer = BacktestOptimizer(RecordingBacktestService())
    results = optimizer.sweep_parameters(
        ticker="AAPL",
        universe=None,
        strategy_name="pullback",
        base_config=BacktestConfig(),
        hold_days=[3],
        strategy_parameters={"min_relative_volume": [1.0]},
    )
    output_path = tmp_path / "sweep.csv"

    optimizer.export_results(results, output_path)

    exported = pd.read_csv(output_path)
    assert list(exported.columns) == [
        "Strategy",
        "Hold Days",
        "Min History Days",
        "Allow Overlap",
        "Entry Reset Policy",
        "Trades",
        "Win Rate",
        "Average Return",
        "Expectancy",
        "Profit Factor",
        "Best Trade",
        "Worst Trade",
        "Strategy Param: min_relative_volume",
    ]
    assert len(exported) == 1
