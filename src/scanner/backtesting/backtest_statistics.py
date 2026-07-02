from dataclasses import dataclass

from scanner.backtesting.trade import Trade


@dataclass
class BacktestStatistics:
    trades: list[Trade]

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> list[Trade]:
        return [
            trade
            for trade in self.trades
            if trade.return_percent > 0
        ]

    @property
    def losing_trades(self) -> list[Trade]:
        return [
            trade
            for trade in self.trades
            if trade.return_percent <= 0
        ]

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0

        return (len(self.winning_trades) / len(self.trades)) * 100

    @property
    def average_return(self) -> float:
        if not self.trades:
            return 0.0

        return sum(t.return_percent for t in self.trades) / len(self.trades)

    @property
    def average_win(self) -> float:
        if not self.winning_trades:
            return 0.0

        return (
            sum(t.return_percent for t in self.winning_trades)
            / len(self.winning_trades)
        )

    @property
    def average_loss(self) -> float:
        if not self.losing_trades:
            return 0.0

        return (
            sum(t.return_percent for t in self.losing_trades)
            / len(self.losing_trades)
        )

    @property
    def best_trade_return(self) -> float:
        if not self.trades:
            return 0.0

        return max(t.return_percent for t in self.trades)

    @property
    def worst_trade_return(self) -> float:
        if not self.trades:
            return 0.0

        return min(t.return_percent for t in self.trades)

    @property
    def expectancy(self) -> float:
        """
        Average expected return per trade.

        Expectancy = Win% * Avg Win + Loss% * Avg Loss
        """

        win_probability = self.win_rate / 100
        loss_probability = 1 - win_probability

        return (
            (win_probability * self.average_win)
            + (loss_probability * self.average_loss)
        )