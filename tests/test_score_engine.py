from scanner.scoring.score_engine import (
    ScoreBreakdown,
    calculate_relative_strength_score,
    calculate_score_breakdown,
    calculate_trend_score,
    calculate_volume_score,
    calculate_volatility_score,
)


def test_trend_score_strong_uptrend_near_20ma():
    score = calculate_trend_score(
        price=105,
        ma20=100,
        ma50=90,
        ma200=80,
    )

    assert score == 80


def test_relative_strength_score_strong():
    assert calculate_relative_strength_score(25) == 25


def test_relative_strength_score_moderate():
    assert calculate_relative_strength_score(12) == 20


def test_relative_strength_score_positive():
    assert calculate_relative_strength_score(3) == 15


def test_relative_strength_score_slightly_negative():
    assert calculate_relative_strength_score(-2) == 5


def test_relative_strength_score_weak():
    assert calculate_relative_strength_score(-10) == 0


def test_volume_score_high():
    assert calculate_volume_score(2.0) == 15


def test_volume_score_medium():
    assert calculate_volume_score(1.5) == 10


def test_volume_score_light():
    assert calculate_volume_score(1.2) == 5


def test_volume_score_low():
    assert calculate_volume_score(0.7) == -5


def test_volatility_score_low_atr():
    assert calculate_volatility_score(atr14=2, price=100) == 10


def test_volatility_score_medium_atr():
    assert calculate_volatility_score(atr14=5, price=100) == 5


def test_volatility_score_high_atr():
    assert calculate_volatility_score(atr14=8, price=100) == 0


def test_score_breakdown_total_score():
    breakdown = calculate_score_breakdown(
        price=105,
        ma20=100,
        ma50=90,
        ma200=80,
        relative_strength=25,
        relative_volume=2.0,
        atr14=2,
    )

    assert isinstance(breakdown, ScoreBreakdown)
    assert breakdown.trend_score == 80
    assert breakdown.relative_strength_score == 25
    assert breakdown.volume_score == 15
    assert breakdown.volatility_score == 10
    assert breakdown.total_score == 130