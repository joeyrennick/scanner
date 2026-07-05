from dataclasses import dataclass
from datetime import date

from scanner.config.settings import settings


@dataclass(frozen=True)
class BacktestConfig:
    history_period: str = settings.backtest_history_period
    hold_days: int = 5
    min_history_days: int = 252
    allow_overlapping_trades: bool = True
    signal_start_date: date | str | None = None
    signal_end_date: date | str | None = None

    def __post_init__(self):
        if self.hold_days <= 0:
            raise ValueError("hold_days must be greater than zero")

        if self.min_history_days < 0:
            raise ValueError("min_history_days cannot be negative")

        if (
            self.signal_start_date is not None
            and self.signal_end_date is not None
            and str(self.signal_start_date) > str(self.signal_end_date)
        ):
            raise ValueError("signal_start_date cannot be after signal_end_date")
