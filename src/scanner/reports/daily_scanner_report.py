from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd


@dataclass
class DailyScannerReport:
    watchlist_path: str
    report_date: date

    def __post_init__(self):
        self.watchlist_path = Path(self.watchlist_path)
        self.watchlist = pd.read_csv(self.watchlist_path)

        if "Ticker" not in self.watchlist.columns:
            raise ValueError("Watchlist CSV is missing required column: Ticker")

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

    def archive_watchlist(self, output_dir: str) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_path = output_dir / f"watchlist_{self.report_date.isoformat()}.csv"
        self.watchlist.to_csv(archive_path, index=False)
        return archive_path

    def generate_html_report(self, output_path: str):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._build_html_report(), encoding="utf-8")

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

    def _build_html_report(self) -> str:
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
    def _format_metric(value) -> str:
        if isinstance(value, float):
            return f"{value:.2f}"

        return str(value)
