import argparse
from math import isinf

import pandas as pd

from scanner.analysis.trade_analyzer import TradeAnalyzer
from scanner.data.ownership import owned_application


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


@owned_application
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
    parser.add_argument(
        "--buckets",
        action="store_true",
        help=(
            "Display strategy, composite score, relative strength, and relative "
            "volume bucket summaries when those columns are present."
        ),
    )
    parser.add_argument(
        "--plot-return-distribution",
        help="Path to save a return distribution chart as a PNG.",
    )
    parser.add_argument(
        "--html-report",
        help="Path to save a full HTML analysis report.",
    )
    parser.add_argument(
        "--export-bucket-summaries",
        help="Directory to export available analyzer bucket summaries as CSV files.",
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

    if args.buckets:
        bucket_summaries = analyzer.bucket_summaries()
        if not bucket_summaries:
            print()
            print("No analyzer bucket columns found.")
        for title, table in bucket_summaries.items():
            print_table(title, table)

    if args.plot_return_distribution:
        analyzer.plot_return_distribution(args.plot_return_distribution)
        print()
        print(f"Saved return distribution plot to {args.plot_return_distribution}")

    if args.html_report:
        analyzer.generate_html_report(
            args.html_report,
            min_trades=args.min_trades,
            top=args.top,
        )
        print()
        print(f"Generated HTML analysis report at {args.html_report}")

    if args.export_ticker_summary:
        analyzer.export_ticker_summary(
            args.export_ticker_summary,
            min_trades=args.min_trades,
        )
        print()
        print(f"Exported ticker summary to {args.export_ticker_summary}")

    if args.export_bucket_summaries:
        exports = analyzer.export_bucket_summaries(args.export_bucket_summaries)
        print()
        if not exports:
            print("No analyzer bucket columns found; no bucket summaries exported.")
        for output_path in exports:
            print(f"Exported bucket summary to {output_path}")


if __name__ == "__main__":
    main()
