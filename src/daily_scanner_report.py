import argparse
from datetime import date
from pathlib import Path

from scanner.reports.daily_scanner_report import DailyScannerReport


def main():
    parser = argparse.ArgumentParser(
        description="Generate a dated daily scanner report from a watchlist CSV.",
    )
    parser.add_argument("--watchlist", default="output/watchlist.csv")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Report date in YYYY-MM-DD format.",
    )
    parser.add_argument("--output-dir", default="output/daily_reports")
    parser.add_argument(
        "--report",
        help="Optional explicit HTML report path.",
    )
    parser.add_argument(
        "--archive-watchlist",
        action="store_true",
        help="Save a dated copy of the watchlist CSV next to the report.",
    )

    args = parser.parse_args()
    report_date = date.fromisoformat(args.date)
    output_dir = Path(args.output_dir)
    report_path = (
        Path(args.report)
        if args.report
        else output_dir / f"daily_scanner_report_{report_date.isoformat()}.html"
    )

    report = DailyScannerReport(
        watchlist_path=args.watchlist,
        report_date=report_date,
    )
    report.generate_html_report(report_path)

    print(f"Generated daily scanner report at {report_path}")

    if args.archive_watchlist:
        archive_path = report.archive_watchlist(output_dir)
        print(f"Archived watchlist at {archive_path}")


if __name__ == "__main__":
    main()
