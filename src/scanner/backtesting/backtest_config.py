from dataclasses import dataclass

from scanner.config.settings import settings


@dataclass(frozen=True)
class BacktestConfig:
    history_period: str = settings.backtest_history_period
    hold_days: int = 5
    min_history_days: int = 252
    allow_overlapping_trades: bool = True

    def __post_init__(self):
        if self.hold_days <= 0:
            raise ValueError("hold_days must be greater than zero")

        if self.min_history_days < 0:
            raise ValueError("min_history_days cannot be negative")
