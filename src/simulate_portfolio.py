import argparse
from math import isinf

from scanner.portfolio.execution_model import ExecutionModel
from scanner.portfolio.portfolio_simulator import PortfolioSimulator
from scanner.portfolio.trade_csv_loader import load_trades_from_csv


def format_value(value):
    if isinstance(value, float):
        if isinf(value):
            return "inf"
        return f"{value:.2f}"
    return value


def print_summary(summary: dict):
    print("=" * 50)
    print("Portfolio Simulation Summary")
    print("=" * 50)

    for label, value in summary.items():
        suffix = "%" if label in {"Total Return", "Max Drawdown", "CAGR"} else ""
        print(f"{label}: {format_value(value)}{suffix}")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate portfolio performance from exported backtest trades.",
    )
    parser.add_argument("trade_csv", help="Path to a trade CSV exported by backtest.py")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--max-open-positions", type=int, default=10)
    parser.add_argument("--max-positions-per-ticker", type=int)
    parser.add_argument(
        "--position-size-percent",
        type=float,
        default=0.10,
        help="Fraction of portfolio equity to allocate per position, such as 0.10.",
    )
    parser.add_argument("--commission-per-trade", type=float, default=0.0)
    parser.add_argument("--commission-per-share", type=float, default=0.0)
    parser.add_argument("--slippage-percent", type=float, default=0.0)
    parser.add_argument(
        "--limit-entry-offset-percent",
        type=float,
        help="Buy limit offset below entry price. Without --assume-limit-fills, lower limits are skipped.",
    )
    parser.add_argument(
        "--assume-limit-fills",
        action="store_true",
        help="Assume limit orders fill at the limit price when using --limit-entry-offset-percent.",
    )
    parser.add_argument("--stop-loss-percent", type=float)
    parser.add_argument("--trailing-stop-percent", type=float)
    parser.add_argument("--export-equity-curve")
    parser.add_argument("--export-positions")
    parser.add_argument("--plot-equity-curve")
    parser.add_argument("--html-report")

    args = parser.parse_args()

    trades = load_trades_from_csv(args.trade_csv)
    execution_model = ExecutionModel(
        commission_per_trade=args.commission_per_trade,
        commission_per_share=args.commission_per_share,
        slippage_percent=args.slippage_percent,
        limit_entry_offset_percent=args.limit_entry_offset_percent,
        assume_limit_fills=args.assume_limit_fills,
        stop_loss_percent=args.stop_loss_percent,
        trailing_stop_percent=args.trailing_stop_percent,
    )
    simulator = PortfolioSimulator(
        initial_cash=args.initial_cash,
        max_open_positions=args.max_open_positions,
        position_size_percent=args.position_size_percent,
        execution_model=execution_model,
        max_positions_per_ticker=args.max_positions_per_ticker,
    )
    result = simulator.run(trades)

    print_summary(result.summary())

    if args.export_equity_curve:
        result.export_equity_curve(args.export_equity_curve)
        print()
        print(f"Exported equity curve to {args.export_equity_curve}")

    if args.export_positions:
        result.export_positions(args.export_positions)
        print()
        print(f"Exported positions to {args.export_positions}")

    if args.plot_equity_curve:
        result.plot_equity_curve(args.plot_equity_curve)
        print()
        print(f"Saved equity curve plot to {args.plot_equity_curve}")

    if args.html_report:
        result.generate_html_report(args.html_report)
        print()
        print(f"Generated portfolio HTML report at {args.html_report}")


if __name__ == "__main__":
    main()
