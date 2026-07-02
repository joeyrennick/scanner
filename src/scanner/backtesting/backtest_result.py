from dataclasses import dataclass

from scanner.backtesting.trade import Trade


@dataclass
class BacktestResult:
    ticker: str
    strategy_name: str
    trades: list[Trade]

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0

        wins = [trade for trade in self.trades if trade.return_percent > 0]
        return (len(wins) / len(self.trades)) * 100

    @property
    def average_return(self) -> float:
        if not self.trades:
            return 0.0

        return sum(trade.return_percent for trade in self.trades) / len(self.trades)