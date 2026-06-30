from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSettings:
    ma_short: int = 20
    ma_medium: int = 50
    ma_long: int = 200
    atr_window: int = 14
    volume_window: int = 20
    relative_strength_lookback_days: int = 63


@dataclass(frozen=True)
class ScannerSettings:
    tickers_file: str = "tickers.txt"
    output_file: str = "output/watchlist.csv"
    benchmark_ticker: str = "SPY"
    indicators: IndicatorSettings = IndicatorSettings()


settings = ScannerSettings()