import argparse

from scanner.config.settings import settings
from scanner.data.market_data import (
    configure_market_data_cache,
    configure_market_data_provider,
    get_market_data_cache_stats,
)
from scanner.utils.worker_tuner import (
    DEFAULT_TICKERS,
    first_unstable_worker_count,
    benchmark_worker_counts,
    parse_worker_counts,
    recommend_worker_count,
    results_dataframe,
)


def main():
    parser = argparse.ArgumentParser(
        description="Find a stable worker count for concurrent market data downloads.",
    )
    parser.add_argument(
        "--workers",
        default="1,2,4,8,12,16,20,24,32",
        help="Comma-separated worker counts to test.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker sample to use for each worker-count trial.",
    )
    parser.add_argument("--period", default="3mo")
    parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=0.05,
        help="Failure rate above this threshold marks a worker count as unstable.",
    )
    parser.add_argument(
        "--latency-spike-multiple",
        type=float,
        default=2.0,
        help="Average latency multiple above baseline that marks instability.",
    )
    parser.add_argument("--export-csv")
    parser.add_argument(
        "--market-data-provider",
        default=settings.market_data_provider,
        help="Market data provider to use for worker tuning.",
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

    args = parser.parse_args()
    configure_market_data_provider(args.market_data_provider)
    configure_market_data_cache(
        enabled=not args.no_market_data_cache,
        force_refresh=args.refresh_market_data_cache,
    )
    worker_counts = parse_worker_counts(args.workers)
    results = benchmark_worker_counts(
        worker_counts=worker_counts,
        tickers=args.tickers,
        period=args.period,
    )
    results_df = results_dataframe(results)
    recommendation = recommend_worker_count(
        results,
        max_failure_rate=args.max_failure_rate,
        latency_spike_multiple=args.latency_spike_multiple,
    )

    print(results_df.to_string(index=False))
    print()

    if recommendation is None:
        print("Recommended max_workers: none; even the lowest worker count was unstable")
    else:
        print(f"Recommended max_workers: {recommendation}")

    first_unstable = first_unstable_worker_count(
        results,
        max_failure_rate=args.max_failure_rate,
        latency_spike_multiple=args.latency_spike_multiple,
    )

    if first_unstable is None:
        print("First unstable worker count: none")
    else:
        print(f"First unstable worker count: {first_unstable}")

    if args.export_csv:
        results_df.to_csv(args.export_csv, index=False)
        print(f"Exported worker benchmark results to {args.export_csv}")

    cache_stats = get_market_data_cache_stats()

    if cache_stats:
        print(
            "Market data cache: "
            f"hits={cache_stats.hits}, "
            f"misses={cache_stats.misses}, "
            f"provider_calls={cache_stats.provider_calls}, "
            f"rows_from_cache={cache_stats.rows_loaded_from_cache}, "
            f"rows_fetched={cache_stats.rows_fetched_from_provider}"
        )


if __name__ == "__main__":
    main()
