import pandas as pd


def add_atr(data, window=14):
    data = data.copy()

    high = data["High"]
    low = data["Low"]
    close = data["Close"]

    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()

    true_range = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    data["ATR14"] = true_range.rolling(window=window).mean()

    return data