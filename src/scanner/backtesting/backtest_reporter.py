class BacktestReporter:

    def print_result(self, result, hold_days: int):
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

    def print_hold_day_comparison(self, results_by_hold_days):
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

    def print_best_hold_period(self, best):
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