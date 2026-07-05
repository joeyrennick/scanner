from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, as_completed

from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.backtester import Backtester
from scanner.config.settings import settings
from scanner.services.market_data_service import MarketDataService
from scanner.universe.universe_provider import UniverseProvider


class BacktestService:

    def __init__(
        self,
        history_period: str | None = None,
        config: BacktestConfig | None = None,
    ):
        self.market_data_service = MarketDataService()
        self.config = config or BacktestConfig(
            history_period=history_period or settings.backtest_history_period,
        )

    def run_single_ticker(
        self,
        ticker: str,
        strategy,
        hold_days: int | None = None,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        backtest_config = self._resolve_config(config=config, hold_days=hold_days)
        history = self.market_data_service.get_history(
            ticker,
            period=backtest_config.history_period,
        )
        benchmark = self.market_data_service.get_history(
            "SPY",
            period=backtest_config.history_period,
        )

        return Backtester().run(
            ticker=ticker.upper(),
            history=history,
            strategy=strategy,
            benchmark_history=benchmark,
            config=backtest_config,
        )

    def run_universe(
        self,
        universe: str,
        strategy,
        hold_days: int | None = None,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        backtest_config = self._resolve_config(config=config, hold_days=hold_days)
        tickers = UniverseProvider().get_universe_tickers(universe)
        return self.run_tickers(
            tickers=tickers,
            result_ticker=universe.upper(),
            strategy=strategy,
            config=backtest_config,
        )

    def run_tickers(
        self,
        tickers: list[str],
        result_ticker: str,
        strategy,
        hold_days: int | None = None,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        backtest_config = self._resolve_config(config=config, hold_days=hold_days)
        benchmark = self.market_data_service.get_history(
            "SPY",
            period=backtest_config.history_period,
        )

        all_trades = []
        skipped = []
        max_workers = settings.max_workers

        def run_one(ticker: str):
            history = self.market_data_service.get_history(
                ticker,
                period=backtest_config.history_period,
            )
            return Backtester().run(
                ticker=ticker,
                history=history,
                strategy=strategy,
                benchmark_history=benchmark,
                config=backtest_config,
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
        hold_days: int | None = None,
        tickers: list[str] | None = None,
        result_ticker: str | None = None,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        backtest_config = self._resolve_config(config=config, hold_days=hold_days)

        if tickers:
            return self.run_tickers(
                tickers=tickers,
                result_ticker=result_ticker or "Custom Ticker List",
                strategy=strategy,
                config=backtest_config,
            )

        if universe:
            return self.run_universe(
                universe=universe,
                strategy=strategy,
                config=backtest_config,
            )

        return self.run_single_ticker(
            ticker=ticker,
            strategy=strategy,
            config=backtest_config,
        )

    def _resolve_config(
        self,
        config: BacktestConfig | None = None,
        hold_days: int | None = None,
    ) -> BacktestConfig:
        backtest_config = config or self.config

        if hold_days is not None:
            return replace(backtest_config, hold_days=hold_days)

        return backtest_config
