import argparse
from dataclasses import replace

from scanner.config.settings import settings
from scanner.data.ownership import owned_application
from scanner.context import ScannerContext
from scanner.data.market_data import (
    check_market_data_connectivity,
    configure_market_data_cache,
    configure_market_data_provider,
    get_market_data_provider,
)
from scanner.services.scan_service import ScanConfig, ScanService
from scanner.universe.universe_provider import UniverseProvider
from scanner.utils.logger import setup_logging


@owned_application
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
    parser.add_argument(
        "--skip-cache-warmup",
        action="store_true",
        help="Skip the pre-scan market data cache warmup.",
    )
    parser.add_argument(
        "--cache-warmup-only",
        action="store_true",
        help="Warm the market data cache and exit without running the scanner.",
    )
    parser.add_argument(
        "--cache-warmup-batch-size",
        type=int,
        default=settings.cache_warmup_batch_size,
        help="Number of symbols to request in each cache warmup batch.",
    )
    parser.add_argument(
        "--cache-warmup-max-provider-batches",
        type=int,
        default=settings.cache_warmup_max_provider_batches,
        help="Maximum cache warmup provider batches to make in one run.",
    )
    parser.add_argument(
        "--cache-warmup-batch-delay-ms",
        type=int,
        default=int(settings.cache_warmup_batch_delay_seconds * 1000),
        help="Delay between cache warmup provider batches in milliseconds.",
    )
    parser.add_argument(
        "--cache-only-preview",
        action="store_true",
        help="Preview cache coverage without making provider calls.",
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

    if args.cache_warmup_batch_size <= 0:
        parser.error("--cache-warmup-batch-size must be greater than zero")

    if (
        args.cache_warmup_max_provider_batches is not None
        and args.cache_warmup_max_provider_batches < 0
    ):
        parser.error("--cache-warmup-max-provider-batches cannot be negative")

    if args.cache_warmup_batch_delay_ms < 0:
        parser.error("--cache-warmup-batch-delay-ms cannot be negative")

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

    context = ScannerContext(
        settings=replace(
            settings,
            market_data_provider=args.market_data_provider,
        ),
        logger=logger,
        market_data_provider=get_market_data_provider(),
        market_data_cache_enabled=not args.no_market_data_cache,
        market_data_cache_force_refresh=args.refresh_market_data_cache,
    )

    if args.cache_warmup_only or args.cache_only_preview:
        from scanner.services.cache_warmup import CacheWarmupConfig, CacheWarmupService

        tickers = UniverseProvider().get_universe_tickers(args.universe)
        result = CacheWarmupService(context=context, logger=logger).run(
            CacheWarmupConfig(
                tickers=[settings.benchmark_ticker] + tickers,
                period=args.history_period,
                batch_size=args.cache_warmup_batch_size,
                batch_delay_seconds=args.cache_warmup_batch_delay_ms / 1000,
                max_provider_batches=args.cache_warmup_max_provider_batches,
                cache_only_preview=args.cache_only_preview,
            )
        )
        logger.info(result.summary())
        return

    scan_result = ScanService(context=context, logger=logger).run(
        ScanConfig(
            universe=args.universe,
            market_data_provider=args.market_data_provider,
            history_period=args.history_period,
            output_file=settings.output_file,
            min_price=args.min_price,
            max_price=args.max_price,
            price_sample_period=args.price_sample_period,
            price_filter_batch_size=price_filter_batch_size,
            price_filter_max_provider_calls=args.price_filter_max_provider_calls,
            price_filter_max_provider_batches=args.price_filter_max_provider_batches,
            price_filter_batch_delay_seconds=args.price_filter_batch_delay_ms / 1000,
            warm_market_data_cache=not args.skip_cache_warmup,
            cache_warmup_batch_size=args.cache_warmup_batch_size,
            cache_warmup_max_provider_batches=args.cache_warmup_max_provider_batches,
            cache_warmup_batch_delay_seconds=args.cache_warmup_batch_delay_ms / 1000,
        )
    )

    print(scan_result.dataframe)


if __name__ == "__main__":
    main()
