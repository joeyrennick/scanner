import pandas as pd

from scanner.models.market_data import MarketData


def create_market_data(
    ticker="TEST",
    start_price=100,
    days=260,
    ma20=99,
    ma50=95,
    ma200=80,
    atr14=2,
    avg_volume=1_000_000,
    relative_volume=1.5,
):
    prices = [start_price + i * 0.1 for i in range(days)]

    history = pd.DataFrame({
        "Close": prices,
        "High": [price * 1.01 for price in prices],
        "Low": [price * 0.99 for price in prices],
        "MA20": [ma20] * days,
        "MA50": [ma50] * days,
        "MA200": [ma200] * days,
        "ATR14": [atr14] * days,
        "AvgVolume20": [avg_volume] * days,
        "RelativeVolume": [relative_volume] * days,
    })

    return MarketData(
        ticker=ticker,
        history=history,
    )