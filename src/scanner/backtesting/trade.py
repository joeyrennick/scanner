from dataclasses import dataclass
from datetime import date


@dataclass
class Trade:
    ticker: str
    strategy_name: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float

    @property
    def return_percent(self) -> float:
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100

    def to_dict(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Strategy": self.strategy_name,
            "Entry Date": self.entry_date.isoformat(),
            "Exit Date": self.exit_date.isoformat(),
            "Hold Days": (self.exit_date - self.entry_date).days,
            "Entry Price": round(self.entry_price, 2),
            "Exit Price": round(self.exit_price, 2),
            "Return %": round(self.return_percent, 2),
            "Winning Trade": "YES" if self.return_percent > 0 else "NO",
        }