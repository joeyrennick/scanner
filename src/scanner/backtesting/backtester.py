from dataclasses import replace

from scanner.backtesting.backtest_config import BacktestConfig
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

        for index in range(
            backtest_config.min_history_days,
            len(history) - backtest_config.hold_days - 1,
        ):
            historical_slice = history.iloc[: index + 1]

            market_data = MarketData(
                ticker=ticker,
                history=historical_slice,
            )
            benchmark_slice = self._benchmark_slice(
                benchmark_history=benchmark_history,
                signal_label=history.index[index],
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

            if result.triggered:
                entry_index = index + 1
                exit_index = entry_index + backtest_config.hold_days

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
                exit_label = history.index[exit_index]

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
