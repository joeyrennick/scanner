from dataclasses import dataclass
from datetime import date

from scanner.backtesting.trade import Trade


@dataclass
class Position:
    trade: Trade
    shares: int
    entry_price: float | None = None
    exit_price: float | None = None
    entry_commission: float = 0.0
    exit_commission: float = 0.0
    exit_reason: str = "TIME_EXIT"

    def __post_init__(self):
        if self.entry_price is None:
            self.entry_price = self.trade.entry_price
        if self.exit_price is None:
            self.exit_price = self.trade.exit_price

    @property
    def ticker(self) -> str:
        return self.trade.ticker

    @property
    def entry_date(self) -> date:
        return self.trade.entry_date

    @property
    def exit_date(self) -> date:
        return self.trade.exit_date

    @property
    def entry_value(self) -> float:
        return self.shares * self.entry_price

    @property
    def exit_value(self) -> float:
        return self.shares * self.exit_price

    @property
    def total_commission(self) -> float:
        return self.entry_commission + self.exit_commission

    @property
    def profit_loss(self) -> float:
        return self.exit_value - self.entry_value - self.total_commission

    @property
    def return_percent(self) -> float:
        if self.entry_value == 0:
            return 0.0

        return (self.profit_loss / self.entry_value) * 100

    def market_value(self, current_date: date) -> float:
        if current_date >= self.exit_date:
            return self.exit_value

        return self.entry_value

    def to_dict(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Entry Date": self.entry_date.isoformat(),
            "Exit Date": self.exit_date.isoformat(),
            "Shares": self.shares,
            "Entry Price": round(self.entry_price, 2),
            "Exit Price": round(self.exit_price, 2),
            "Entry Value": round(self.entry_value, 2),
            "Exit Value": round(self.exit_value, 2),
            "Entry Commission": round(self.entry_commission, 2),
            "Exit Commission": round(self.exit_commission, 2),
            "Total Commission": round(self.total_commission, 2),
            "Profit/Loss": round(self.profit_loss, 2),
            "Return %": round(self.return_percent, 2),
            "Exit Reason": self.exit_reason,
        }
