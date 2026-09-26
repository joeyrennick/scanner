from html import escape
from pathlib import Path
import os

import numpy as np
import pandas as pd


class TradeAnalyzer:
    RETURN_COLUMN = "Return %"
    TICKER_COLUMN = "Ticker"
    STRATEGY_COLUMN = "Strategy"
    ENTRY_DATE_COLUMN = "Entry Date"
    EXIT_DATE_COLUMN = "Exit Date"
    COMPOSITE_SCORE_COLUMN = "Composite Score"
    RELATIVE_STRENGTH_COLUMN = "Relative Strength"
    RELATIVE_VOLUME_COLUMN = "Relative Volume"

    COMPOSITE_SCORE_BUCKETS = [-np.inf, 50, 70, 85, np.inf]
    RELATIVE_STRENGTH_BUCKETS = [-np.inf, 0, 10, 20, np.inf]
    RELATIVE_VOLUME_BUCKETS = [-np.inf, 0.8, 1.0, 1.5, 2.0, np.inf]

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

        for column in [
            self.COMPOSITE_SCORE_COLUMN,
            self.RELATIVE_STRENGTH_COLUMN,
            self.RELATIVE_VOLUME_COLUMN,
        ]:
            if column in self.trades.columns:
                self.trades[column] = pd.to_numeric(
                    self.trades[column],
                    errors="coerce",
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

    def strategy_summary(self) -> pd.DataFrame:
        self._require_column(self.STRATEGY_COLUMN)
        return self._group_summary(self.trades, self.STRATEGY_COLUMN)

    def composite_score_bucket_summary(
        self,
        bins: list[float] | None = None,
    ) -> pd.DataFrame:
        return self._numeric_bucket_summary(
            source_column=self.COMPOSITE_SCORE_COLUMN,
            bucket_column="Composite Score Bucket",
            bins=bins or self.COMPOSITE_SCORE_BUCKETS,
        )

    def relative_strength_bucket_summary(
        self,
        bins: list[float] | None = None,
    ) -> pd.DataFrame:
        return self._numeric_bucket_summary(
            source_column=self.RELATIVE_STRENGTH_COLUMN,
            bucket_column="Relative Strength Bucket",
            bins=bins or self.RELATIVE_STRENGTH_BUCKETS,
        )

    def relative_volume_bucket_summary(
        self,
        bins: list[float] | None = None,
    ) -> pd.DataFrame:
        return self._numeric_bucket_summary(
            source_column=self.RELATIVE_VOLUME_COLUMN,
            bucket_column="Relative Volume Bucket",
            bins=bins or self.RELATIVE_VOLUME_BUCKETS,
        )

    def bucket_summaries(self) -> dict[str, pd.DataFrame]:
        summaries = {}

        if self.STRATEGY_COLUMN in self.trades.columns:
            summaries["Strategy Summary"] = self.strategy_summary()

        if self.COMPOSITE_SCORE_COLUMN in self.trades.columns:
            summaries["Composite Score Buckets"] = (
                self.composite_score_bucket_summary()
            )

        if self.RELATIVE_STRENGTH_COLUMN in self.trades.columns:
            summaries["Relative Strength Buckets"] = (
                self.relative_strength_bucket_summary()
            )

        if self.RELATIVE_VOLUME_COLUMN in self.trades.columns:
            summaries["Relative Volume Buckets"] = self.relative_volume_bucket_summary()

        return summaries

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

    def plot_return_distribution(
        self,
        output_path: str,
        bins: list[float] | None = None,
    ):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        from scanner.config.paths import ApplicationPaths
        matplotlib_cache = ApplicationPaths.resolve().cache / "matplotlib"
        font_cache = ApplicationPaths.resolve().cache / "fonts"
        matplotlib_cache.mkdir(parents=True, exist_ok=True)
        font_cache.mkdir(parents=True, exist_ok=True)

        os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))
        os.environ.setdefault("XDG_CACHE_HOME", str(font_cache))

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        distribution = self.return_distribution(bins=bins)

        fig, ax = plt.subplots(figsize=(11, 6))
        bars = ax.bar(
            distribution["Range"],
            distribution["Trades"],
            color="#2563eb",
            edgecolor="#1f2937",
            linewidth=0.8,
        )

        ax.set_title("Return Distribution")
        ax.set_xlabel("Trade Return")
        ax.set_ylabel("Trades")
        ax.grid(axis="y", alpha=0.25)
        ax.bar_label(bars, padding=3, fontsize=8)
        plt.xticks(rotation=35, ha="right")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

    def export_ticker_summary(self, output_path: str, min_trades: int = 1):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.ticker_summary(min_trades=min_trades).to_csv(output_path, index=False)

    def export_bucket_summaries(self, output_dir: str) -> list[Path]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exports = []
        for title, summary in self.bucket_summaries().items():
            filename = f"{title.lower().replace(' ', '_')}.csv"
            output_path = output_dir / filename
            summary.to_csv(output_path, index=False)
            exports.append(output_path)

        return exports

    def generate_html_report(
        self,
        output_path: str,
        min_trades: int = 1,
        top: int = 10,
    ):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chart_path = output_path.with_name(
            f"{output_path.stem}_return_distribution.png"
        )
        self.plot_return_distribution(chart_path)

        summary = self.summary()
        report_html = self._build_html_report(
            title="Trade Analysis Report",
            summary=summary,
            chart_filename=chart_path.name,
            top_by_average_return=self.rank_tickers_by_average_return(
                min_trades=min_trades
            ).head(top),
            top_by_win_rate=self.rank_tickers_by_win_rate(min_trades=min_trades).head(
                top
            ),
            monthly_summary=self.monthly_summary(),
            weekday_summary=self.weekday_summary(),
            return_distribution=self.return_distribution(),
            bucket_summaries=self.bucket_summaries(),
        )

        output_path.write_text(report_html, encoding="utf-8")

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

    def _group_summary(
        self,
        trades: pd.DataFrame,
        group_column: str,
        sort_by_performance: bool = True,
    ) -> pd.DataFrame:
        columns = [
            group_column,
            "Trades",
            "Win Rate",
            "Average Return",
            "Median Return",
            "Best Trade",
            "Worst Trade",
            "Profit Factor",
        ]

        trades = trades.dropna(subset=[group_column])
        if trades.empty:
            return pd.DataFrame(columns=columns)

        grouped = trades.groupby(group_column, observed=True, sort=True)
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

        summary = summary.reset_index().rename(
            columns={
                "Average_Return": "Average Return",
                "Median_Return": "Median Return",
                "Best_Trade": "Best Trade",
                "Worst_Trade": "Worst Trade",
                "Win_Rate": "Win Rate",
                "Profit_Factor": "Profit Factor",
            }
        )

        if sort_by_performance:
            summary = summary.sort_values(
                by=["Average Return", "Win Rate", "Trades"],
                ascending=[False, False, False],
            )

        return summary[columns].reset_index(drop=True)

    def _numeric_bucket_summary(
        self,
        source_column: str,
        bucket_column: str,
        bins: list[float],
    ) -> pd.DataFrame:
        self._require_column(source_column)
        trades = self.trades.copy()
        labels = [
            self._format_numeric_bin_label(left, right)
            for left, right in zip(bins[:-1], bins[1:])
        ]
        trades[bucket_column] = pd.cut(
            trades[source_column],
            bins=bins,
            labels=labels,
            include_lowest=True,
            right=True,
        )
        return self._group_summary(
            trades,
            bucket_column,
            sort_by_performance=False,
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

    def _require_column(self, column: str):
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

    @staticmethod
    def _format_numeric_bin_label(left: float, right: float) -> str:
        if left == -np.inf:
            return f"<= {right:g}"
        if right == np.inf:
            return f"> {left:g}"
        return f"> {left:g} to <= {right:g}"

    def _build_html_report(
        self,
        title: str,
        summary: dict,
        chart_filename: str,
        top_by_average_return: pd.DataFrame,
        top_by_win_rate: pd.DataFrame,
        monthly_summary: pd.DataFrame,
        weekday_summary: pd.DataFrame,
        return_distribution: pd.DataFrame,
        bucket_summaries: dict[str, pd.DataFrame],
    ) -> str:
        metric_cards = "\n".join(
            f"""
            <div class="metric">
                <span>{escape(label)}</span>
                <strong>{escape(self._format_report_value(value, label))}</strong>
            </div>
            """
            for label, value in summary.items()
        )

        metric_cards += f"""
            <div class="metric">
                <span>Longest Winning Streak</span>
                <strong>{self.longest_winning_streak()}</strong>
            </div>
            <div class="metric">
                <span>Longest Losing Streak</span>
                <strong>{self.longest_losing_streak()}</strong>
            </div>
        """

        bucket_sections = "\n".join(
            f"""
        <section>
            <h2>{escape(title)}</h2>
            {self._dataframe_to_html(table)}
        </section>
            """
            for title, table in bucket_summaries.items()
        )

        return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <style>
        body {{
            background: #f8fafc;
            color: #111827;
            font-family: Arial, sans-serif;
            margin: 0;
        }}
        main {{
            margin: 0 auto;
            max-width: 1180px;
            padding: 32px 24px;
        }}
        h1, h2 {{
            margin: 0;
        }}
        h1 {{
            font-size: 32px;
            margin-bottom: 8px;
        }}
        h2 {{
            border-bottom: 1px solid #d1d5db;
            font-size: 20px;
            margin-top: 34px;
            padding-bottom: 8px;
        }}
        .subtitle {{
            color: #4b5563;
            margin: 0 0 24px;
        }}
        .metrics {{
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        }}
        .metric {{
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 14px 16px;
        }}
        .metric span {{
            color: #4b5563;
            display: block;
            font-size: 13px;
            margin-bottom: 6px;
        }}
        .metric strong {{
            font-size: 22px;
        }}
        .chart {{
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            margin-top: 16px;
            padding: 12px;
        }}
        .chart img {{
            display: block;
            height: auto;
            max-width: 100%;
        }}
        table {{
            background: #ffffff;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 14px;
            width: 100%;
        }}
        th, td {{
            border: 1px solid #d1d5db;
            padding: 8px 10px;
            text-align: right;
        }}
        th:first-child, td:first-child {{
            text-align: left;
        }}
        th {{
            background: #e5e7eb;
            color: #111827;
        }}
        tr:nth-child(even) td {{
            background: #f9fafb;
        }}
    </style>
</head>
<body>
    <main>
        <h1>{escape(title)}</h1>
        <p class="subtitle">Generated from {escape(str(self.trade_csv_path or "DataFrame"))}</p>

        <section>
            <h2>Summary</h2>
            <div class="metrics">
                {metric_cards}
            </div>
        </section>

        <section>
            <h2>Return Distribution</h2>
            <div class="chart">
                <img src="{escape(chart_filename)}" alt="Return distribution chart">
            </div>
            {self._dataframe_to_html(return_distribution)}
        </section>

        {bucket_sections}

        <section>
            <h2>Top Tickers by Average Return</h2>
            {self._dataframe_to_html(top_by_average_return)}
        </section>

        <section>
            <h2>Top Tickers by Win Rate</h2>
            {self._dataframe_to_html(top_by_win_rate)}
        </section>

        <section>
            <h2>Monthly Summary</h2>
            {self._dataframe_to_html(monthly_summary)}
        </section>

        <section>
            <h2>Weekday Summary</h2>
            {self._dataframe_to_html(weekday_summary)}
        </section>
    </main>
</body>
</html>
"""

    @staticmethod
    def _dataframe_to_html(dataframe: pd.DataFrame) -> str:
        return dataframe.to_html(
            index=False,
            border=0,
            classes="data-table",
            float_format=lambda value: f"{value:.2f}",
        )

    @staticmethod
    def _format_report_value(value, label: str) -> str:
        percent_labels = {
            "Win Rate",
            "Average Return",
            "Median Return",
            "Average Winner",
            "Average Loser",
            "Best Trade",
            "Worst Trade",
            "Expectancy",
        }

        if isinstance(value, float):
            formatted = "inf" if np.isinf(value) else f"{value:.2f}"
        else:
            formatted = str(value)

        if label in percent_labels:
            return f"{formatted}%"

        return formatted
