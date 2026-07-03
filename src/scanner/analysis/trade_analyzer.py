from pathlib import Path

import numpy as np
import pandas as pd


class TradeAnalyzer:
    RETURN_COLUMN = "Return %"
    TICKER_COLUMN = "Ticker"
    ENTRY_DATE_COLUMN = "Entry Date"
    EXIT_DATE_COLUMN = "Exit Date"

    def __init__(self, trade_csv_path: str):
        self.trade_csv_path = Path(trade_csv_path)
        self.trades = pd.read_csv(self.trade_csv_path)
        self._prepare_trades()

    @classmethod
    def from_dataframe(cls, trades: pd.DataFrame):
        analyzer = cls.__new__(cls)
        analyzer.trade_csv_path = None
        analyzer.trades = trades.copy()
        analyzer._prepare_trades()
        return analyzer

    def _prepare_trades(self):
        self._validate_columns()

        self.trades[self.RETURN_COLUMN] = pd.to_numeric(
            self.trades[self.RETURN_COLUMN],
            errors="raise",
        )

        for column in [self.ENTRY_DATE_COLUMN, self.EXIT_DATE_COLUMN]:
            if column in self.trades.columns:
                self.trades[column] = pd.to_datetime(self.trades[column])

    def _validate_columns(self):
        required_columns = [self.RETURN_COLUMN]
        missing_columns = [
            column for column in required_columns if column not in self.trades.columns
        ]

        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"Trade CSV is missing required columns: {missing}")

    def summary(self) -> dict:
        total_trades = len(self.trades)

        if total_trades == 0:
            return {
                "Total Trades": 0,
                "Win Rate": 0.0,
                "Average Return": 0.0,
                "Median Return": 0.0,
                "Average Winner": 0.0,
                "Average Loser": 0.0,
                "Best Trade": 0.0,
                "Worst Trade": 0.0,
                "Profit Factor": 0.0,
                "Expectancy": 0.0,
            }

        returns = self.trades[self.RETURN_COLUMN]
        winning_trades = returns[returns > 0]
        losing_trades = returns[returns <= 0]

        return {
            "Total Trades": total_trades,
            "Win Rate": len(winning_trades) / total_trades * 100,
            "Average Return": returns.mean(),
            "Median Return": returns.median(),
            "Average Winner": winning_trades.mean() if len(winning_trades) else 0.0,
            "Average Loser": losing_trades.mean() if len(losing_trades) else 0.0,
            "Best Trade": returns.max(),
            "Worst Trade": returns.min(),
            "Profit Factor": self.profit_factor(),
            "Expectancy": returns.mean(),
        }

    def ticker_summary(self, min_trades: int = 1) -> pd.DataFrame:
        if self.TICKER_COLUMN not in self.trades.columns:
            raise ValueError("Trade CSV is missing required columns: Ticker")

        if self.trades.empty:
            return pd.DataFrame(
                columns=[
                    "Ticker",
                    "Trades",
                    "Win Rate",
                    "Average Return",
                    "Median Return",
                    "Best Trade",
                    "Worst Trade",
                    "Profit Factor",
                ]
            )

        grouped = self.trades.groupby(self.TICKER_COLUMN)
        summary = grouped[self.RETURN_COLUMN].agg(
            Trades="count",
            Average_Return="mean",
            Median_Return="median",
            Best_Trade="max",
            Worst_Trade="min",
        )

        summary["Win_Rate"] = grouped[self.RETURN_COLUMN].apply(
            lambda returns: (returns > 0).mean() * 100
        )
        summary["Profit_Factor"] = grouped[self.RETURN_COLUMN].apply(
            self._profit_factor_for_returns
        )

        summary = summary.reset_index()
        summary = summary[summary["Trades"] >= min_trades]
        summary = summary.rename(
            columns={
                self.TICKER_COLUMN: "Ticker",
                "Average_Return": "Average Return",
                "Median_Return": "Median Return",
                "Best_Trade": "Best Trade",
                "Worst_Trade": "Worst Trade",
                "Win_Rate": "Win Rate",
                "Profit_Factor": "Profit Factor",
            }
        )

        columns = [
            "Ticker",
            "Trades",
            "Win Rate",
            "Average Return",
            "Median Return",
            "Best Trade",
            "Worst Trade",
            "Profit Factor",
        ]
        return summary[columns].sort_values(
            by=["Average Return", "Win Rate", "Trades"],
            ascending=[False, False, False],
        )

    def rank_tickers_by_average_return(self, min_trades: int = 1) -> pd.DataFrame:
        return self.ticker_summary(min_trades=min_trades).sort_values(
            by=["Average Return", "Win Rate", "Trades"],
            ascending=[False, False, False],
        )

    def rank_tickers_by_win_rate(self, min_trades: int = 1) -> pd.DataFrame:
        return self.ticker_summary(min_trades=min_trades).sort_values(
            by=["Win Rate", "Average Return", "Trades"],
            ascending=[False, False, False],
        )

    def monthly_summary(self) -> pd.DataFrame:
        self._require_date_column(self.EXIT_DATE_COLUMN)
        trades = self.trades.copy()
        trades["Month"] = trades[self.EXIT_DATE_COLUMN].dt.to_period("M").astype(str)
        return self._period_summary(trades, "Month")

    def weekday_summary(self) -> pd.DataFrame:
        self._require_date_column(self.ENTRY_DATE_COLUMN)
        trades = self.trades.copy()
        trades["Weekday"] = trades[self.ENTRY_DATE_COLUMN].dt.day_name()
        summary = self._period_summary(trades, "Weekday")

        weekday_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        summary["Weekday"] = pd.Categorical(
            summary["Weekday"],
            categories=weekday_order,
            ordered=True,
        )
        return summary.sort_values("Weekday").reset_index(drop=True)

    def longest_winning_streak(self) -> int:
        return self._longest_streak(winning=True)

    def longest_losing_streak(self) -> int:
        return self._longest_streak(winning=False)

    def profit_factor(self) -> float:
        return self._profit_factor_for_returns(self.trades[self.RETURN_COLUMN])

    def return_distribution(self, bins: list[float] | None = None) -> pd.DataFrame:
        if bins is None:
            bins = [-np.inf, -10, -5, -2, 0, 2, 5, 10, np.inf]

        labels = [
            self._format_bin_label(left, right)
            for left, right in zip(bins[:-1], bins[1:])
        ]

        bucket = pd.cut(
            self.trades[self.RETURN_COLUMN],
            bins=bins,
            labels=labels,
            include_lowest=True,
            right=True,
        )

        counts = bucket.value_counts(sort=False)
        total = len(self.trades)
        distribution = pd.DataFrame(
            {
                "Range": counts.index.astype(str),
                "Trades": counts.values,
                "Percent": (counts.values / total * 100) if total else 0.0,
            }
        )
        return distribution

    def export_ticker_summary(self, output_path: str, min_trades: int = 1):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.ticker_summary(min_trades=min_trades).to_csv(output_path, index=False)

    def _period_summary(self, trades: pd.DataFrame, period_column: str) -> pd.DataFrame:
        grouped = trades.groupby(period_column)
        summary = grouped[self.RETURN_COLUMN].agg(
            Trades="count",
            Average_Return="mean",
            Median_Return="median",
            Best_Trade="max",
            Worst_Trade="min",
        )
        summary["Win_Rate"] = grouped[self.RETURN_COLUMN].apply(
            lambda returns: (returns > 0).mean() * 100
        )
        summary = summary.reset_index()
        return summary.rename(
            columns={
                "Average_Return": "Average Return",
                "Median_Return": "Median Return",
                "Best_Trade": "Best Trade",
                "Worst_Trade": "Worst Trade",
                "Win_Rate": "Win Rate",
            }
        )

    def _longest_streak(self, winning: bool) -> int:
        trades = self.trades

        if self.EXIT_DATE_COLUMN in trades.columns:
            trades = trades.sort_values(self.EXIT_DATE_COLUMN)

        current_streak = 0
        longest_streak = 0

        for return_percent in trades[self.RETURN_COLUMN]:
            is_match = return_percent > 0 if winning else return_percent <= 0

            if is_match:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 0

        return longest_streak

    def _require_date_column(self, column: str):
        if column not in self.trades.columns:
            raise ValueError(f"Trade CSV is missing required columns: {column}")

    @staticmethod
    def _profit_factor_for_returns(returns: pd.Series) -> float:
        gross_profit = returns[returns > 0].sum()
        gross_loss = returns[returns < 0].sum()

        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0

        return gross_profit / abs(gross_loss)

    @staticmethod
    def _format_bin_label(left: float, right: float) -> str:
        if left == -np.inf:
            return f"<= {right:g}%"
        if right == np.inf:
            return f"> {left:g}%"
        return f"> {left:g}% to <= {right:g}%"
