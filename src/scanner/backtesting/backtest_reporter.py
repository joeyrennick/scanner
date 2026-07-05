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

    def print_parameter_sweep(self, results, top: int = 10):
        print("=" * 132)
        print("Parameter Sweep Results")
        print("=" * 132)

        if not results:
            print("No sweep results matched the minimum trade count.")
            print("=" * 132)
            return

        print(
            f"{'Rank':<6}"
            f"{'Hold':<7}"
            f"{'MinHist':<9}"
            f"{'Overlap':<10}"
            f"{'Trades':<9}"
            f"{'Win Rate':<11}"
            f"{'Avg Ret':<11}"
            f"{'Expect':<11}"
            f"{'PF':<8}"
            f"{'Strategy Params':<50}"
        )
        print("-" * 132)

        for rank, sweep_result in enumerate(results[:top], start=1):
            row = sweep_result.to_dict()
            params = self._format_strategy_params(
                sweep_result.candidate.strategy_parameters
            )
            win_rate = f"{row['Win Rate']:.2f}%"
            average_return = f"{row['Average Return']:.2f}%"
            expectancy = f"{row['Expectancy']:.2f}%"
            profit_factor = f"{row['Profit Factor']:.2f}"
            print(
                f"{rank:<6}"
                f"{row['Hold Days']:<7}"
                f"{row['Min History Days']:<9}"
                f"{str(row['Allow Overlap']):<10}"
                f"{row['Trades']:<9}"
                f"{win_rate:<11}"
                f"{average_return:<11}"
                f"{expectancy:<11}"
                f"{profit_factor:<8}"
                f"{params:<50}"
            )

        print("=" * 132)

    @staticmethod
    def _format_strategy_params(parameters: dict) -> str:
        if not parameters:
            return "default"

        return ", ".join(
            f"{name}={value}" for name, value in parameters.items()
        )

    def print_walk_forward(self, summary, results):
        print("=" * 140)
        print("Walk-Forward Results")
        print("=" * 140)
        print(f"Windows Tested: {summary.windows}")
        print(
            "Forward Windows With Trades: "
            f"{summary.forward_windows_with_trades}"
        )
        print(
            "Profitable Forward Windows: "
            f"{summary.profitable_forward_windows}"
        )
        print(f"Average Forward Return: {summary.average_forward_return:.2f}%")
        print(
            "Average Forward Expectancy: "
            f"{summary.average_forward_expectancy:.2f}%"
        )
        print(
            "Average Forward Profit Factor: "
            f"{summary.average_forward_profit_factor:.2f}"
        )
        print("-" * 140)

        print(
            f"{'Train':<23}"
            f"{'Test':<23}"
            f"{'Hold':<7}"
            f"{'Trades':<9}"
            f"{'Win Rate':<11}"
            f"{'Avg Ret':<11}"
            f"{'Expect':<11}"
            f"{'PF':<8}"
            f"{'Selected Strategy Params':<40}"
        )
        print("-" * 140)

        for result in results:
            row = result.to_dict()
            train_period = f"{row['Train Start']} -> {row['Train End']}"
            test_period = f"{row['Test Start']} -> {row['Test End']}"
            params = (
                self._format_strategy_params(
                    result.training_result.candidate.strategy_parameters
                )
                if result.training_result is not None
                else "n/a"
            )
            win_rate = f"{row['Forward Win Rate']:.2f}%"
            average_return = f"{row['Forward Average Return']:.2f}%"
            expectancy = f"{row['Forward Expectancy']:.2f}%"
            profit_factor = f"{row['Forward Profit Factor']:.2f}"
            print(
                f"{train_period:<23}"
                f"{test_period:<23}"
                f"{str(row['Selected Hold Days']):<7}"
                f"{row['Forward Trades']:<9}"
                f"{win_rate:<11}"
                f"{average_return:<11}"
                f"{expectancy:<11}"
                f"{profit_factor:<8}"
                f"{params:<40}"
            )

        print("=" * 140)
