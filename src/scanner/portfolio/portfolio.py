from dataclasses import dataclass, field
from datetime import date
from math import floor

from scanner.backtesting.trade import Trade
from scanner.portfolio.execution_model import ExecutionModel
from scanner.portfolio.position import Position


@dataclass
class Portfolio:
    initial_cash: float = 100_000.0
    max_open_positions: int = 10
    position_size_percent: float = 0.10
    execution_model: ExecutionModel = field(default_factory=ExecutionModel)
    max_positions_per_ticker: int | None = None
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
        if self.max_positions_per_ticker is not None and self.max_positions_per_ticker <= 0:
            raise ValueError("max_positions_per_ticker must be greater than zero")

        self.cash = self.initial_cash

    def equity(self, current_date: date) -> float:
        open_value = sum(
            position.market_value(current_date)
            for position in self.open_positions
        )
        return self.cash + open_value

    def available_slots(self) -> int:
        return self.max_open_positions - len(self.open_positions)

    def can_open_position(self, trade: Trade | None = None) -> bool:
        if self.available_slots() <= 0 or self.cash <= 0:
            return False

        if trade is None or self.max_positions_per_ticker is None:
            return True

        open_ticker_positions = [
            position
            for position in self.open_positions
            if position.ticker == trade.ticker
        ]
        return len(open_ticker_positions) < self.max_positions_per_ticker

    def position_shares_for_trade(self, trade: Trade, entry_price: float) -> int:
        target_position_value = self.equity(trade.entry_date) * self.position_size_percent
        position_value = min(target_position_value, self.cash)
        available_for_shares = position_value - self.execution_model.commission_per_trade

        if available_for_shares <= 0:
            return 0

        effective_price_per_share = entry_price + self.execution_model.commission_per_share
        return floor(available_for_shares / effective_price_per_share)

    def open_position(self, trade: Trade) -> Position | None:
        if not self.can_open_position(trade):
            return None

        entry_price = self.execution_model.entry_price_for_trade(trade)

        if entry_price is None:
            return None

        shares = self.position_shares_for_trade(trade, entry_price)

        if shares <= 0:
            return None

        exit_price, exit_reason = self.execution_model.exit_price_for_trade(
            trade,
            entry_price,
        )
        entry_commission = self.execution_model.commission_for_order(shares)
        exit_commission = self.execution_model.commission_for_order(shares)
        position = Position(
            trade=trade,
            shares=shares,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_commission=entry_commission,
            exit_commission=exit_commission,
            exit_reason=exit_reason,
        )
        self.cash -= position.entry_value + position.entry_commission
        self.open_positions.append(position)
        return position

    def close_positions_on(self, current_date: date) -> list[Position]:
        closing_positions = [
            position
            for position in self.open_positions
            if position.exit_date <= current_date
        ]

        for position in closing_positions:
            self.cash += position.exit_value - position.exit_commission
            self.open_positions.remove(position)
            self.closed_positions.append(position)

        return closing_positions
