from dataclasses import dataclass

from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy, StrategyConfig
from scanner.strategies.strategy_category import StrategyCategory


@dataclass(frozen=True)
class BreakoutStrategyConfig(StrategyConfig):
    max_percent_below_52_week_high: float = 3.0
    min_relative_volume: float = 1.2
    min_relative_strength: float = 0.0
    triggered_score: int = 25


class BreakoutStrategy(BaseStrategy):
    name = "Breakout Strategy"
    category = StrategyCategory.ENTRY
    config_class = BreakoutStrategyConfig

    def __init__(self, config: BreakoutStrategyConfig | None = None):
        self.config = config or BreakoutStrategyConfig()

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        max_high_distance = self.config.max_percent_below_52_week_high
        min_relative_volume = self.config.min_relative_volume
        min_relative_strength = self.config.min_relative_strength
        high_check_name = (
            "Near 52-Week High"
            if max_high_distance == 3.0
            else f"Near 52-Week High ≤ {max_high_distance:g}%"
        )
        checks = {
            high_check_name: (
                market_data.percent_below_52_week_high <= max_high_distance
            ),
            "Price > 50MA": market_data.price > market_data.ma50,
            "Price > 200MA": market_data.price > market_data.ma200,
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
                "Price is near a 52-week high with strong volume and relative strength"
                if triggered
                else "Breakout conditions not met"
            ),
            checks=checks,
        )
