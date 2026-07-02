import argparse

from scanner.backtesting.backtest_optimizer import BacktestOptimizer
from scanner.backtesting.backtest_reporter import BacktestReporter
from scanner.backtesting.backtester import Backtester
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.services.market_data_service import MarketDataService
from scanner.strategies.pullback_strategy import PullbackStrategy


def get_strategy(strategy_name: str):
    if strategy_name == "pullback":
        return PullbackStrategy()

    raise ValueError(f"Unsupported strategy: {strategy_name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--strategy", default="pullback")
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--compare-hold-days", nargs="+", type=int)
    parser.add_argument("--optimize-hold-days", action="store_true")

    args = parser.parse_args()

    market_data_service = MarketDataService()

    history = market_data_service.get_history(args.ticker, period="5y")
    benchmark = market_data_service.get_history("SPY", period="5y")

    relative_strength = calculate_relative_strength(history, benchmark)
    strategy = get_strategy(args.strategy)
    reporter = BacktestReporter()

    if args.optimize_hold_days:
        results_by_hold_days, best = BacktestOptimizer().optimize_hold_days(
            ticker=args.ticker.upper(),
            history=history,
            strategy=strategy,
            relative_strength=relative_strength,
            min_hold_days=1,
            max_hold_days=30,
        )

        reporter.print_hold_day_comparison(results_by_hold_days)
        reporter.print_best_hold_period(best)

    elif args.compare_hold_days:
        results_by_hold_days = []

        for hold_days in args.compare_hold_days:
            result = Backtester().run(
                ticker=args.ticker.upper(),
                history=history,
                strategy=strategy,
                relative_strength=relative_strength,
                hold_days=hold_days,
            )

            results_by_hold_days.append((hold_days, result))

        reporter.print_hold_day_comparison(results_by_hold_days)

    else:
        result = Backtester().run(
            ticker=args.ticker.upper(),
            history=history,
            strategy=strategy,
            relative_strength=relative_strength,
            hold_days=args.hold_days,
        )

        reporter.print_result(result, args.hold_days)


if __name__ == "__main__":
    main()