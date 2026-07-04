from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerSettings:
    benchmark_ticker: str = "SPY"
    output_file: str = "output/watchlist.csv"
    market_data_provider: str = "yahoo"
    market_data_cache_enabled: bool = True
    market_data_cache_path: str = "output/market_data_cache.sqlite"
    market_data_refresh_overlap_days: int = 10
    scan_history_period: str = "1y"
    backtest_history_period: str = "1y"
    price_filter_sample_period: str = "5d"
    price_filter_max_cache_age_days: int = 7
    price_filter_workers: int = 5
    price_filter_max_provider_calls: int | None = 500
    price_filter_batch_size: int = 50
    price_filter_batch_delay_seconds: float = 0.5
    price_filter_max_provider_batches: int | None = 10
    max_workers: int = 40
    relative_strength_lookback_days: int = 63


settings = ScannerSettings()
