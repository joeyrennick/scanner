from datetime import date
from html import escape
from pathlib import Path
from uuid import uuid4

import pandas as pd
from scanner.config.paths import ApplicationPaths
from scanner.data.ownership import acquire_database


class TradeJournal:
    COLUMNS = [
        "Trade ID",
        "Ticker",
        "Strategy",
        "Entry Date",
        "Entry Price",
        "Shares",
        "Suggested Stop",
        "Suggested Exit",
        "Exit Date",
        "Exit Price",
        "Status",
        "Notes",
        "Exit Notes",
    ]

    def __init__(self, journal_path: str | None = None):
        self.journal_path = Path(journal_path) if journal_path else ApplicationPaths.resolve().journal
        self._ownership = acquire_database(self.journal_path)
        self.trades = self._load_trades()

    def add_trade(
        self,
        ticker: str,
        entry_date: date,
        entry_price: float,
        shares: int,
        strategy: str = "",
        suggested_stop: float | None = None,
        suggested_exit: float | None = None,
        notes: str = "",
    ) -> str:
        if entry_price <= 0:
            raise ValueError("entry_price must be greater than zero")
        if shares <= 0:
            raise ValueError("shares must be greater than zero")

        trade_id = self._new_trade_id()
        trade = {
            "Trade ID": trade_id,
            "Ticker": ticker.upper(),
            "Strategy": strategy,
            "Entry Date": entry_date.isoformat(),
            "Entry Price": entry_price,
            "Shares": shares,
            "Suggested Stop": suggested_stop,
            "Suggested Exit": suggested_exit,
            "Exit Date": "",
            "Exit Price": "",
            "Status": "OPEN",
            "Notes": notes,
            "Exit Notes": "",
        }

        self.trades = pd.concat(
            [self.trades, pd.DataFrame([trade], columns=self.COLUMNS)],
            ignore_index=True,
        )
        self.save()
        return trade_id

    def close_trade(
        self,
        trade_id: str,
        exit_date: date,
        exit_price: float,
        exit_notes: str = "",
    ):
        if exit_price <= 0:
            raise ValueError("exit_price must be greater than zero")

        matches = self.trades["Trade ID"] == trade_id

        if not matches.any():
            raise ValueError(f"Trade ID not found: {trade_id}")

        index = self.trades[matches].index[0]

        if self.trades.at[index, "Status"] == "CLOSED":
            raise ValueError(f"Trade ID is already closed: {trade_id}")

        self.trades.at[index, "Exit Date"] = exit_date.isoformat()
        self.trades.at[index, "Exit Price"] = str(exit_price)
        self.trades.at[index, "Status"] = "CLOSED"
        self.trades.at[index, "Exit Notes"] = exit_notes
        self.save()

    def review_dataframe(self) -> pd.DataFrame:
        trades = self.trades.copy()

        if trades.empty:
            return pd.DataFrame(columns=self.COLUMNS + self._metric_columns())

        trades["Entry Price"] = pd.to_numeric(trades["Entry Price"], errors="coerce")
        trades["Exit Price"] = pd.to_numeric(trades["Exit Price"], errors="coerce")
        trades["Shares"] = pd.to_numeric(trades["Shares"], errors="coerce")
        trades["Entry Value"] = trades["Entry Price"] * trades["Shares"]
        trades["Exit Value"] = trades["Exit Price"] * trades["Shares"]
        trades["Profit/Loss"] = trades["Exit Value"] - trades["Entry Value"]
        trades["Return %"] = trades["Profit/Loss"] / trades["Entry Value"] * 100

        entry_dates = pd.to_datetime(trades["Entry Date"], errors="coerce")
        exit_dates = pd.to_datetime(trades["Exit Date"], errors="coerce")
        trades["Holding Days"] = (exit_dates - entry_dates).dt.days

        return trades

    def summary(self) -> dict:
        reviewed = self.review_dataframe()
        closed = reviewed[reviewed["Status"] == "CLOSED"]

        if closed.empty:
            return {
                "Total Trades": len(reviewed),
                "Open Trades": len(reviewed[reviewed["Status"] == "OPEN"]),
                "Closed Trades": 0,
                "Win Rate": 0.0,
                "Total Profit/Loss": 0.0,
                "Average Return": 0.0,
                "Best Trade": 0.0,
                "Worst Trade": 0.0,
            }

        winners = closed[closed["Profit/Loss"] > 0]

        return {
            "Total Trades": len(reviewed),
            "Open Trades": len(reviewed[reviewed["Status"] == "OPEN"]),
            "Closed Trades": len(closed),
            "Win Rate": len(winners) / len(closed) * 100,
            "Total Profit/Loss": closed["Profit/Loss"].sum(),
            "Average Return": closed["Return %"].mean(),
            "Best Trade": closed["Return %"].max(),
            "Worst Trade": closed["Return %"].min(),
        }

    def generate_html_report(self, output_path: str):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._build_html_report(), encoding="utf-8")

    def save(self):
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.trades.to_csv(self.journal_path, index=False)

    def _load_trades(self) -> pd.DataFrame:
        if not self.journal_path.exists():
            return pd.DataFrame(columns=self.COLUMNS)

        trades = pd.read_csv(self.journal_path, dtype=str).fillna("")

        for column in self.COLUMNS:
            if column not in trades.columns:
                trades[column] = ""

        return trades[self.COLUMNS]

    def _new_trade_id(self) -> str:
        return uuid4().hex[:8].upper()

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
    <title>Manual Trade Journal</title>
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
        <h1>Manual Trade Journal</h1>
        <section>
            <h2>Summary</h2>
            <div class="metrics">
                {metric_cards}
            </div>
        </section>
        <section>
            <h2>Trades</h2>
            {self._dataframe_to_html(self.review_dataframe())}
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

    @staticmethod
    def _metric_columns() -> list[str]:
        return [
            "Entry Value",
            "Exit Value",
            "Profit/Loss",
            "Return %",
            "Holding Days",
        ]
