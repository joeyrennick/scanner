from dataclasses import dataclass


@dataclass
class Trade:
    ticker: str
    strategy_name: str
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float

    @property
    def return_percent(self) -> float:
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100