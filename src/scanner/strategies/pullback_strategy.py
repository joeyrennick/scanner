from dataclasses import dataclass

from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy, StrategyConfig
from scanner.strategies.strategy_category import StrategyCategory


@dataclass(frozen=True)
class PullbackStrategyConfig(StrategyConfig):
    max_distance_from_ma20: float = 0.03
    min_relative_volume: float = 1.0
    min_relative_strength: float = 0.0
    persistence_lookback_days: int = 20
    min_price_above_ma200_days: int = 18
    min_ma50_above_ma200_days: int = 20
    min_ma50_ma200_spread: float = 0.01
    whipsaw_lookback_days: int = 60
    max_price_ma200_crosses: int = 2
    triggered_score: int = 20


class PullbackStrategy(BaseStrategy):
    name = "Pullback Strategy"
    category = StrategyCategory.ENTRY
    config_class = PullbackStrategyConfig

    def __init__(self, config: PullbackStrategyConfig | None = None):
        self.config = config or PullbackStrategyConfig()

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        max_distance_pct = self.config.max_distance_from_ma20 * 100
        min_relative_volume = self.config.min_relative_volume
        min_relative_strength = self.config.min_relative_strength
        persistence_days = self.config.persistence_lookback_days
        price_above_days = market_data.price_above_ma200_days(persistence_days)
        ma50_above_days = market_data.ma50_above_ma200_days(persistence_days)
        min_spread_pct = self.config.min_ma50_ma200_spread * 100
        cross_count = market_data.price_ma200_cross_count(
            self.config.whipsaw_lookback_days
        )
        checks = {
            "Price > 200MA": market_data.price > market_data.ma200,
            "50MA > 200MA": market_data.ma50 > market_data.ma200,
            (
                f"Price > 200MA ≥ {self.config.min_price_above_ma200_days}/"
                f"{persistence_days} Sessions"
            ): price_above_days >= self.config.min_price_above_ma200_days,
            (
                f"50MA > 200MA ≥ {self.config.min_ma50_above_ma200_days}/"
                f"{persistence_days} Sessions"
            ): ma50_above_days >= self.config.min_ma50_above_ma200_days,
            f"50MA ≥ {min_spread_pct:g}% Above 200MA": (
                market_data.ma50_ma200_spread >= self.config.min_ma50_ma200_spread
            ),
            (
                f"Price/200MA Crosses ≤ {self.config.max_price_ma200_crosses} In "
                f"{self.config.whipsaw_lookback_days} Sessions"
            ): cross_count <= self.config.max_price_ma200_crosses,
            f"Near 20MA ≤ {max_distance_pct:g}%": (
                abs(market_data.price - market_data.ma20) / market_data.ma20
                <= self.config.max_distance_from_ma20
            ),
            f"Relative Volume ≥ {min_relative_volume:g}": (
                market_data.relative_volume >= min_relative_volume
            ),
            f"Relative Strength > {min_relative_strength:g}": (
                relative_strength > min_relative_strength
            ),
        }

        triggered = all(checks.values())

        return StrategyResult(
            name=self.name,
            category=self.category,
            triggered=triggered,
            score=self.config.triggered_score if triggered else 0,
            reason=(
                "Price is in an uptrend and pulling back near the 20MA"
                if triggered
                else "Pullback conditions not met"
            ),
            checks=checks,
        )
