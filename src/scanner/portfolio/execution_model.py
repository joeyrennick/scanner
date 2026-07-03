from dataclasses import dataclass

from scanner.backtesting.trade import Trade


@dataclass
class ExecutionModel:
    commission_per_trade: float = 0.0
    commission_per_share: float = 0.0
    slippage_percent: float = 0.0
    limit_entry_offset_percent: float | None = None
    assume_limit_fills: bool = False
    stop_loss_percent: float | None = None
    trailing_stop_percent: float | None = None

    def __post_init__(self):
        if self.commission_per_trade < 0:
            raise ValueError("commission_per_trade cannot be negative")
        if self.commission_per_share < 0:
            raise ValueError("commission_per_share cannot be negative")
        if self.slippage_percent < 0:
            raise ValueError("slippage_percent cannot be negative")

        for label, value in [
            ("limit_entry_offset_percent", self.limit_entry_offset_percent),
            ("stop_loss_percent", self.stop_loss_percent),
            ("trailing_stop_percent", self.trailing_stop_percent),
        ]:
            if value is not None and value < 0:
                raise ValueError(f"{label} cannot be negative")

    def entry_price_for_trade(self, trade: Trade) -> float | None:
        entry_price = trade.entry_price

        if self.limit_entry_offset_percent is not None:
            limit_price = trade.entry_price * (1 - self.limit_entry_offset_percent / 100)

            if limit_price < trade.entry_price and not self.assume_limit_fills:
                return None

            entry_price = limit_price

        return entry_price * (1 + self.slippage_percent / 100)

    def exit_price_for_trade(self, trade: Trade, entry_price: float) -> tuple[float, str]:
        exit_price = trade.exit_price
        exit_reason = "TIME_EXIT"

        if self.stop_loss_percent is not None:
            stop_price = entry_price * (1 - self.stop_loss_percent / 100)

            if exit_price <= stop_price:
                exit_price = stop_price
                exit_reason = "STOP_LOSS"

        if self.trailing_stop_percent is not None:
            highest_observed_price = max(entry_price, trade.exit_price)
            trailing_stop_price = highest_observed_price * (
                1 - self.trailing_stop_percent / 100
            )

            if exit_price <= trailing_stop_price:
                exit_price = trailing_stop_price
                exit_reason = "TRAILING_STOP"

        return exit_price * (1 - self.slippage_percent / 100), exit_reason

    def commission_for_order(self, shares: int) -> float:
        return self.commission_per_trade + (shares * self.commission_per_share)
