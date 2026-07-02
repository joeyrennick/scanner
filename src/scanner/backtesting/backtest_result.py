from dataclasses import dataclass

from scanner.backtesting.backtest_statistics import BacktestStatistics
from scanner.backtesting.trade import Trade


@dataclass
class BacktestResult:
    ticker: str
    strategy_name: str
    trades: list[Trade]

    @property
    def statistics(self) -> BacktestStatistics:
        return BacktestStatistics(self.trades)