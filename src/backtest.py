import argparse
import os

import pandas as pd

from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtest_optimizer import BacktestOptimizer
from scanner.backtesting.backtest_reporter import BacktestReporter
from scanner.backtesting.backtest_service import BacktestService
from scanner.backtesting.walk_forward import WalkForwardTester
from scanner.backtesting.watchlist_loader import load_watchlist_tickers
from scanner.data.market_data import (
    check_market_data_connectivity,
    configure_market_data_cache,
    configure_market_data_provider,
    get_market_data_cache_overview,
    get_market_data_cache_stats,
)
from scanner.config.settings import settings
from scanner.services.price_filter import filter_tickers_by_price
from scanner.strategies.strategy_registry import StrategyRegistry
from scanner.universe.universe_provider import UniverseProvider
from scanner.utils.cache_summary import format_cache_summary


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
    parser.add_argument(
        "--min-history-days",
        type=int,
        default=252,
        help="Minimum number of historical bars required before evaluating signals.",
    )
    parser.add_argument(
        "--no-overlapping-trades",
        action="store_true",
        help="Skip new signals while a prior backtest trade is still open.",
    )
    parser.add_argument(
        "--entry-reset-policy",
        choices=["none", "signal-off"],
        default="none",
        help=(
            "Require a setup reset before another entry. "
            "'signal-off' waits until the strategy signal turns off."
        ),
    )
    parser.add_argument("--compare-hold-days", nargs="+", type=int)
    parser.add_argument("--optimize-hold-days", action="store_true")
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Run a parameter sweep over backtest and strategy settings.",
    )
    parser.add_argument(
        "--sweep-hold-days",
        nargs="+",
        type=int,
        help="Hold-day values to include in --sweep.",
    )
    parser.add_argument(
        "--sweep-min-history-days",
        nargs="+",
        type=int,
        help="Minimum-history values to include in --sweep.",
    )
    parser.add_argument(
        "--sweep-overlap",
        nargs="+",
        choices=["allowed", "blocked"],
        help="Overlap modes to include in --sweep.",
    )
    parser.add_argument(
        "--sweep-entry-reset-policy",
        nargs="+",
        choices=["none", "signal-off"],
        help="Entry reset policies to include in --sweep.",
    )
    parser.add_argument(
        "--sweep-strategy-param",
        action="append",
        default=[],
        metavar="NAME=VALUE[,VALUE...]",
        help=(
            "Strategy config field and values to include in --sweep. "
            "Example: min_relative_volume=1.0,1.25,1.5"
        ),
    )
    parser.add_argument(
        "--sweep-sort-by",
        default="expectancy",
        choices=sorted(BacktestOptimizer.SORT_KEYS.keys()),
        help="Metric used to rank parameter sweep results.",
    )
    parser.add_argument(
        "--sweep-min-trades",
        type=int,
        default=1,
        help="Minimum trades required for a sweep row to be ranked.",
    )
    parser.add_argument(
        "--sweep-top",
        type=int,
        default=10,
        help="Number of ranked sweep rows to print.",
    )
    parser.add_argument(
        "--export-sweep-results",
        help="Path to export parameter sweep results as CSV.",
    )
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help=(
            "Run walk-forward testing by optimizing on each training window "
            "and testing on the following forward window."
        ),
    )
    parser.add_argument(
        "--walk-forward-start-date",
        help="Walk-forward start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--walk-forward-end-date",
        help="Walk-forward end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--walk-forward-train-months",
        type=int,
        default=6,
        help="Number of months in each walk-forward training window.",
    )
    parser.add_argument(
        "--walk-forward-test-months",
        type=int,
        default=3,
        help="Number of months in each walk-forward forward-test window.",
    )
    parser.add_argument(
        "--walk-forward-step-months",
        type=int,
        help=(
            "Months to advance between walk-forward windows. "
            "Defaults to --walk-forward-test-months."
        ),
    )
    parser.add_argument(
        "--export-walk-forward-results",
        help="Path to export walk-forward results as CSV.",
    )
    parser.add_argument(
        "--export-trades",
        help="Path to export individual backtest trades as CSV.",
    )
    parser.add_argument(
        "--preflight-market-data",
        action="store_true",
        help="Check Yahoo/yfinance connectivity before running the backtest.",
    )
    parser.add_argument(
        "--market-data-provider",
        default=settings.market_data_provider,
        help="Market data provider to use for downloads.",
    )
    parser.add_argument(
        "--no-market-data-cache",
        action="store_true",
        help="Disable the local market data cache for this run.",
    )
    parser.add_argument(
        "--refresh-market-data-cache",
        action="store_true",
        help="Force provider refreshes and update the local market data cache.",
    )
    parser.add_argument(
        "--history-period",
        default=settings.backtest_history_period,
        help="Price history period to download for backtesting.",
    )
    parser.add_argument(
        "--min-price",
        type=float,
        help="Skip tickers with latest close below this price.",
    )
    parser.add_argument(
        "--max-price",
        type=float,
        help="Skip tickers with latest close above this price.",
    )
    parser.add_argument(
        "--price-sample-period",
        default=settings.price_filter_sample_period,
        help="Small history period to fetch when price is not already cached.",
    )
    parser.add_argument(
        "--price-filter-workers",
        type=int,
        help="Deprecated alias for --price-filter-batch-size.",
    )
    parser.add_argument(
        "--price-filter-batch-size",
        type=int,
        default=settings.price_filter_batch_size,
        help="Number of uncached symbols to request in each price-filter batch.",
    )
    parser.add_argument(
        "--price-filter-max-provider-calls",
        type=int,
        default=settings.price_filter_max_provider_calls,
        help="Maximum uncached price-filter provider calls to make in one run.",
    )
    parser.add_argument(
        "--price-filter-max-provider-batches",
        type=int,
        default=settings.price_filter_max_provider_batches,
        help="Maximum price-filter provider batches to make in one run.",
    )
    parser.add_argument(
        "--price-filter-batch-delay-ms",
        type=int,
        default=int(settings.price_filter_batch_delay_seconds * 1000),
        help="Delay between price-filter provider batches in milliseconds.",
    )

    args = parser.parse_args()

    if (
        args.min_price is not None
        and args.max_price is not None
        and args.min_price > args.max_price
    ):
        parser.error("--min-price cannot be greater than --max-price")

    price_filter_batch_size = (
        args.price_filter_workers
        if args.price_filter_workers is not None
        else args.price_filter_batch_size
    )

    if price_filter_batch_size <= 0:
        parser.error("--price-filter-batch-size must be greater than zero")

    if (
        args.price_filter_max_provider_calls is not None
        and args.price_filter_max_provider_calls < 0
    ):
        parser.error("--price-filter-max-provider-calls cannot be negative")

    if (
        args.price_filter_max_provider_batches is not None
        and args.price_filter_max_provider_batches < 0
    ):
        parser.error("--price-filter-max-provider-batches cannot be negative")

    if args.price_filter_batch_delay_ms < 0:
        parser.error("--price-filter-batch-delay-ms cannot be negative")

    if args.sweep_min_trades < 0:
        parser.error("--sweep-min-trades cannot be negative")

    if args.sweep_top <= 0:
        parser.error("--sweep-top must be greater than zero")

    if args.sweep and args.walk_forward:
        parser.error("--sweep and --walk-forward cannot be used together")

    if args.walk_forward:
        if not args.walk_forward_start_date or not args.walk_forward_end_date:
            parser.error(
                "--walk-forward requires --walk-forward-start-date and "
                "--walk-forward-end-date"
            )

        if args.walk_forward_train_months <= 0:
            parser.error("--walk-forward-train-months must be greater than zero")

        if args.walk_forward_test_months <= 0:
            parser.error("--walk-forward-test-months must be greater than zero")

        if (
            args.walk_forward_step_months is not None
            and args.walk_forward_step_months <= 0
        ):
            parser.error("--walk-forward-step-months must be greater than zero")

    try:
        backtest_config = BacktestConfig(
            history_period=args.history_period,
            hold_days=args.hold_days,
            min_history_days=args.min_history_days,
            allow_overlapping_trades=not args.no_overlapping_trades,
            entry_reset_policy=_parse_entry_reset_policy(args.entry_reset_policy),
        )
    except ValueError as error:
        parser.error(str(error))

    selected_sources = [
        source for source in [args.ticker, args.universe, args.watchlist] if source
    ]

    if len(selected_sources) != 1:
        parser.error("Exactly one of --ticker, --universe, or --watchlist is required")

    if args.watchlist_all and not args.watchlist:
        parser.error("--watchlist-all requires --watchlist")

    try:
        configure_market_data_provider(args.market_data_provider)
    except ValueError as error:
        parser.error(str(error))

    configure_market_data_cache(
        enabled=not args.no_market_data_cache,
        force_refresh=args.refresh_market_data_cache,
    )

    if args.preflight_market_data:
        try:
            result = check_market_data_connectivity(
                ticker=settings.benchmark_ticker,
                period="5d",
                provider=args.market_data_provider,
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
    selected_tickers = None

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
        selected_tickers = watchlist_tickers

    if args.universe:
        selected_tickers = UniverseProvider().get_universe_tickers(args.universe)
        result_ticker = args.universe.upper()

    if args.ticker:
        selected_tickers = [args.ticker.upper()]
        result_ticker = args.ticker.upper()

    if args.min_price is not None or args.max_price is not None:
        price_filter_result = filter_tickers_by_price(
            tickers=selected_tickers or [],
            min_price=args.min_price,
            max_price=args.max_price,
            provider_name=args.market_data_provider,
            cache_path=settings.market_data_cache_path,
            sample_period=args.price_sample_period,
            max_cached_price_age_days=settings.price_filter_max_cache_age_days,
            max_provider_calls=args.price_filter_max_provider_calls,
            batch_size=price_filter_batch_size,
            batch_delay_seconds=args.price_filter_batch_delay_ms / 1000,
            max_provider_batches=args.price_filter_max_provider_batches,
        )
        selected_tickers = price_filter_result.tickers
        print(
            "Price filter kept "
            f"{price_filter_result.passed_count}/{price_filter_result.checked_count} "
            f"tickers; skipped={price_filter_result.skipped_count}; "
            f"provider_calls_attempted={price_filter_result.provider_calls_attempted}; "
            f"provider_call_limit={price_filter_result.provider_calls_allowed}; "
            f"provider_batches_attempted={price_filter_result.provider_batches_attempted}; "
            f"provider_batch_limit={price_filter_result.provider_batches_allowed}"
        )

        if not selected_tickers:
            print("No tickers matched the price filter.")
            _print_cache_stats()
            return

        if args.watchlist or args.universe:
            watchlist_tickers = selected_tickers
            result_ticker = result_ticker or "Filtered Tickers"
        else:
            args.ticker = selected_tickers[0]

    if args.universe and selected_tickers is not None:
        watchlist_tickers = selected_tickers
        result_ticker = result_ticker or args.universe.upper()
        args.universe = None

    service = BacktestService(config=backtest_config)
    reporter = BacktestReporter()

    if args.walk_forward:
        tester = WalkForwardTester(service)

        try:
            walk_forward_results = tester.run(
                ticker=args.ticker,
                universe=args.universe,
                strategy_name=args.strategy,
                base_config=backtest_config,
                start_date=args.walk_forward_start_date,
                end_date=args.walk_forward_end_date,
                train_months=args.walk_forward_train_months,
                test_months=args.walk_forward_test_months,
                step_months=args.walk_forward_step_months,
                tickers=watchlist_tickers,
                result_ticker=result_ticker,
                hold_days=args.sweep_hold_days,
                min_history_days=args.sweep_min_history_days,
                allow_overlapping_trades=_parse_sweep_overlap(args.sweep_overlap),
                entry_reset_policies=_parse_sweep_entry_reset_policies(
                    args.sweep_entry_reset_policy
                ),
                strategy_parameters=_parse_sweep_strategy_params(
                    args.sweep_strategy_param
                ),
                sort_by=args.sweep_sort_by,
                min_trades=args.sweep_min_trades,
            )
        except ValueError as error:
            parser.error(str(error))

        reporter.print_walk_forward(
            tester.summary(walk_forward_results),
            walk_forward_results,
        )

        if args.export_walk_forward_results:
            tester.export_results(
                walk_forward_results,
                args.export_walk_forward_results,
            )
            print(
                "Exported walk-forward results to "
                f"{args.export_walk_forward_results}"
            )

    elif args.sweep:
        optimizer = BacktestOptimizer(service)

        try:
            sweep_results = optimizer.sweep_parameters(
                ticker=args.ticker,
                universe=args.universe,
                strategy_name=args.strategy,
                base_config=backtest_config,
                tickers=watchlist_tickers,
                result_ticker=result_ticker,
                hold_days=args.sweep_hold_days,
                min_history_days=args.sweep_min_history_days,
                allow_overlapping_trades=_parse_sweep_overlap(args.sweep_overlap),
                entry_reset_policies=_parse_sweep_entry_reset_policies(
                    args.sweep_entry_reset_policy
                ),
                strategy_parameters=_parse_sweep_strategy_params(
                    args.sweep_strategy_param
                ),
                sort_by=args.sweep_sort_by,
                min_trades=args.sweep_min_trades,
            )
        except ValueError as error:
            parser.error(str(error))

        reporter.print_parameter_sweep(sweep_results, top=args.sweep_top)

        if args.export_sweep_results:
            optimizer.export_results(sweep_results, args.export_sweep_results)
            print(f"Exported parameter sweep results to {args.export_sweep_results}")

    elif args.optimize_hold_days:
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
            tickers=watchlist_tickers,
            result_ticker=result_ticker,
            config=backtest_config,
        )

        reporter.print_result(result, backtest_config.hold_days)

        if args.export_trades:
            export_trades(result, args.export_trades)

    _print_cache_stats()


