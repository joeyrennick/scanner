from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import time

import pandas as pd

from scanner.config.settings import settings
from scanner.data.market_data import (
    check_market_data_connectivity,
    configure_market_data_cache,
    configure_market_data_provider,
    download_price_data,
    get_market_data_cache_overview,
    get_market_data_cache_stats,
)
from scanner.services.market_analyzer import MarketAnalyzer
from scanner.services.price_filter import filter_tickers_by_price
from scanner.universe.universe_provider import UniverseProvider
from scanner.strategies.strategy_category import StrategyCategory
from scanner.utils.logger import setup_logging
from scanner.utils.cache_summary import format_cache_summary


def analyze_one(ticker: str, benchmark_data, period: str):
    analyzer = MarketAnalyzer()
    result = analyzer.analyze(ticker, benchmark_data, period=period)
    return ticker, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--universe",
        choices=UniverseProvider.SUPPORTED_UNIVERSES,
        default="all",
        help="Universe to scan. Defaults to all supported US stock universes.",
    )
    parser.add_argument(
        "--preflight-market-data",
        action="store_true",
        help="Check Yahoo/yfinance connectivity before running the scan.",
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
        default=settings.scan_history_period,
        help="Price history period to download for scanner analysis.",
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

    logger = setup_logging()

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
            logger.error(f"Market data preflight failed: {error}")
            raise SystemExit(1)

        logger.info(
            "Market data preflight passed for "
            f"{result.ticker} ({result.rows} rows in {result.elapsed_seconds:.2f}s)"
        )

    start = time.perf_counter()

    tickers = UniverseProvider().get_universe_tickers(args.universe)

    if args.min_price is not None or args.max_price is not None:
        logger.info(
            "Applying price filter: "
            f"min={args.min_price if args.min_price is not None else 'none'}, "
            f"max={args.max_price if args.max_price is not None else 'none'}"
        )
        price_filter_result = filter_tickers_by_price(
            tickers=tickers,
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
            logger=logger,
        )
        tickers = price_filter_result.tickers
        logger.info(
            "Price filter kept "
            f"{price_filter_result.passed_count}/{price_filter_result.checked_count} "
            f"tickers; skipped={price_filter_result.skipped_count}; "
            f"provider_calls_attempted={price_filter_result.provider_calls_attempted}; "
            f"provider_call_limit={price_filter_result.provider_calls_allowed}; "
            f"provider_batches_attempted={price_filter_result.provider_batches_attempted}; "
            f"provider_batch_limit={price_filter_result.provider_batches_allowed}"
        )

    benchmark_data = download_price_data(
        settings.benchmark_ticker,
        period=args.history_period,
    )

    results = []
    skipped = []

    logger.info(f"Loaded {len(tickers)} tickers")
    logger.info(f"Starting scan with {settings.max_workers} workers")

    with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
        futures = {
            executor.submit(
                analyze_one,
                ticker,
                benchmark_data,
                args.history_period,
            ): ticker
            for ticker in tickers
        }

        completed = 0

        for future in as_completed(futures):
            completed += 1
            ticker = futures[future]

            try:
                _, result = future.result()
                results.append(result)
                logger.info(f"[{completed}/{len(tickers)}] Finished {ticker}")

            except Exception as e:
                skipped.append((ticker, str(e)))
                logger.warning(f"[{completed}/{len(tickers)}] Skipping {ticker}: {e}")


    trade_candidates = [
        result
        for result in results
        if any(
            strategy.triggered and strategy.category == StrategyCategory.ENTRY
            for strategy in result.strategy_results
        )
    ]

    if trade_candidates:
        df = pd.DataFrame([result.to_dict() for result in trade_candidates])
        df = df.sort_values(by="Composite Score", ascending=False)
    else:
        logger.info("No trade candidates found.")
        df = pd.DataFrame()

    print(df)

    df.to_csv(settings.output_file, index=False)

    elapsed = time.perf_counter() - start

    logger.info("=" * 50)
    logger.info(f"Total tickers: {len(tickers)}")
    logger.info(f"Successfully analyzed: {len(results)}")
    logger.info(f"Trade candidates: {len(trade_candidates)}")
    logger.info(f"Skipped: {len(skipped)}")
    logger.info(f"Scan completed in {elapsed:.2f} seconds")

    cache_summary = format_cache_summary(
        get_market_data_cache_stats(),
        get_market_data_cache_overview(),
    )

    if cache_summary:
        logger.info(cache_summary)

    if skipped:
        logger.info("Skipped tickers:")
        for ticker, reason in skipped:
            logger.info(f"  - {ticker}: {reason}")


if __name__ == "__main__":
    main()
