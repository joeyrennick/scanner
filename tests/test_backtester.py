from scanner.backtesting.backtester import Backtester
from scanner.strategies.pullback_strategy import PullbackStrategy
from tests.market_data_factory import create_market_data


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
        relative_strength=15,
        hold_days=5,
    )

    assert result.ticker == "TEST"
    assert result.strategy_name == "Pullback Strategy"
    assert result.total_trades > 0
    assert result.average_return > 0
    assert result.win_rate > 0