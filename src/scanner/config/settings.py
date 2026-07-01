from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerSettings:
    benchmark_ticker: str = "SPY"
    output_file: str = "output/watchlist.csv"
    max_workers: int = 10
    relative_strength_lookback_days: int = 63


settings = ScannerSettings()