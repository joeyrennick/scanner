from scanner.models.market_data import MarketData
from scanner.strategies.strategy_engine import StrategyEngine
import pandas as pd


def create_market_data(
    price=100,
    ma20=99,
    ma50=95,
    ma200=80,
    atr14=2,
    avg_volume=1000000,
    relative_volume=1.5,
):
    history = pd.DataFrame({
        "Close": [price],
        "High": [price],
        "MA20": [ma20],
        "MA50": [ma50],
        "MA200": [ma200],
        "ATR14": [atr14],
        "AvgVolume20": [avg_volume],
        "RelativeVolume": [relative_volume],
    })

    return MarketData(
        ticker="TEST",
        history=history,
    )


def test_pullback_strategy_triggers():
    engine = StrategyEngine()

    market_data = create_market_data()

    results = engine.evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    pullback = results[0]

    assert pullback.triggered
    assert pullback.score == 20


def test_pullback_strategy_does_not_trigger_when_below_200ma():
    engine = StrategyEngine()

    market_data = create_market_data(
        price=75,
        ma20=76,
        ma50=74,
        ma200=80,
    )

    results = engine.evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not results[0].triggered