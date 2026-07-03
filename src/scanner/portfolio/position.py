from dataclasses import dataclass
from datetime import date

from scanner.backtesting.trade import Trade


@dataclass
class Position:
    trade: Trade
    shares: int

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
        return self.shares * self.trade.entry_price

    @property
    def exit_value(self) -> float:
        return self.shares * self.trade.exit_price

    @property
    def profit_loss(self) -> float:
        return self.exit_value - self.entry_value

    @property
    def return_percent(self) -> float:
        return self.trade.return_percent

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
            "Entry Price": round(self.trade.entry_price, 2),
            "Exit Price": round(self.trade.exit_price, 2),
            "Entry Value": round(self.entry_value, 2),
            "Exit Value": round(self.exit_value, 2),
            "Profit/Loss": round(self.profit_loss, 2),
            "Return %": round(self.return_percent, 2),
        }
