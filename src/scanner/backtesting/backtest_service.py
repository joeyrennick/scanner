from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.backtester import Backtester
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.services.market_data_service import MarketDataService
from scanner.universe.universe_provider import UniverseProvider


class BacktestService:

    def __init__(self):
        self.market_data_service = MarketDataService()

    def run_single_ticker(
        self,
        ticker: str,
        strategy,
        hold_days: int,
    ) -> BacktestResult:
        history = self.market_data_service.get_history(ticker, period="5y")
        benchmark = self.market_data_service.get_history("SPY", period="5y")

        relative_strength = calculate_relative_strength(history, benchmark)

        return Backtester().run(
            ticker=ticker.upper(),
            history=history,
            strategy=strategy,
            relative_strength=relative_strength,
            hold_days=hold_days,
        )

    def run_universe(
        self,
        universe: str,
        strategy,
        hold_days: int,
    ) -> BacktestResult:
        if universe != "sp500":
            raise ValueError(f"Unsupported universe: {universe}")

        tickers = UniverseProvider().get_sp500_tickers()
        benchmark = self.market_data_service.get_history("SPY", period="5y")

        all_trades = []
        skipped = []

        print(f"Backtesting {len(tickers)} stocks...")

        for index, ticker in enumerate(tickers, start=1):
            print(f"[{index}/{len(tickers)}] {ticker}")

            try:
                history = self.market_data_service.get_history(ticker, period="5y")
                relative_strength = calculate_relative_strength(history, benchmark)

                result = Backtester().run(
                    ticker=ticker,
                    history=history,
                    strategy=strategy,
                    relative_strength=relative_strength,
                    hold_days=hold_days,
                )

                all_trades.extend(result.trades)

            except Exception as e:
                skipped.append((ticker, str(e)))

        print(f"Skipped: {len(skipped)}")

        return BacktestResult(
            ticker="S&P 500",
            strategy_name=strategy.name,
            trades=all_trades,
        )

    def run(
        self,
        ticker: str | None,
        universe: str | None,
        strategy,
        hold_days: int,
    ) -> BacktestResult:
        if universe:
            return self.run_universe(
                universe=universe,
                strategy=strategy,
                hold_days=hold_days,
            )

        return self.run_single_ticker(
            ticker=ticker,
            strategy=strategy,
            hold_days=hold_days,
        )