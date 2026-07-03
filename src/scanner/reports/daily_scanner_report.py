from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class DailyScannerReport:
    watchlist_path: str
    report_date: date
    portfolio_equity_curve_path: str | None = None
    portfolio_report_path: str | None = None
    account_size: float | None = None
    risk_per_trade_percent: float | None = None
    suggested_hold_days: int = 5
    reward_risk_multiple: float = 2.0

    def __post_init__(self):
        self.watchlist_path = Path(self.watchlist_path)
        self.watchlist = pd.read_csv(self.watchlist_path)
        self.portfolio_equity_curve = None

        if self.portfolio_equity_curve_path:
            self.portfolio_equity_curve_path = Path(self.portfolio_equity_curve_path)
            self.portfolio_equity_curve = pd.read_csv(self.portfolio_equity_curve_path)

            if "Date" in self.portfolio_equity_curve.columns:
                self.portfolio_equity_curve["Date"] = pd.to_datetime(
                    self.portfolio_equity_curve["Date"]
                )

        if "Ticker" not in self.watchlist.columns:
            raise ValueError("Watchlist CSV is missing required column: Ticker")

        if self.account_size is not None and self.account_size <= 0:
            raise ValueError("account_size must be greater than zero")

        if self.risk_per_trade_percent is not None and self.risk_per_trade_percent <= 0:
            raise ValueError("risk_per_trade_percent must be greater than zero")

        if self.suggested_hold_days <= 0:
            raise ValueError("suggested_hold_days must be greater than zero")

        if self.reward_risk_multiple <= 0:
            raise ValueError("reward_risk_multiple must be greater than zero")

    def summary(self) -> dict:
        summary = {
            "Report Date": self.report_date.isoformat(),
            "Candidates": len(self.watchlist),
        }

        if "Composite Score" in self.watchlist.columns and not self.watchlist.empty:
            summary["Average Composite Score"] = self.watchlist["Composite Score"].mean()
            summary["Highest Composite Score"] = self.watchlist["Composite Score"].max()

        if "Triggered Strategies" in self.watchlist.columns:
            for strategy in self._triggered_strategy_counts().items():
                name, count = strategy
                summary[f"{name} Candidates"] = count

        return summary

    def portfolio_summary(self) -> dict:
        if self.portfolio_equity_curve is None or self.portfolio_equity_curve.empty:
            return {}

        required_columns = {"Date", "Equity"}
        missing_columns = required_columns - set(self.portfolio_equity_curve.columns)

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Portfolio equity curve is missing required columns: {missing}")

        equity = self.portfolio_equity_curve["Equity"]
        initial_equity = equity.iloc[0]
        final_equity = equity.iloc[-1]
        running_high = equity.cummax()
        drawdown = ((equity - running_high) / running_high * 100).min()
        returns = equity.pct_change().dropna()
        sharpe_ratio = 0.0

        if len(returns) > 1 and returns.std(ddof=1) != 0:
            sharpe_ratio = returns.mean() / returns.std(ddof=1) * np.sqrt(252)

        start_date = self.portfolio_equity_curve.iloc[0]["Date"]
        end_date = self.portfolio_equity_curve.iloc[-1]["Date"]
        years = (end_date - start_date).days / 365.25
        cagr = 0.0

        if years > 0 and final_equity > 0:
            cagr = ((final_equity / initial_equity) ** (1 / years) - 1) * 100

        summary = {
            "Initial Equity": initial_equity,
            "Final Equity": final_equity,
            "Total Return": ((final_equity - initial_equity) / initial_equity) * 100,
            "Max Drawdown": drawdown,
            "CAGR": cagr,
            "Sharpe Ratio": sharpe_ratio,
        }

        if "Open Positions" in self.portfolio_equity_curve.columns:
            summary["Current Open Positions"] = self.portfolio_equity_curve.iloc[-1][
                "Open Positions"
            ]

        return summary

    def archive_watchlist(self, output_dir: str) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_path = output_dir / f"watchlist_{self.report_date.isoformat()}.csv"
        self.watchlist.to_csv(archive_path, index=False)
        return archive_path

    def generate_html_report(self, output_path: str):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self._build_html_report(output_path=output_path),
            encoding="utf-8",
        )

    def _triggered_strategy_counts(self) -> dict[str, int]:
        counts = {}

        for strategies in self.watchlist["Triggered Strategies"].dropna():
            for strategy in str(strategies).split(","):
                strategy = strategy.strip()

                if not strategy or strategy == "None":
                    continue

                counts[strategy] = counts.get(strategy, 0) + 1

        return counts

    def _report_columns(self) -> list[str]:
        preferred_columns = [
            "Ticker",
            "Triggered Strategies",
            "Composite Score",
            "Technical Score",
            "Strategy Score",
            "Price",
            "Stop 2ATR",
            "ATR14",
            "Relative Strength",
            "Relative Volume",
        ]
        failed_check_columns = [
            column for column in self.watchlist.columns if column.endswith(": Failed Checks")
        ]
        columns = [
            column for column in preferred_columns if column in self.watchlist.columns
        ]
        columns.extend(failed_check_columns)
        return columns or list(self.watchlist.columns)

    def _report_table(self) -> pd.DataFrame:
        report = self.watchlist[self._report_columns()].copy()

        if "Composite Score" in report.columns:
            report = report.sort_values(by="Composite Score", ascending=False)

        return report

    def manual_trade_checklist(self) -> pd.DataFrame:
        required_columns = {"Ticker", "Price", "Stop 2ATR"}
        missing_columns = required_columns - set(self.watchlist.columns)

        if missing_columns:
            return pd.DataFrame()

        checklist = pd.DataFrame()
        checklist["Ticker"] = self.watchlist["Ticker"]

        if "Triggered Strategies" in self.watchlist.columns:
            checklist["Triggered Strategy"] = self.watchlist["Triggered Strategies"]

        checklist["Entry Area"] = self.watchlist["Price"]
        checklist["Suggested Stop"] = self.watchlist["Stop 2ATR"]
        checklist["Risk / Share"] = checklist["Entry Area"] - checklist["Suggested Stop"]
        checklist["Suggested Exit"] = (
            checklist["Entry Area"]
            + (checklist["Risk / Share"] * self.reward_risk_multiple)
        )
        checklist["Reward/Risk"] = self.reward_risk_multiple
        checklist["Suggested Hold Time"] = (
            f"{self.suggested_hold_days} trading days"
        )
        checklist["Risk Budget"] = self._risk_budget()
        checklist["Position Size Estimate"] = checklist["Risk / Share"].apply(
            self._position_size_for_risk
        )
        checklist["Estimated Position Value"] = (
            checklist["Position Size Estimate"] * checklist["Entry Area"]
        )
        checklist["Notes"] = ""

        if "Composite Score" in self.watchlist.columns:
            checklist["Composite Score"] = self.watchlist["Composite Score"]
            checklist = checklist.sort_values(by="Composite Score", ascending=False)

        return checklist

    def _build_html_report(self, output_path: Path) -> str:
        metric_cards = "\n".join(
            f"""
            <div class="metric">
                <span>{escape(label)}</span>
                <strong>{escape(self._format_metric(value))}</strong>
            </div>
            """
            for label, value in self.summary().items()
        )

        return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Daily Scanner Report - {escape(self.report_date.isoformat())}</title>
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
        th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{
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
        <h1>Daily Scanner Report</h1>
        <p class="subtitle">Generated from {escape(str(self.watchlist_path))}</p>
        <section>
            <h2>Summary</h2>
            <div class="metrics">
                {metric_cards}
            </div>
        </section>
        <section>
            <h2>Watchlist Candidates</h2>
            {self._dataframe_to_html(self._report_table())}
        </section>
        {self._manual_trade_checklist_section()}
        {self._portfolio_context_section(output_path)}
    </main>
</body>
</html>
"""

    def _portfolio_context_section(self, output_path: Path) -> str:
        portfolio_summary = self.portfolio_summary()

        if not portfolio_summary and not self.portfolio_report_path:
            return ""

        metric_cards = "\n".join(
            f"""
            <div class="metric">
                <span>{escape(label)}</span>
                <strong>{escape(self._format_metric(value))}</strong>
            </div>
            """
            for label, value in portfolio_summary.items()
        )
        detailed_report = ""

        if self.portfolio_report_path:
            portfolio_report_href = self._relative_path(
                target_path=Path(self.portfolio_report_path),
                base_path=output_path.parent,
            )
            detailed_report = (
                f'<p class="subtitle"><a href="{escape(portfolio_report_href)}">'
                "Open detailed portfolio report</a></p>"
            )

        return f"""
        <section>
            <h2>Portfolio/Risk Context</h2>
            {detailed_report}
            <div class="metrics">
                {metric_cards}
            </div>
        </section>
        """

    def _manual_trade_checklist_section(self) -> str:
        checklist = self.manual_trade_checklist()

        if checklist.empty:
            return ""

        return f"""
        <section>
            <h2>Manual Trade Checklist</h2>
            {self._dataframe_to_html(checklist)}
        </section>
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
    def _format_metric(value) -> str:
        if isinstance(value, float):
            return f"{value:.2f}"

        return str(value)

    def _risk_budget(self) -> float | None:
        if self.account_size is None or self.risk_per_trade_percent is None:
            return None

        return self.account_size * (self.risk_per_trade_percent / 100)

    def _position_size_for_risk(self, risk_per_share: float) -> int | None:
        risk_budget = self._risk_budget()

        if risk_budget is None or risk_per_share <= 0:
            return None

        return int(risk_budget // risk_per_share)

    @staticmethod
    def _relative_path(target_path: Path, base_path: Path) -> str:
        try:
            return str(target_path.resolve().relative_to(base_path.resolve()))
        except ValueError:
            import os

            return os.path.relpath(target_path, start=base_path)
