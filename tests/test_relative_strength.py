import pandas as pd
import pytest

from scanner.indicators.relative_strength import calculate_relative_strength


def create_history(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes})


def test_calculate_relative_strength_uses_two_price_histories():
    stock_history = create_history([100, 110])
    benchmark_history = create_history([100, 105])

    result = calculate_relative_strength(
        stock_history,
        benchmark_history,
        lookback_days=2,
    )

    assert result == pytest.approx(5.0)


def test_calculate_relative_strength_rejects_scalar_benchmark_return():
    stock_history = create_history([100, 110])

    with pytest.raises(TypeError, match="benchmark_history"):
        calculate_relative_strength(
            stock_history,
            5.0,
            lookback_days=2,
        )


def test_calculate_relative_strength_rejects_insufficient_history():
    stock_history = create_history([100])
    benchmark_history = create_history([100])

    with pytest.raises(ValueError, match="Insufficient price history"):
        calculate_relative_strength(
            stock_history,
            benchmark_history,
            lookback_days=2,
        )
