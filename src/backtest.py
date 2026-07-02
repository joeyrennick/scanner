import argparse

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--strategy", default="pullback")
    parser.add_argument("--hold-days", type=int, default=5)

    args = parser.parse_args()

    if args.strategy != "pullback":
        raise ValueError("Only pullback strategy is supported for now")

    history = prepare_history(args.ticker)
    benchmark = prepare_history("SPY")

    relative_strength = calculate_relative_strength(history, benchmark)

    result = Backtester().run(
        ticker=args.ticker.upper(),
        history=history,
        strategy=PullbackStrategy(),
        relative_strength=relative_strength,
        hold_days=args.hold_days,
    )

    stats = result.statistics

    print("=" * 50)
    print("Backtest Results")
    print("=" * 50)
    print(f"Ticker: {result.ticker}")
    print(f"Strategy: {result.strategy_name}")
    print(f"Hold Days: {args.hold_days}")
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


if __name__ == "__main__":
    main()