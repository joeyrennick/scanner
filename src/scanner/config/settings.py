from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerSettings:
    benchmark_ticker: str = "SPY"
    output_file: str = "output/watchlist.csv"
    market_data_provider: str = "yahoo"
    market_data_cache_enabled: bool = True
    market_data_cache_path: str = "output/market_data_cache.sqlite"
    market_data_refresh_overlap_days: int = 10
    max_workers: int = 40
    relative_strength_lookback_days: int = 63


settings = ScannerSettings()
