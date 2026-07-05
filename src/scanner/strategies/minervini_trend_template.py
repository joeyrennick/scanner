from dataclasses import dataclass

from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy, StrategyConfig
from scanner.strategies.strategy_category import StrategyCategory


@dataclass(frozen=True)
class MinerviniTrendTemplateConfig(StrategyConfig):
    min_percent_above_52_week_low: float = 30.0
    max_percent_below_52_week_high: float = 25.0
    min_relative_strength: float = 0.0
    triggered_score: int = 30


class MinerviniTrendTemplate(BaseStrategy):
    name = "Minervini Trend Template"
    category = StrategyCategory.FILTER
    config_class = MinerviniTrendTemplateConfig

    def __init__(self, config: MinerviniTrendTemplateConfig | None = None):
        self.config = config or MinerviniTrendTemplateConfig()

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        min_low_distance = self.config.min_percent_above_52_week_low
        max_high_distance = self.config.max_percent_below_52_week_high
        min_relative_strength = self.config.min_relative_strength
        checks = {
            "Price > 50MA": market_data.price > market_data.ma50,
            "Price > 150MA": market_data.price > market_data.ma150,
            "Price > 200MA": market_data.price > market_data.ma200,
            "50MA > 150MA": market_data.ma50 > market_data.ma150,
            "150MA > 200MA": market_data.ma150 > market_data.ma200,
            "200MA Rising": market_data.ma200_rising,
            f"Price ≥ {min_low_distance:g}% Above 52W Low": (
                market_data.percent_above_52_week_low >= min_low_distance
            ),
            f"Price Within {max_high_distance:g}% Of 52W High": (
                market_data.percent_below_52_week_high <= max_high_distance
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
                "Stock meets Minervini Trend Template criteria"
                if triggered
                else "Stock does not meet Minervini Trend Template criteria"
            ),
            checks=checks,
        )
