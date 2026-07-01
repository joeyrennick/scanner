from scanner.config.settings import settings


def percent_change(data):
    close = data["Close"]

    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    lookback_days = settings.relative_strength_lookback_days

    if len(close) < lookback_days:
        raise ValueError(f"Insufficient price history: only {len(close)} rows")

    old = close.iloc[-lookback_days].item()
    new = close.iloc[-1].item()

    return ((new - old) / old) * 100


def calculate_relative_strength(stock_data, benchmark_data):
    return percent_change(stock_data) - percent_change(benchmark_data)