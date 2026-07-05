from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtest_optimizer import (
    BacktestOptimizer,
    ParameterSweepCandidate,
    ParameterSweepResult,
)
from scanner.strategies.strategy_registry import StrategyRegistry


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


@dataclass(frozen=True)
class WalkForwardResult:
    window: WalkForwardWindow
    training_result: ParameterSweepResult | None
    forward_result: ParameterSweepResult | None

    def to_dict(self) -> dict[str, Any]:
        row = {
            "Train Start": self.window.train_start.date().isoformat(),
            "Train End": self.window.train_end.date().isoformat(),
            "Test Start": self.window.test_start.date().isoformat(),
            "Test End": self.window.test_end.date().isoformat(),
        }

        if self.training_result is None or self.forward_result is None:
            row.update(
                {
                    "Selected Hold Days": None,
                    "Selected Min History Days": None,
                    "Selected Allow Overlap": None,
                    "Selected Entry Reset Policy": None,
                    "Training Trades": 0,
                    "Training Expectancy": 0.0,
                    "Training Profit Factor": 0.0,
                    "Forward Trades": 0,
                    "Forward Win Rate": 0.0,
                    "Forward Average Return": 0.0,
                    "Forward Expectancy": 0.0,
                    "Forward Profit Factor": 0.0,
                    "Forward Best Trade": 0.0,
                    "Forward Worst Trade": 0.0,
                }
            )
            return row

        training_stats = self.training_result.result.statistics
        forward_stats = self.forward_result.result.statistics
        candidate = self.training_result.candidate
        row.update(
            {
                "Selected Hold Days": candidate.backtest_config.hold_days,
                "Selected Min History Days": candidate.backtest_config.min_history_days,
                "Selected Allow Overlap": (
                    candidate.backtest_config.allow_overlapping_trades
                ),
                "Selected Entry Reset Policy": (
                    candidate.backtest_config.entry_reset_policy
                ),
                "Training Trades": training_stats.total_trades,
                "Training Expectancy": training_stats.expectancy,
                "Training Profit Factor": training_stats.profit_factor,
                "Forward Trades": forward_stats.total_trades,
                "Forward Win Rate": forward_stats.win_rate,
                "Forward Average Return": forward_stats.average_return,
                "Forward Expectancy": forward_stats.expectancy,
                "Forward Profit Factor": forward_stats.profit_factor,
                "Forward Best Trade": forward_stats.best_trade_return,
                "Forward Worst Trade": forward_stats.worst_trade_return,
            }
        )

        for name, value in candidate.strategy_parameters.items():
            row[f"Selected Strategy Param: {name}"] = value

        return row


@dataclass(frozen=True)
class WalkForwardSummary:
    windows: int
    forward_windows_with_trades: int
    profitable_forward_windows: int
    average_forward_return: float
    average_forward_expectancy: float
    average_forward_profit_factor: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "Windows": self.windows,
            "Forward Windows With Trades": self.forward_windows_with_trades,
            "Profitable Forward Windows": self.profitable_forward_windows,
            "Average Forward Return": self.average_forward_return,
            "Average Forward Expectancy": self.average_forward_expectancy,
            "Average Forward Profit Factor": self.average_forward_profit_factor,
        }