def _print_cache_stats():
    cache_summary = format_cache_summary(
        get_market_data_cache_stats(),
        get_market_data_cache_overview(),
    )

    if cache_summary:
        print(cache_summary)


def _parse_sweep_overlap(values: list[str] | None) -> list[bool] | None:
    if values is None:
        return None

    return [value == "allowed" for value in values]


def _parse_entry_reset_policy(value: str) -> str:
    return value.replace("-", "_")


def _parse_sweep_entry_reset_policies(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None

    return [_parse_entry_reset_policy(value) for value in values]


def _parse_sweep_strategy_params(values: list[str]) -> dict[str, list]:
    parsed = {}

    for value in values:
        if "=" not in value:
            raise ValueError(
                "--sweep-strategy-param values must use NAME=VALUE[,VALUE...]"
            )

        name, raw_values = value.split("=", 1)
        name = name.strip()

        if not name:
            raise ValueError("--sweep-strategy-param name cannot be empty")

        parsed_values = [
            _parse_sweep_value(raw_value.strip())
            for raw_value in raw_values.split(",")
            if raw_value.strip()
        ]

        if not parsed_values:
            raise ValueError(
                f"--sweep-strategy-param {name} must include at least one value"
            )

        parsed[name] = parsed_values

    return parsed


def _parse_sweep_value(value: str):
    lower_value = value.lower()

    if lower_value in {"true", "false"}:
        return lower_value == "true"

    if lower_value in {"none", "null"}:
        return None

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value

if __name__ == "__main__":
    main()
