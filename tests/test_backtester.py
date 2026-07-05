from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtester import Backtester
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.pullback_strategy import PullbackStrategy
from scanner.strategies.strategy_category import StrategyCategory
from tests.market_data_factory import create_market_data


def create_flat_benchmark_history(days: int):
    benchmark = create_market_data(days=days).history.copy()
    benchmark["Close"] = 100
    return benchmark


def test_backtester_creates_trades_from_pullback_triggers():
    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=95,
        ma200=80,
        days=260,
    )

    result = Backtester().run(
        ticker="TEST",
        history=market_data.history,
        strategy=PullbackStrategy(),
        benchmark_history=create_flat_benchmark_history(days=260),
        hold_days=5,
    )

    assert result.ticker == "TEST"
    assert result.strategy_name == "Pullback Strategy"
    assert result.statistics.total_trades > 0
    assert result.statistics.average_return > 0
    assert result.statistics.win_rate > 0


def test_backtester_can_block_overlapping_trades():
    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=95,
        ma200=80,
        days=260,
    )

    overlapping_result = Backtester().run(
        ticker="TEST",
        history=market_data.history,
        strategy=PullbackStrategy(),
        benchmark_history=create_flat_benchmark_history(days=260),
        config=BacktestConfig(hold_days=5, allow_overlapping_trades=True),
    )
    blocked_result = Backtester().run(
        ticker="TEST",
        history=market_data.history,
        strategy=PullbackStrategy(),
        benchmark_history=create_flat_benchmark_history(days=260),
        config=BacktestConfig(hold_days=5, allow_overlapping_trades=False),
    )

    assert overlapping_result.statistics.total_trades > blocked_result.statistics.total_trades
    assert blocked_result.statistics.total_trades == 1


def test_backtester_uses_configured_min_history_days():
    market_data = create_market_data(
        start_price=100,
        ma20=106,
        ma50=95,
        ma200=80,
        days=80,
    )

    default_result = Backtester().run(
        ticker="TEST",
        history=market_data.history,
        strategy=PullbackStrategy(),
        benchmark_history=create_flat_benchmark_history(days=80),
        config=BacktestConfig(hold_days=5),
    )
    configured_result = Backtester().run(
        ticker="TEST",
        history=market_data.history,
        strategy=PullbackStrategy(),
        benchmark_history=create_flat_benchmark_history(days=80),
        config=BacktestConfig(hold_days=5, min_history_days=63),
    )

    assert default_result.statistics.total_trades == 0
    assert configured_result.statistics.total_trades > 0


def test_backtester_calculates_relative_strength_without_future_data():
    market_data = create_market_data(
        start_price=100,
        ma20=100,
        ma50=95,
        ma200=80,
        days=70,
    )
    market_data.history["Close"] = 100
    market_data.history.loc[market_data.history.index[-1], "Close"] = 200

    class RecordingStrategy:
        name = "Recording Strategy"
        category = StrategyCategory.ENTRY

        def __init__(self):
            self.relative_strengths = []

        def evaluate(self, market_data, relative_strength):
            self.relative_strengths.append(relative_strength)
            return StrategyResult(
                name=self.name,
                category=self.category,
                triggered=False,
                score=0,
                reason="record only",
                checks={},
            )

    strategy = RecordingStrategy()

    Backtester().run(
        ticker="TEST",
        history=market_data.history,
        strategy=strategy,
        benchmark_history=create_flat_benchmark_history(days=70),
        config=BacktestConfig(hold_days=1, min_history_days=63),
    )

    assert strategy.relative_strengths
    assert max(strategy.relative_strengths) == 0
