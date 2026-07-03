class BacktestOptimizer:

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
