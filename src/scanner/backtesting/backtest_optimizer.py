from dataclasses import dataclass, fields, replace
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

from scanner.backtesting.backtest_config import BacktestConfig
from scanner.strategies.strategy_registry import StrategyRegistry


@dataclass(frozen=True)
class ParameterSweepCandidate:
    strategy_name: str
    backtest_config: BacktestConfig
    strategy_config: Any
    strategy_parameters: dict[str, Any]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "hold_days": self.backtest_config.hold_days,
            "min_history_days": self.backtest_config.min_history_days,
            "allow_overlapping_trades": (
                self.backtest_config.allow_overlapping_trades
            ),
            "entry_reset_policy": self.backtest_config.entry_reset_policy,
            **self.strategy_parameters,
        }


@dataclass(frozen=True)
class ParameterSweepResult:
    candidate: ParameterSweepCandidate
    result: Any

    def to_dict(self) -> dict[str, Any]:
        stats = self.result.statistics
        row = {
            "Strategy": self.result.strategy_name,
            "Hold Days": self.candidate.backtest_config.hold_days,
            "Min History Days": self.candidate.backtest_config.min_history_days,
            "Allow Overlap": self.candidate.backtest_config.allow_overlapping_trades,
            "Entry Reset Policy": self.candidate.backtest_config.entry_reset_policy,
            "Trades": stats.total_trades,
            "Win Rate": stats.win_rate,
            "Average Return": stats.average_return,
            "Expectancy": stats.expectancy,
            "Profit Factor": stats.profit_factor,
            "Best Trade": stats.best_trade_return,
            "Worst Trade": stats.worst_trade_return,
        }

        for name, value in self.candidate.strategy_parameters.items():
            row[f"Strategy Param: {name}"] = value

        return row


