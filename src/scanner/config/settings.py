from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerSettings:
    benchmark_ticker: str = "SPY"
    output_file: str = "output/watchlist.csv"
    market_data_provider: str = "yahoo"
    max_workers: int = 40
    relative_strength_lookback_days: int = 63


settings = ScannerSettings()
