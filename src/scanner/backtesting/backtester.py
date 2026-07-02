from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.trade import Trade
from scanner.models.market_data import MarketData
from scanner.strategies.base_strategy import BaseStrategy


class Backtester:

    def run(
        self,
        ticker: str,
        history,
        strategy: BaseStrategy,
        relative_strength: float,
        min_history_days: int = 252,
        hold_days: int = 5,
    ) -> BacktestResult:
        trades = []

        for index in range(min_history_days, len(history) - hold_days):
            historical_slice = history.iloc[: index + 1]

            market_data = MarketData(
                ticker=ticker,
                history=historical_slice,
            )

            result = strategy.evaluate(
                market_data=market_data,
                relative_strength=relative_strength,
            )

            if result.triggered:
                entry_index = index + 1
                exit_index = index + hold_days

                entry_price = history.iloc[entry_index]["Close"]
                exit_price = history.iloc[exit_index]["Close"]

                trades.append(
                    Trade(
                        ticker=ticker,
                        strategy_name=strategy.name,
                        entry_index=entry_index,
                        exit_index=exit_index,
                        entry_price=entry_price,
                        exit_price=exit_price,
                    )
                )

        return BacktestResult(
            ticker=ticker,
            strategy_name=strategy.name,
            trades=trades,
        )