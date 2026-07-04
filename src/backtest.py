import argparse
import os

import pandas as pd

from scanner.backtesting.backtest_optimizer import BacktestOptimizer
from scanner.backtesting.backtest_reporter import BacktestReporter
from scanner.backtesting.backtest_service import BacktestService
from scanner.backtesting.watchlist_loader import load_watchlist_tickers
from scanner.data.market_data import check_market_data_connectivity
from scanner.config.settings import settings
from scanner.strategies.strategy_registry import StrategyRegistry
from scanner.universe.universe_provider import UniverseProvider


def export_trades(result, output_file: str):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    df = pd.DataFrame([trade.to_dict() for trade in result.trades])
    df.to_csv(output_file, index=False)

    print(f"Exported {len(result.trades)} trades to {output_file}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--ticker")
    parser.add_argument(
        "--universe",
        choices=UniverseProvider.SUPPORTED_UNIVERSES,
        help="Backtest an entire stock universe.",
    )
    parser.add_argument(
        "--watchlist",
        help="Backtest tickers from a watchlist CSV.",
    )
    parser.add_argument(
        "--watchlist-all",
        action="store_true",
        help="Backtest every ticker in --watchlist instead of filtering by strategy.",
    )

    parser.add_argument("--strategy", default="pullback")
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--compare-hold-days", nargs="+", type=int)
    parser.add_argument("--optimize-hold-days", action="store_true")
    parser.add_argument(
        "--export-trades",
        help="Path to export individual backtest trades as CSV.",
    )
    parser.add_argument(
        "--preflight-market-data",
        action="store_true",
        help="Check Yahoo/yfinance connectivity before running the backtest.",
    )

    args = parser.parse_args()

    selected_sources = [
        source for source in [args.ticker, args.universe, args.watchlist] if source
    ]

    if len(selected_sources) != 1:
        parser.error("Exactly one of --ticker, --universe, or --watchlist is required")

    if args.watchlist_all and not args.watchlist:
        parser.error("--watchlist-all requires --watchlist")

    if args.preflight_market_data:
        try:
            result = check_market_data_connectivity(
                ticker=settings.benchmark_ticker,
                period="5d",
            )
        except Exception as error:
            parser.error(f"Market data preflight failed: {error}")

        print(
            "Market data preflight passed for "
            f"{result.ticker} ({result.rows} rows in {result.elapsed_seconds:.2f}s)"
        )

    strategy = StrategyRegistry.get(args.strategy)
    watchlist_tickers = None
    result_ticker = None

    if args.watchlist:
        try:
            watchlist_tickers = load_watchlist_tickers(
                watchlist_path=args.watchlist,
                strategy_name=strategy.name,
                include_all=args.watchlist_all,
            )
        except ValueError as error:
            parser.error(str(error))

        result_ticker = "Watchlist"

    service = BacktestService()
    reporter = BacktestReporter()

    if args.optimize_hold_days:
        optimizer = BacktestOptimizer(service)

        results_by_hold_days, best = optimizer.optimize_hold_days(
            ticker=args.ticker,
            universe=args.universe,
            strategy=strategy,
            tickers=watchlist_tickers,
            result_ticker=result_ticker,
            min_hold_days=1,
            max_hold_days=30,
        )

        reporter.print_hold_day_comparison(results_by_hold_days)
        reporter.print_best_hold_period(best)

    elif args.compare_hold_days:
        results_by_hold_days = []

        for hold_days in args.compare_hold_days:
            result = service.run(
                ticker=args.ticker,
                universe=args.universe,
                strategy=strategy,
                hold_days=hold_days,
                tickers=watchlist_tickers,
                result_ticker=result_ticker,
            )

            results_by_hold_days.append((hold_days, result))

        reporter.print_hold_day_comparison(results_by_hold_days)

    else:
        result = service.run(
            ticker=args.ticker,
            universe=args.universe,
            strategy=strategy,
            hold_days=args.hold_days,
            tickers=watchlist_tickers,
            result_ticker=result_ticker,
        )

        reporter.print_result(result, args.hold_days)

        if args.export_trades:
            export_trades(result, args.export_trades)



if __name__ == "__main__":
    main()
