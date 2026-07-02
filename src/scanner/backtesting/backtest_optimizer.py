from scanner.backtesting.backtester import Backtester


class BacktestOptimizer:

    def optimize_hold_days(
        self,
        ticker: str,
        history,
        strategy,
        relative_strength: float,
        min_hold_days: int = 1,
        max_hold_days: int = 30,
    ):
        results = []

        for hold_days in range(min_hold_days, max_hold_days + 1):

            result = Backtester().run(
                ticker=ticker,
                history=history,
                strategy=strategy,
                relative_strength=relative_strength,
                hold_days=hold_days,
            )

            results.append((hold_days, result))

        best = max(
            results,
            key=lambda item: item[1].statistics.expectancy,
        )

        return results, best