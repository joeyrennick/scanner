import argparse
from datetime import date

from scanner.journal.trade_journal import TradeJournal


def print_summary(summary: dict):
    print("=" * 50)
    print("Manual Trade Journal Summary")
    print("=" * 50)

    for label, value in summary.items():
        suffix = "%" if label in {"Win Rate", "Average Return", "Best Trade", "Worst Trade"} else ""
        print(f"{label}: {format_value(value)}{suffix}")


def format_value(value):
    if isinstance(value, float):
        return f"{value:.2f}"

    return value


def main():
    parser = argparse.ArgumentParser(description="Track manually executed trades.")
    parser.add_argument("--journal", default="output/trade_journal.csv")

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--ticker", required=True)
    add_parser.add_argument("--entry-date", required=True)
    add_parser.add_argument("--entry-price", type=float, required=True)
    add_parser.add_argument("--shares", type=int, required=True)
    add_parser.add_argument("--strategy", default="")
    add_parser.add_argument("--suggested-stop", type=float)
    add_parser.add_argument("--suggested-exit", type=float)
    add_parser.add_argument("--notes", default="")

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--trade-id", required=True)
    close_parser.add_argument("--exit-date", required=True)
    close_parser.add_argument("--exit-price", type=float, required=True)
    close_parser.add_argument("--exit-notes", default="")

    subparsers.add_parser("list")
    subparsers.add_parser("summary")

    report_parser = subparsers.add_parser("html-report")
    report_parser.add_argument("--output", default="output/trade_journal_report.html")

    args = parser.parse_args()
    journal = TradeJournal(args.journal)

    if args.command == "add":
        trade_id = journal.add_trade(
            ticker=args.ticker,
            entry_date=date.fromisoformat(args.entry_date),
            entry_price=args.entry_price,
            shares=args.shares,
            strategy=args.strategy,
            suggested_stop=args.suggested_stop,
            suggested_exit=args.suggested_exit,
            notes=args.notes,
        )
        print(f"Added trade {trade_id}")

    elif args.command == "close":
        journal.close_trade(
            trade_id=args.trade_id,
            exit_date=date.fromisoformat(args.exit_date),
            exit_price=args.exit_price,
            exit_notes=args.exit_notes,
        )
        print(f"Closed trade {args.trade_id}")

    elif args.command == "list":
        print(journal.review_dataframe().to_string(index=False))

    elif args.command == "summary":
        print_summary(journal.summary())

    elif args.command == "html-report":
        journal.generate_html_report(args.output)
        print(f"Generated trade journal report at {args.output}")


if __name__ == "__main__":
    main()