class WalkForwardTester:
    def __init__(self, service):
        self.service = service
        self.optimizer = BacktestOptimizer(service)

    def run(
        self,
        ticker: str | None,
        universe: str | None,
        strategy_name: str,
        base_config: BacktestConfig,
        start_date: str,
        end_date: str,
        train_months: int,
        test_months: int,
        step_months: int | None = None,
        tickers: list[str] | None = None,
        result_ticker: str | None = None,
        hold_days: list[int] | None = None,
        min_history_days: list[int] | None = None,
        allow_overlapping_trades: list[bool] | None = None,
        entry_reset_policies: list[str] | None = None,
        strategy_parameters: dict[str, list[Any]] | None = None,
        sort_by: str = "expectancy",
        min_trades: int = 1,
    ) -> list[WalkForwardResult]:
        windows = self.build_windows(
            start_date=start_date,
            end_date=end_date,
            train_months=train_months,
            test_months=test_months,
            step_months=step_months,
        )
        results = []

        for window in windows:
            train_config = replace(
                base_config,
                signal_start_date=window.train_start.date(),
                signal_end_date=window.train_end.date(),
            )
            training_results = self.optimizer.sweep_parameters(
                ticker=ticker,
                universe=universe,
                strategy_name=strategy_name,
                base_config=train_config,
                tickers=tickers,
                result_ticker=result_ticker,
                hold_days=hold_days,
                min_history_days=min_history_days,
                allow_overlapping_trades=allow_overlapping_trades,
                entry_reset_policies=entry_reset_policies,
                strategy_parameters=strategy_parameters,
                sort_by=sort_by,
                min_trades=min_trades,
            )
            best_training_result = training_results[0] if training_results else None
            forward_result = None

            if best_training_result is not None:
                forward_result = self._run_forward_window(
                    ticker=ticker,
                    universe=universe,
                    strategy_name=strategy_name,
                    training_result=best_training_result,
                    window=window,
                    tickers=tickers,
                    result_ticker=result_ticker,
                )

            results.append(
                WalkForwardResult(
                    window=window,
                    training_result=best_training_result,
                    forward_result=forward_result,
                )
            )

        return results

    def build_windows(
        self,
        start_date: str,
        end_date: str,
        train_months: int,
        test_months: int,
        step_months: int | None = None,
    ) -> list[WalkForwardWindow]:
        if train_months <= 0:
            raise ValueError("train_months must be greater than zero")

        if test_months <= 0:
            raise ValueError("test_months must be greater than zero")

        step_months = step_months or test_months

        if step_months <= 0:
            raise ValueError("step_months must be greater than zero")

        start = pd.Timestamp(start_date).normalize()
        end = pd.Timestamp(end_date).normalize()

        if start >= end:
            raise ValueError("start_date must be before end_date")

        windows = []
        train_start = start

        while True:
            train_end = (
                train_start
                + pd.DateOffset(months=train_months)
                - pd.Timedelta(days=1)
            )
            test_start = train_end + pd.Timedelta(days=1)
            test_end = (
                test_start
                + pd.DateOffset(months=test_months)
                - pd.Timedelta(days=1)
            )

            if test_end > end:
                break

            windows.append(
                WalkForwardWindow(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
            train_start = train_start + pd.DateOffset(months=step_months)

        if not windows:
            raise ValueError("No complete walk-forward windows fit the date range")

        return windows

    def summary(self, results: list[WalkForwardResult]) -> WalkForwardSummary:
        forward_stats = [
            result.forward_result.result.statistics
            for result in results
            if result.forward_result is not None
        ]
        forward_stats_with_trades = [
            stats for stats in forward_stats if stats.total_trades > 0
        ]

        if not forward_stats_with_trades:
            return WalkForwardSummary(
                windows=len(results),
                forward_windows_with_trades=0,
                profitable_forward_windows=0,
                average_forward_return=0.0,
                average_forward_expectancy=0.0,
                average_forward_profit_factor=0.0,
            )

        return WalkForwardSummary(
            windows=len(results),
            forward_windows_with_trades=len(forward_stats_with_trades),
            profitable_forward_windows=sum(
                1 for stats in forward_stats_with_trades if stats.expectancy > 0
            ),
            average_forward_return=sum(
                stats.average_return for stats in forward_stats_with_trades
            )
            / len(forward_stats_with_trades),
            average_forward_expectancy=sum(
                stats.expectancy for stats in forward_stats_with_trades
            )
            / len(forward_stats_with_trades),
            average_forward_profit_factor=sum(
                stats.profit_factor for stats in forward_stats_with_trades
            )
            / len(forward_stats_with_trades),
        )

    def to_dataframe(self, results: list[WalkForwardResult]) -> pd.DataFrame:
        return pd.DataFrame([result.to_dict() for result in results])

    def export_results(
        self,
        results: list[WalkForwardResult],
        output_path: str,
    ):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe(results).to_csv(output_path, index=False)

    def _run_forward_window(
        self,
        ticker: str | None,
        universe: str | None,
        strategy_name: str,
        training_result: ParameterSweepResult,
        window: WalkForwardWindow,
        tickers: list[str] | None = None,
        result_ticker: str | None = None,
    ) -> ParameterSweepResult:
        selected_candidate = training_result.candidate
        forward_config = replace(
            selected_candidate.backtest_config,
            signal_start_date=window.test_start.date(),
            signal_end_date=window.test_end.date(),
        )
        strategy = StrategyRegistry.get(
            strategy_name,
            config=selected_candidate.strategy_config,
        )
        result = self.service.run(
            ticker=ticker,
            universe=universe,
            strategy=strategy,
            tickers=tickers,
            result_ticker=result_ticker,
            config=forward_config,
        )

        return ParameterSweepResult(
            candidate=ParameterSweepCandidate(
                strategy_name=selected_candidate.strategy_name,
                backtest_config=forward_config,
                strategy_config=selected_candidate.strategy_config,
                strategy_parameters=selected_candidate.strategy_parameters,
            ),
            result=result,
        )
