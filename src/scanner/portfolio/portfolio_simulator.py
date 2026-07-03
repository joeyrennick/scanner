from datetime import date

import pandas as pd

from scanner.backtesting.trade import Trade
from scanner.portfolio.portfolio import Portfolio
from scanner.portfolio.portfolio_simulation_result import PortfolioSimulationResult


class PortfolioSimulator:

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        max_open_positions: int = 10,
        position_size_percent: float = 0.10,
    ):
        self.initial_cash = initial_cash
        self.max_open_positions = max_open_positions
        self.position_size_percent = position_size_percent

    def run(self, trades: list[Trade]) -> PortfolioSimulationResult:
        portfolio = Portfolio(
            initial_cash=self.initial_cash,
            max_open_positions=self.max_open_positions,
            position_size_percent=self.position_size_percent,
        )
        trades_by_entry_date = self._group_trades_by_entry_date(trades)
        simulation_dates = self._simulation_dates(trades)
        equity_points = []
        skipped_trades = 0

        if not simulation_dates:
            return PortfolioSimulationResult(
                initial_cash=portfolio.initial_cash,
                final_cash=portfolio.cash,
                final_equity=portfolio.cash,
                equity_curve=pd.DataFrame(columns=["Date", "Cash", "Open Value", "Equity"]),
                positions=[],
                skipped_trades=0,
            )

        for current_date in simulation_dates:
            portfolio.close_positions_on(current_date)

            for trade in trades_by_entry_date.get(current_date, []):
                position = portfolio.open_position(trade)

                if position is None:
                    skipped_trades += 1

            open_value = sum(
                position.market_value(current_date)
                for position in portfolio.open_positions
            )
            equity_points.append(
                {
                    "Date": current_date,
                    "Cash": portfolio.cash,
                    "Open Value": open_value,
                    "Equity": portfolio.cash + open_value,
                    "Open Positions": len(portfolio.open_positions),
                }
            )

        final_date = simulation_dates[-1]
        portfolio.close_positions_on(final_date)
        final_equity = portfolio.equity(final_date)

        equity_curve = pd.DataFrame(equity_points)

        return PortfolioSimulationResult(
            initial_cash=portfolio.initial_cash,
            final_cash=portfolio.cash,
            final_equity=final_equity,
            equity_curve=equity_curve,
            positions=portfolio.closed_positions + portfolio.open_positions,
            skipped_trades=skipped_trades,
        )

    @staticmethod
    def _group_trades_by_entry_date(trades: list[Trade]) -> dict[date, list[Trade]]:
        grouped: dict[date, list[Trade]] = {}

        for trade in sorted(trades, key=lambda trade: (trade.entry_date, trade.ticker)):
            grouped.setdefault(trade.entry_date, []).append(trade)

        return grouped

    @staticmethod
    def _simulation_dates(trades: list[Trade]) -> list[date]:
        dates = set()

        for trade in trades:
            dates.add(trade.entry_date)
            dates.add(trade.exit_date)

        return sorted(dates)
