from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ScannerSettings:
    benchmark_ticker: str = "SPY"
    output_file: str = "output/watchlist.csv"
    market_data_provider: str = os.environ.get("MARKET_DATA_PROVIDER", "massive")
    market_data_cache_enabled: bool = True
    market_data_cache_path: str = "output/market_data_cache.sqlite"
    market_data_cache_retention_years: int = 5
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
    cache_warmup_enabled: bool = True
    cache_warmup_batch_size: int = 50
    cache_warmup_batch_delay_seconds: float = 0.5
    cache_warmup_max_provider_batches: int | None = None
    cache_warmup_stop_on_rate_limit: bool = True
    massive_batch_workers: int = int(os.environ.get("MASSIVE_BATCH_WORKERS", "10"))
    max_workers: int = 40
    backtest_max_workers: int = 80
    relative_strength_lookback_days: int = 63


settings = ScannerSettings()
