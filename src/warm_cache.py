import argparse
from dataclasses import replace

from scanner.config.settings import settings
from scanner.context import ScannerContext
from scanner.data.market_data import configure_market_data_provider
from scanner.services.cache_warmup import CacheWarmupConfig, CacheWarmupService
from scanner.universe.universe_provider import UniverseProvider
from scanner.utils.cache_summary import format_cache_summary
from scanner.utils.logger import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Safely warm the local market data cache in provider batches.",
    )
    parser.add_argument(
        "--universe",
        choices=UniverseProvider.SUPPORTED_UNIVERSES,
        default="all",
        help="Universe to warm. Defaults to all supported US stock universes.",
    )
    parser.add_argument(
        "--tickers",
        help="Optional comma-separated ticker override.",
    )
    parser.add_argument(
        "--market-data-provider",
        default=settings.market_data_provider,
        help="Market data provider to use for downloads.",
    )
    parser.add_argument(
        "--history-period",
        default=settings.scan_history_period,
        help="Price history period to cache.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.cache_warmup_batch_size,
        help="Number of symbols to request per provider batch.",
    )
    parser.add_argument(
        "--max-provider-batches",
        type=int,
        default=settings.cache_warmup_max_provider_batches,
        help="Maximum provider batches to make in one run.",
    )
    parser.add_argument(
        "--batch-delay-ms",
        type=int,
        default=int(settings.cache_warmup_batch_delay_seconds * 1000),
        help="Delay between provider batches in milliseconds.",
    )
    parser.add_argument(
        "--cache-only-preview",
        action="store_true",
        help="Preview cache coverage without making provider calls.",
    )
    parser.add_argument(
        "--refresh-market-data-cache",
        action="store_true",
        help="Force provider refreshes. This can increase Yahoo request volume.",
    )
    parser.add_argument(
        "--keep-going-on-rate-limit",
        action="store_true",
        help="Do not stop automatically when a rate-limit error is detected.",
    )
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")

    if args.max_provider_batches is not None and args.max_provider_batches < 0:
        parser.error("--max-provider-batches cannot be negative")

    if args.batch_delay_ms < 0:
        parser.error("--batch-delay-ms cannot be negative")

    try:
        configure_market_data_provider(args.market_data_provider)
    except ValueError as error:
        parser.error(str(error))

    logger = setup_logging()
    context = ScannerContext(
        settings=replace(settings, market_data_provider=args.market_data_provider),
        logger=logger,
        market_data_cache_enabled=True,
        market_data_cache_force_refresh=args.refresh_market_data_cache,
    )

    tickers = _resolve_tickers(args)
    result = CacheWarmupService(context=context, logger=logger).run(
        CacheWarmupConfig(
            tickers=[settings.benchmark_ticker] + tickers,
            period=args.history_period,
            batch_size=args.batch_size,
            batch_delay_seconds=args.batch_delay_ms / 1000,
            max_provider_batches=args.max_provider_batches,
            cache_only_preview=args.cache_only_preview,
            stop_on_rate_limit=not args.keep_going_on_rate_limit,
        )
    )

    logger.info(result.summary())

    cache_summary = format_cache_summary(
        context.get_market_data_cache_stats(),
        context.get_market_data_cache_overview(),
    )
    if cache_summary:
        logger.info(cache_summary)


def _resolve_tickers(args) -> list[str]:
    if args.tickers:
        return [
            ticker.strip().upper()
            for ticker in args.tickers.split(",")
            if ticker.strip()
        ]

    return UniverseProvider().get_universe_tickers(args.universe)


if __name__ == "__main__":
    main()
