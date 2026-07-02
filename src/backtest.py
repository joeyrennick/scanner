import argparse

from scanner.backtesting.backtest_optimizer import BacktestOptimizer
from scanner.backtesting.backtester import Backtester
from scanner.data.market_data import download_price_data
from scanner.indicators.atr import add_atr
from scanner.indicators.moving_averages import add_moving_averages
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.indicators.volume import add_volume_indicators
from scanner.strategies.pullback_strategy import PullbackStrategy


def prepare_history(ticker: str):
    data = download_price_data(ticker, period="5y")
    data = add_moving_averages(data)
    data = add_atr(data)
    data = add_volume_indicators(data)
    return data


def get_strategy(strategy_name: str):
    if strategy_name == "pullback":
        return PullbackStrategy()

    raise ValueError(f"Unsupported strategy: {strategy_name}")


def print_result(result, hold_days: int):
    stats = result.statistics

    print("=" * 50)
    print("Backtest Results")
    print("=" * 50)
    print(f"Ticker: {result.ticker}")
    print(f"Strategy: {result.strategy_name}")
    print(f"Hold Days: {hold_days}")
    print("-" * 50)
    print(f"Trades: {stats.total_trades}")
    print(f"Win Rate: {stats.win_rate:.2f}%")
    print(f"Average Return: {stats.average_return:.2f}%")
    print(f"Average Win: {stats.average_win:.2f}%")
    print(f"Average Loss: {stats.average_loss:.2f}%")
    print(f"Best Trade: {stats.best_trade_return:.2f}%")
    print(f"Worst Trade: {stats.worst_trade_return:.2f}%")
    print(f"Expectancy: {stats.expectancy:.2f}%")
    print("=" * 50)


def print_hold_day_comparison(results_by_hold_days):
    print("=" * 90)
    print("Hold Days Comparison")
    print("=" * 90)

    print(
        f"{'Hold Days':<12}"
        f"{'Trades':<10}"
        f"{'Win Rate':<12}"
        f"{'Avg Return':<14}"
        f"{'Expectancy':<14}"
        f"{'Best':<12}"
        f"{'Worst':<12}"
    )

    print("-" * 90)

    for hold_days, result in results_by_hold_days:
        stats = result.statistics

        win_rate = f"{stats.win_rate:.2f}%"
        avg_return = f"{stats.average_return:.2f}%"
        expectancy = f"{stats.expectancy:.2f}%"
        best = f"{stats.best_trade_return:.2f}%"
        worst = f"{stats.worst_trade_return:.2f}%"

        print(
            f"{hold_days:<12}"
            f"{stats.total_trades:<10}"
            f"{win_rate:<12}"
            f"{avg_return:<14}"
            f"{expectancy:<14}"
            f"{best:<12}"
            f"{worst:<12}"
        )

    print("=" * 90)


def print_best_hold_period(best):
    hold_days, result = best
    stats = result.statistics

    print()
    print("=" * 50)
    print("Best Hold Period")
    print("=" * 50)
    print(f"Hold Days: {hold_days}")
    print(f"Trades: {stats.total_trades}")
    print(f"Win Rate: {stats.win_rate:.2f}%")
    print(f"Average Return: {stats.average_return:.2f}%")
    print(f"Expectancy: {stats.expectancy:.2f}%")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--strategy", default="pullback")
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--compare-hold-days", nargs="+", type=int)
    parser.add_argument("--optimize-hold-days", action="store_true")

    args = parser.parse_args()

    history = prepare_history(args.ticker)
    benchmark = prepare_history("SPY")

    relative_strength = calculate_relative_strength(history, benchmark)
    strategy = get_strategy(args.strategy)

    if args.optimize_hold_days:
        results_by_hold_days, best = BacktestOptimizer().optimize_hold_days(
            ticker=args.ticker.upper(),
            history=history,
            strategy=strategy,
            relative_strength=relative_strength,
            min_hold_days=1,
            max_hold_days=30,
        )

        print_hold_day_comparison(results_by_hold_days)
        print_best_hold_period(best)

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

        print_hold_day_comparison(results_by_hold_days)

    else:
        result = Backtester().run(
            ticker=args.ticker.upper(),
            history=history,
            strategy=strategy,
            relative_strength=relative_strength,
            hold_days=args.hold_days,
        )

        print_result(result, args.hold_days)


if __name__ == "__main__":
    main()