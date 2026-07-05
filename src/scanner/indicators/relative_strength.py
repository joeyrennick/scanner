from scanner.config.settings import settings


def percent_change(price_history, lookback_days: int | None = None):
    close = _close_series(price_history)

    lookback_days = (
        settings.relative_strength_lookback_days
        if lookback_days is None
        else lookback_days
    )

    if len(close) < lookback_days:
        raise ValueError(f"Insufficient price history: only {len(close)} rows")

    old = close.iloc[-lookback_days].item()
    new = close.iloc[-1].item()

    return ((new - old) / old) * 100


def calculate_relative_strength(
    stock_history,
    benchmark_history,
    lookback_days: int | None = None,
) -> float:
    if isinstance(benchmark_history, int | float):
        raise TypeError(
            "benchmark_history must be price history, not a scalar benchmark return"
        )

    return percent_change(stock_history, lookback_days=lookback_days) - percent_change(
        benchmark_history,
        lookback_days=lookback_days,
    )


def _close_series(price_history):
    if isinstance(price_history, int | float):
        raise TypeError("price_history must be a pandas Series or DataFrame")

    if hasattr(price_history, "columns"):
        if "Close" in price_history.columns:
            return price_history["Close"]

        return price_history.iloc[:, 0]

    return price_history