class BacktestOptimizer:

    SORT_KEYS = {
        "expectancy": "Expectancy",
        "average_return": "Average Return",
        "win_rate": "Win Rate",
        "profit_factor": "Profit Factor",
        "trades": "Trades",
    }

    def __init__(self, service):
        self.service = service

    def optimize_hold_days(
        self,
        ticker: str | None,
        universe: str | None,
        strategy,
        tickers: list[str] | None = None,
        result_ticker: str | None = None,
        min_hold_days: int = 1,
        max_hold_days: int = 30,
    ):
        results = []

        for hold_days in range(min_hold_days, max_hold_days + 1):
            result = self.service.run(
                ticker=ticker,
                universe=universe,
                strategy=strategy,
                hold_days=hold_days,
                tickers=tickers,
                result_ticker=result_ticker,
            )

            results.append((hold_days, result))

        best = max(
            results,
            key=lambda item: item[1].statistics.expectancy,
        )

        return results, best

    def sweep_parameters(
        self,
        ticker: str | None,
        universe: str | None,
        strategy_name: str,
        base_config: BacktestConfig,
        tickers: list[str] | None = None,
        result_ticker: str | None = None,
        hold_days: list[int] | None = None,
        min_history_days: list[int] | None = None,
        allow_overlapping_trades: list[bool] | None = None,
        entry_reset_policies: list[str] | None = None,
        strategy_parameters: dict[str, list[Any]] | None = None,
        sort_by: str = "expectancy",
        min_trades: int = 1,
    ) -> list[ParameterSweepResult]:
        candidates = self.build_candidates(
            strategy_name=strategy_name,
            base_config=base_config,
            hold_days=hold_days,
            min_history_days=min_history_days,
            allow_overlapping_trades=allow_overlapping_trades,
            entry_reset_policies=entry_reset_policies,
            strategy_parameters=strategy_parameters,
        )

        results = []
        for candidate in candidates:
            strategy = StrategyRegistry.get(
                strategy_name,
                config=candidate.strategy_config,
            )
            result = self.service.run(
                ticker=ticker,
                universe=universe,
                strategy=strategy,
                tickers=tickers,
                result_ticker=result_ticker,
                config=candidate.backtest_config,
            )
            results.append(
                ParameterSweepResult(
                    candidate=candidate,
                    result=result,
                )
            )

        return self.rank_results(
            results,
            sort_by=sort_by,
            min_trades=min_trades,
        )

    def build_candidates(
        self,
        strategy_name: str,
        base_config: BacktestConfig,
        hold_days: list[int] | None = None,
        min_history_days: list[int] | None = None,
        allow_overlapping_trades: list[bool] | None = None,
        entry_reset_policies: list[str] | None = None,
        strategy_parameters: dict[str, list[Any]] | None = None,
    ) -> list[ParameterSweepCandidate]:
        strategy_parameters = strategy_parameters or {}
        default_strategy_config = StrategyRegistry.default_config(strategy_name)
        valid_strategy_fields = {
            field.name for field in fields(default_strategy_config)
        }
        invalid_fields = set(strategy_parameters) - valid_strategy_fields

        if invalid_fields:
            invalid = ", ".join(sorted(invalid_fields))
            valid = ", ".join(sorted(valid_strategy_fields))
            raise ValueError(
                f"Unknown strategy sweep parameter(s): {invalid}. "
                f"Supported parameters for {strategy_name}: {valid}"
            )

        hold_day_values = hold_days or [base_config.hold_days]
        min_history_values = min_history_days or [base_config.min_history_days]
        overlap_values = (
            allow_overlapping_trades
            if allow_overlapping_trades is not None
            else [base_config.allow_overlapping_trades]
        )
        reset_policy_values = entry_reset_policies or [
            base_config.entry_reset_policy
        ]
        strategy_param_names = list(strategy_parameters.keys())
        strategy_param_values = [
            strategy_parameters[name] for name in strategy_param_names
        ]

        if not strategy_param_names:
            strategy_param_combinations = [()]
        else:
            strategy_param_combinations = product(*strategy_param_values)

        candidates = []
        for (
            hold_days_value,
            min_history_value,
            overlap_value,
            reset_policy_value,
            strategy_values,
        ) in product(
            hold_day_values,
            min_history_values,
            overlap_values,
            reset_policy_values,
            strategy_param_combinations,
        ):
            strategy_params = dict(zip(strategy_param_names, strategy_values))
            backtest_config = replace(
                base_config,
                hold_days=hold_days_value,
                min_history_days=min_history_value,
                allow_overlapping_trades=overlap_value,
                entry_reset_policy=reset_policy_value,
            )
            strategy_config = replace(
                default_strategy_config,
                **strategy_params,
            )
            candidates.append(
                ParameterSweepCandidate(
                    strategy_name=strategy_name,
                    backtest_config=backtest_config,
                    strategy_config=strategy_config,
                    strategy_parameters=strategy_params,
                )
            )

        return candidates

    def rank_results(
        self,
        results: list[ParameterSweepResult],
        sort_by: str = "expectancy",
        min_trades: int = 1,
    ) -> list[ParameterSweepResult]:
        if sort_by not in self.SORT_KEYS:
            supported = ", ".join(sorted(self.SORT_KEYS.keys()))
            raise ValueError(f"Unsupported sort metric '{sort_by}': {supported}")

        ranked = [
            result
            for result in results
            if result.result.statistics.total_trades >= min_trades
        ]
        return sorted(
            ranked,
            key=lambda sweep_result: self._sort_value(sweep_result, sort_by),
            reverse=True,
        )

    def to_dataframe(
        self,
        results: list[ParameterSweepResult],
    ) -> pd.DataFrame:
        return pd.DataFrame([result.to_dict() for result in results])

    def export_results(
        self,
        results: list[ParameterSweepResult],
        output_path: str,
    ):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe(results).to_csv(output_path, index=False)

    def _sort_value(
        self,
        result: ParameterSweepResult,
        sort_by: str,
    ) -> float:
        row = result.to_dict()
        return row[self.SORT_KEYS[sort_by]]
