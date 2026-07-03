from dataclasses import dataclass

import numpy as np
import pandas as pd

from scanner.portfolio.position import Position


@dataclass
class PortfolioSimulationResult:
    initial_cash: float
    final_cash: float
    final_equity: float
    equity_curve: pd.DataFrame
    positions: list[Position]
    skipped_trades: int

    @property
    def total_return_percent(self) -> float:
        return ((self.final_equity - self.initial_cash) / self.initial_cash) * 100

    @property
    def max_drawdown_percent(self) -> float:
        if self.equity_curve.empty:
            return 0.0

        running_high = self.equity_curve["Equity"].cummax()
        drawdowns = (self.equity_curve["Equity"] - running_high) / running_high * 100
        return drawdowns.min()

    @property
    def cagr_percent(self) -> float:
        if self.equity_curve.empty:
            return 0.0

        start_date = self.equity_curve.iloc[0]["Date"]
        end_date = self.equity_curve.iloc[-1]["Date"]
        years = (end_date - start_date).days / 365.25

        if years <= 0 or self.final_equity <= 0:
            return 0.0

        cagr = (self.final_equity / self.initial_cash) ** (1 / years) - 1
        return cagr * 100

    @property
    def sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0

        returns = self.equity_curve["Equity"].pct_change().dropna()

        if returns.empty:
            return 0.0

        standard_deviation = returns.std(ddof=1)

        if standard_deviation == 0 or np.isnan(standard_deviation):
            return 0.0

        return (returns.mean() / standard_deviation) * np.sqrt(252)

    def positions_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([position.to_dict() for position in self.positions])
