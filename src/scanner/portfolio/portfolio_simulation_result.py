from dataclasses import dataclass
from html import escape
from pathlib import Path
import os

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

    def summary(self) -> dict:
        return {
            "Initial Cash": self.initial_cash,
            "Final Cash": self.final_cash,
            "Final Equity": self.final_equity,
            "Total Return": self.total_return_percent,
            "Max Drawdown": self.max_drawdown_percent,
            "CAGR": self.cagr_percent,
            "Sharpe Ratio": self.sharpe_ratio,
            "Positions": len(self.positions),
            "Skipped Trades": self.skipped_trades,
        }

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

    def export_equity_curve(self, output_path: str):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.equity_curve.to_csv(output_path, index=False)

    def export_positions(self, output_path: str):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.positions_dataframe().to_csv(output_path, index=False)

    def plot_equity_curve(self, output_path: str):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        matplotlib_cache = output_path.parent / ".matplotlib-cache"
        font_cache = output_path.parent / ".cache"
        matplotlib_cache.mkdir(parents=True, exist_ok=True)
        font_cache.mkdir(parents=True, exist_ok=True)

        os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))
        os.environ.setdefault("XDG_CACHE_HOME", str(font_cache))

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(11, 6))

        if not self.equity_curve.empty:
            ax.plot(
                self.equity_curve["Date"],
                self.equity_curve["Equity"],
                color="#2563eb",
                linewidth=2,
            )

        ax.set_title("Portfolio Equity Curve")
        ax.set_xlabel("Date")
        ax.set_ylabel("Equity")
        ax.grid(alpha=0.25)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

    def generate_html_report(self, output_path: str):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chart_path = output_path.with_name(f"{output_path.stem}_equity_curve.png")
        self.plot_equity_curve(chart_path)

        output_path.write_text(
            self._build_html_report(chart_filename=chart_path.name),
            encoding="utf-8",
        )

    def _build_html_report(self, chart_filename: str) -> str:
        metric_cards = "\n".join(
            f"""
            <div class="metric">
                <span>{escape(label)}</span>
                <strong>{escape(self._format_report_value(value, label))}</strong>
            </div>
            """
            for label, value in self.summary().items()
        )

        return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Portfolio Simulation Report</title>
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
            margin-bottom: 24px;
        }}
        h2 {{
            border-bottom: 1px solid #d1d5db;
            font-size: 20px;
            margin-top: 34px;
            padding-bottom: 8px;
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
        }}
        tr:nth-child(even) td {{
            background: #f9fafb;
        }}
    </style>
</head>
<body>
    <main>
        <h1>Portfolio Simulation Report</h1>
        <section>
            <h2>Summary</h2>
            <div class="metrics">
                {metric_cards}
            </div>
        </section>
        <section>
            <h2>Equity Curve</h2>
            <div class="chart">
                <img src="{escape(chart_filename)}" alt="Portfolio equity curve">
            </div>
        </section>
        <section>
            <h2>Equity Curve Data</h2>
            {self._dataframe_to_html(self.equity_curve)}
        </section>
        <section>
            <h2>Positions</h2>
            {self._dataframe_to_html(self.positions_dataframe())}
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
        percent_labels = {"Total Return", "Max Drawdown", "CAGR"}

        if isinstance(value, float):
            formatted = f"{value:.2f}"
        else:
            formatted = str(value)

        if label in percent_labels:
            return f"{formatted}%"

        return formatted
