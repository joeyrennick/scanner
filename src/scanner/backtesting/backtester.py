from dataclasses import replace

import pandas as pd

from scanner.backtesting.backtest_config import (
    ENTRY_RESET_POLICY_SIGNAL_OFF,
    BacktestConfig,
)
from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.trade import Trade
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.models.market_data import MarketData
from scanner.strategies.base_strategy import BaseStrategy


class Backtester:

    def run(
        self,
        ticker: str,
        history,
        strategy: BaseStrategy,
        benchmark_history,
        config: BacktestConfig | None = None,
        min_history_days: int | None = None,
        hold_days: int | None = None,
    ) -> BacktestResult:
        backtest_config = config or BacktestConfig()

        if hold_days is not None:
            backtest_config = replace(backtest_config, hold_days=hold_days)

        if min_history_days is not None:
            backtest_config = replace(
                backtest_config,
                min_history_days=min_history_days,
            )

        trades = []
        last_exit_index = -1
        waiting_for_signal_reset = False

        for index in range(
            backtest_config.min_history_days,
            len(history) - backtest_config.hold_days - 1,
        ):
            signal_label = history.index[index]

            if not self._is_signal_in_window(signal_label, backtest_config):
                continue

            historical_slice = history.iloc[: index + 1]

            market_data = MarketData(
                ticker=ticker,
                history=historical_slice,
            )
            benchmark_slice = self._benchmark_slice(
                benchmark_history=benchmark_history,
                signal_label=signal_label,
                signal_index=index,
            )
            relative_strength = calculate_relative_strength(
                historical_slice,
                benchmark_slice,
            )

            result = strategy.evaluate(
                market_data=market_data,
                relative_strength=relative_strength,
            )

            if waiting_for_signal_reset:
                if not result.triggered:
                    waiting_for_signal_reset = False
                continue

            if result.triggered:
                entry_index = index + 1
                exit_index = entry_index + backtest_config.hold_days
                exit_label = history.index[exit_index]

                if not self._is_exit_in_window(exit_label, backtest_config):
                    continue

                if (
                    not backtest_config.allow_overlapping_trades
                    and entry_index <= last_exit_index
                ):
                    continue

                entry_price = history.iloc[entry_index]["Close"]
                exit_price = history.iloc[exit_index]["Close"]

                if hasattr(entry_price, "item"):
                    entry_price = entry_price.item()

                if hasattr(exit_price, "item"):
                    exit_price = exit_price.item()

                entry_label = history.index[entry_index]

                entry_date = (
                    entry_label.date()
                    if hasattr(entry_label, "date")
                    else entry_label
                )

                exit_date = (
                    exit_label.date()
                    if hasattr(exit_label, "date")
                    else exit_label
                )
                
                trades.append(
                    Trade(
                        ticker=ticker,
                        strategy_name=strategy.name,
                        entry_date=entry_date,
                        exit_date=exit_date,
                        entry_price=entry_price,
                        exit_price=exit_price,
                    )
                )
                last_exit_index = exit_index

                if (
                    backtest_config.entry_reset_policy
                    == ENTRY_RESET_POLICY_SIGNAL_OFF
                ):
                    waiting_for_signal_reset = True

        return BacktestResult(
            ticker=ticker,
            strategy_name=strategy.name,
            trades=trades,
        )

    def _benchmark_slice(self, benchmark_history, signal_label, signal_index: int):
        try:
            benchmark_slice = benchmark_history.loc[:signal_label]

            if not benchmark_slice.empty:
                return benchmark_slice

        except (AttributeError, KeyError, TypeError):
            pass

        return benchmark_history.iloc[: signal_index + 1]

    def _is_signal_in_window(self, signal_label, config: BacktestConfig) -> bool:
        return self._is_label_in_window(
            label=signal_label,
            start=config.signal_start_date,
            end=config.signal_end_date,
        )

    def _is_exit_in_window(self, exit_label, config: BacktestConfig) -> bool:
        if config.signal_end_date is None:
            return True

        return self._label_to_timestamp(exit_label) <= self._label_to_timestamp(
            config.signal_end_date
        )

    def _is_label_in_window(self, label, start, end) -> bool:
        timestamp = self._label_to_timestamp(label)

        if start is not None and timestamp < self._label_to_timestamp(start):
            return False

        if end is not None and timestamp > self._label_to_timestamp(end):
            return False

        return True

    @staticmethod
    def _label_to_timestamp(label):
        return pd.Timestamp(label).normalize()
