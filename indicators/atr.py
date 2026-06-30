def add_atr(data, window=14):
    data = data.copy()

    high_low = data["High"] - data["Low"]
    high_close = (data["High"] - data["Close"].shift()).abs()
    low_close = (data["Low"] - data["Close"].shift()).abs()

    true_range = high_low.combine(high_close, max).combine(low_close, max)

    data["ATR14"] = true_range.rolling(window=window).mean()

    return data