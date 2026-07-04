from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.backtester import Backtester
from scanner.config.settings import settings
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.services.market_data_service import MarketDataService
from scanner.universe.universe_provider import UniverseProvider
from concurrent.futures import ThreadPoolExecutor, as_completed


class BacktestService:

    def __init__(self, history_period: str = settings.backtest_history_period):
        self.market_data_service = MarketDataService()
        self.history_period = history_period

    def run_single_ticker(
        self,
        ticker: str,
        strategy,
        hold_days: int,
    ) -> BacktestResult:
        history = self.market_data_service.get_history(
            ticker,
            period=self.history_period,
        )
        benchmark = self.market_data_service.get_history(
            "SPY",
            period=self.history_period,
        )

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
        tickers = UniverseProvider().get_universe_tickers(universe)
        return self.run_tickers(
            tickers=tickers,
            result_ticker=universe.upper(),
            strategy=strategy,
            hold_days=hold_days,
        )

    def run_tickers(
        self,
        tickers: list[str],
        result_ticker: str,
        strategy,
        hold_days: int,
    ) -> BacktestResult:
        benchmark = self.market_data_service.get_history(
            "SPY",
            period=self.history_period,
        )

        all_trades = []
        skipped = []
        max_workers = settings.max_workers

        def run_one(ticker: str):
            history = self.market_data_service.get_history(
                ticker,
                period=self.history_period,
            )
            relative_strength = calculate_relative_strength(history, benchmark)

            return Backtester().run(
                ticker=ticker,
                history=history,
                strategy=strategy,
                relative_strength=relative_strength,
                hold_days=hold_days,
            )
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_one, ticker): ticker
                for ticker in tickers
            }

            completed = 0

            for future in as_completed(futures):
                completed += 1
                ticker = futures[future]

                try:
                    result = future.result()
                    all_trades.extend(result.trades)
                    print(f"[{completed}/{len(tickers)}] Finished {ticker}")

                except Exception as e:
                    skipped.append((ticker, str(e)))
                    print(f"[{completed}/{len(tickers)}] Skipped {ticker}: {e}")

        print(f"Skipped: {len(skipped)}")

        return BacktestResult(
            ticker=result_ticker,
            strategy_name=strategy.name,
            trades=all_trades,
        )

    def run(
        self,
        ticker: str | None,
        universe: str | None,
        strategy,
        hold_days: int,
        tickers: list[str] | None = None,
        result_ticker: str | None = None,
    ) -> BacktestResult:
        if tickers:
            return self.run_tickers(
                tickers=tickers,
                result_ticker=result_ticker or "Custom Ticker List",
                strategy=strategy,
                hold_days=hold_days,
            )

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
