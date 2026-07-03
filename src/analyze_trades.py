import argparse
from math import isinf

import pandas as pd

from scanner.analysis.trade_analyzer import TradeAnalyzer


def format_value(value):
    if isinstance(value, float):
        if isinf(value):
            return "inf"
        return f"{value:.2f}"
    return value


def print_summary(summary: dict):
    print("=" * 50)
    print("Trade Analysis Summary")
    print("=" * 50)

    for label, value in summary.items():
        suffix = "%" if label in {
            "Win Rate",
            "Average Return",
            "Median Return",
            "Average Winner",
            "Average Loser",
            "Best Trade",
            "Worst Trade",
            "Expectancy",
        } else ""
        print(f"{label}: {format_value(value)}{suffix}")


def print_table(title: str, table: pd.DataFrame, rows: int | None = None):
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)

    if rows:
        table = table.head(rows)

    if table.empty:
        print("No rows")
        return

    print(table.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(
        description="Analyze exported swing scanner backtest trades.",
    )
    parser.add_argument("trade_csv", help="Path to a trade CSV exported by backtest.py")
    parser.add_argument(
        "--min-trades",
        type=int,
        default=1,
        help="Minimum trades required for ticker rankings.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of ranked tickers to display.",
    )
    parser.add_argument(
        "--export-ticker-summary",
        help="Path to export ticker-level summary statistics as CSV.",
    )
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="Display monthly performance summary.",
    )
    parser.add_argument(
        "--weekday",
        action="store_true",
        help="Display entry weekday performance summary.",
    )
    parser.add_argument(
        "--distribution",
        action="store_true",
        help="Display return distribution buckets.",
    )

    args = parser.parse_args()

    analyzer = TradeAnalyzer(args.trade_csv)

    print_summary(analyzer.summary())
    print()
    print(f"Longest Winning Streak: {analyzer.longest_winning_streak()}")
    print(f"Longest Losing Streak: {analyzer.longest_losing_streak()}")

    print_table(
        "Top Tickers by Average Return",
        analyzer.rank_tickers_by_average_return(min_trades=args.min_trades),
        rows=args.top,
    )
    print_table(
        "Top Tickers by Win Rate",
        analyzer.rank_tickers_by_win_rate(min_trades=args.min_trades),
        rows=args.top,
    )

    if args.monthly:
        print_table("Monthly Summary", analyzer.monthly_summary())

    if args.weekday:
        print_table("Weekday Summary", analyzer.weekday_summary())

    if args.distribution:
        print_table("Return Distribution", analyzer.return_distribution())

    if args.export_ticker_summary:
        analyzer.export_ticker_summary(
            args.export_ticker_summary,
            min_trades=args.min_trades,
        )
        print()
        print(f"Exported ticker summary to {args.export_ticker_summary}")


if __name__ == "__main__":
    main()
