from scanner.strategies.strategy_engine import StrategyEngine
from tests.market_data_factory import create_market_data


def test_pullback_strategy_triggers():
    engine = StrategyEngine()
    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=95,
        ma200=80,
    )

    results = engine.evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    pullback = next(result for result in results if result.name == "Pullback Strategy")

    assert pullback.triggered
    assert pullback.score == 20


def test_pullback_strategy_does_not_trigger_when_below_200ma():
    engine = StrategyEngine()

    market_data = create_market_data(
        start_price=75,
        ma20=76,
        ma50=74,
        ma200=80,
    )

    results = engine.evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    pullback = next(result for result in results if result.name == "Pullback Strategy")

    assert not pullback.triggered