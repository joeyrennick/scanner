from dataclasses import dataclass, field
from datetime import date
from math import floor

from scanner.backtesting.trade import Trade
from scanner.portfolio.position import Position


@dataclass
class Portfolio:
    initial_cash: float = 100_000.0
    max_open_positions: int = 10
    position_size_percent: float = 0.10
    cash: float = field(init=False)
    open_positions: list[Position] = field(default_factory=list)
    closed_positions: list[Position] = field(default_factory=list)

    def __post_init__(self):
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be greater than zero")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be greater than zero")
        if self.position_size_percent <= 0:
            raise ValueError("position_size_percent must be greater than zero")

        self.cash = self.initial_cash

    def equity(self, current_date: date) -> float:
        open_value = sum(
            position.market_value(current_date)
            for position in self.open_positions
        )
        return self.cash + open_value

    def available_slots(self) -> int:
        return self.max_open_positions - len(self.open_positions)

    def can_open_position(self) -> bool:
        return self.available_slots() > 0 and self.cash > 0

    def position_shares_for_trade(self, trade: Trade) -> int:
        target_position_value = self.equity(trade.entry_date) * self.position_size_percent
        position_value = min(target_position_value, self.cash)
        return floor(position_value / trade.entry_price)

    def open_position(self, trade: Trade) -> Position | None:
        if not self.can_open_position():
            return None

        shares = self.position_shares_for_trade(trade)

        if shares <= 0:
            return None

        position = Position(trade=trade, shares=shares)
        self.cash -= position.entry_value
        self.open_positions.append(position)
        return position

    def close_positions_on(self, current_date: date) -> list[Position]:
        closing_positions = [
            position
            for position in self.open_positions
            if position.exit_date <= current_date
        ]

        for position in closing_positions:
            self.cash += position.exit_value
            self.open_positions.remove(position)
            self.closed_positions.append(position)

        return closing_positions
