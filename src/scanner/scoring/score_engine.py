from dataclasses import dataclass


@dataclass
class ScoreBreakdown:
    trend_score: int
    relative_strength_score: int
    volume_score: int
    volatility_score: int

    @property
    def total_score(self) -> int:
        return (
            self.trend_score
            + self.relative_strength_score
            + self.volume_score
            + self.volatility_score
        )


def calculate_trend_score(price: float, ma20: float, ma50: float, ma200: float) -> int:
    score = 0

    if price > ma20:
        score += 10
    if price > ma50:
        score += 15
    if price > ma200:
        score += 20
    if ma50 > ma200:
        score += 20

    if abs(price - ma20) / ma20 <= 0.05:
        score += 15

    return score


def calculate_relative_strength_score(relative_strength: float) -> int:
    if relative_strength > 20:
        return 25
    if relative_strength > 10:
        return 20
    if relative_strength > 0:
        return 15
    if relative_strength > -5:
        return 5
    return 0


def calculate_volume_score(relative_volume: float) -> int:
    if relative_volume >= 2.0:
        return 15
    if relative_volume >= 1.5:
        return 10
    if relative_volume >= 1.2:
        return 5
    if relative_volume < 0.8:
        return -5
    return 0


def calculate_volatility_score(atr14: float, price: float) -> int:
    atr_percent = atr14 / price

    if atr_percent <= 0.03:
        return 10
    if atr_percent <= 0.06:
        return 5
    return 0


def calculate_score_breakdown(
    price: float,
    ma20: float,
    ma50: float,
    ma200: float,
    relative_strength: float,
    relative_volume: float,
    atr14: float,
) -> ScoreBreakdown:
    return ScoreBreakdown(
        trend_score=calculate_trend_score(price, ma20, ma50, ma200),
        relative_strength_score=calculate_relative_strength_score(relative_strength),
        volume_score=calculate_volume_score(relative_volume),
        volatility_score=calculate_volatility_score(atr14, price),
    )