import argparse

from concurrent.futures import ThreadPoolExecutor, as_completed
from scanner.universe.universe_provider import UniverseProvider
from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.backtest_optimizer import BacktestOptimizer
from scanner.backtesting.backtest_reporter import BacktestReporter
from scanner.backtesting.backtester import Backtester
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.services.market_data_service import MarketDataService
from scanner.strategies.strategy_registry import StrategyRegistry

def run_single_ticker_backtest(
    ticker,
    strategy,
    hold_days: int,
    market_data_service: MarketDataService,
    benchmark,
):
    history = market_data_service.get_history(
        ticker,
        period="5y",
    )

    relative_strength = calculate_relative_strength(
        history,
        benchmark,
    )

    result = Backtester().run(
        ticker=ticker,
        history=history,
        strategy=strategy,
        relative_strength=relative_strength,
        hold_days=hold_days,
    )

    return ticker, result

def run_sp500_backtest(
    strategy,
    hold_days: int,
    market_data_service: MarketDataService,
    max_workers: int = 20,
):
    all_trades = []
    skipped = []

    tickers = UniverseProvider().get_sp500_tickers()
    benchmark = market_data_service.get_history("SPY", period="5y")

    print(f"Backtesting {len(tickers)} stocks with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_single_ticker_backtest,
                ticker,
                strategy,
                hold_days,
                market_data_service,
                benchmark,
            ): ticker
            for ticker in tickers
        }

        completed = 0

        for future in as_completed(futures):
            completed += 1
            ticker = futures[future]

            try:
                _, result = future.result()
                all_trades.extend(result.trades)
                print(f"[{completed}/{len(tickers)}] Finished {ticker}")

            except Exception as e:
                skipped.append((ticker, str(e)))
                print(f"[{completed}/{len(tickers)}] Skipped {ticker}: {e}")

    print(f"Skipped: {len(skipped)}")

    return BacktestResult(
        ticker="S&P 500",
        strategy_name=strategy.name,
        trades=all_trades,
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker")
    parser.add_argument("--strategy", default="pullback")
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--compare-hold-days", nargs="+", type=int)
    parser.add_argument("--optimize-hold-days", action="store_true")
    parser.add_argument(
        "--universe",
        choices=["sp500"],
        help="Backtest an entire stock universe instead of a single ticker.",
    )

    args = parser.parse_args()

    if not args.universe and not args.ticker:
        parser.error("--ticker is required unless --universe is provided")
    
    if args.universe == "sp500":
        strategy = StrategyRegistry.get(args.strategy)
        reporter = BacktestReporter()

        market_data_service = MarketDataService()

        result = run_sp500_backtest(
            strategy=strategy,
            hold_days=args.hold_days,
            market_data_service=market_data_service,
        )

        reporter.print_result(result, args.hold_days)
        return
    
    market_data_service = MarketDataService()

    history = market_data_service.get_history(args.ticker, period="5y")
    benchmark = market_data_service.get_history("SPY", period="5y")

    relative_strength = calculate_relative_strength(history, benchmark)
    strategy = StrategyRegistry.get(args.strategy)
    reporter = BacktestReporter()

    if args.optimize_hold_days:
        results_by_hold_days, best = BacktestOptimizer().optimize_hold_days(
            ticker=args.ticker.upper(),
            history=history,
            strategy=strategy,
            relative_strength=relative_strength,
            min_hold_days=1,
            max_hold_days=30,
        )

        reporter.print_hold_day_comparison(results_by_hold_days)
        reporter.print_best_hold_period(best)

    elif args.compare_hold_days:
        results_by_hold_days = []

        for hold_days in args.compare_hold_days:
            result = Backtester().run(
                ticker=args.ticker.upper(),
                history=history,
                strategy=strategy,
                relative_strength=relative_strength,
                hold_days=hold_days,
            )

            results_by_hold_days.append((hold_days, result))

        reporter.print_hold_day_comparison(results_by_hold_days)

    else:
        result = Backtester().run(
            ticker=args.ticker.upper(),
            history=history,
            strategy=strategy,
            relative_strength=relative_strength,
            hold_days=args.hold_days,
        )

        reporter.print_result(result, args.hold_days)


if __name__ == "__main__":
    main()