from dataclasses import dataclass
from typing import Literal

from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy, StrategyConfig
from scanner.strategies.strategy_category import StrategyCategory


BounceAnchor = Literal["ma20", "ma50"]


@dataclass(frozen=True)
class ConfigurableBounceStrategyConfig(StrategyConfig):
    anchor: BounceAnchor = "ma20"
    max_distance_from_anchor: float = 0.03
    require_prior_day_high_confirmation: bool = False
    min_relative_volume: float | None = None
    min_relative_strength: float = 0.0
    triggered_score: int = 20


class ConfigurableBounceStrategy(BaseStrategy):
    name = "Bounce Strategy"
    category = StrategyCategory.ENTRY
    config_class = ConfigurableBounceStrategyConfig

    def __init__(self, config: ConfigurableBounceStrategyConfig | None = None):
        self.config = config or ConfigurableBounceStrategyConfig()
        if self.config.anchor not in ("ma20", "ma50"):
            raise ValueError("Bounce anchor must be 'ma20' or 'ma50'")

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        anchor_label = self._anchor_label()
        anchor_value = self._anchor_value(market_data)
        max_distance_pct = self.config.max_distance_from_anchor * 100

        checks = {
            "Price > 200MA": market_data.price > market_data.ma200,
            "50MA > 200MA": market_data.ma50 > market_data.ma200,
            f"Price ≥ {anchor_label}": market_data.price >= anchor_value,
            f"Within {max_distance_pct:g}% Of {anchor_label}": (
                abs(market_data.price - anchor_value) / anchor_value
                <= self.config.max_distance_from_anchor
            ),
            f"Relative Strength > {self.config.min_relative_strength:g}": (
                relative_strength > self.config.min_relative_strength
            ),
        }

        if self.config.require_prior_day_high_confirmation:
            checks["Close > Prior Day High"] = self._closes_above_prior_day_high(
                market_data
            )

        if self.config.min_relative_volume is not None:
            checks[f"Relative Volume ≥ {self.config.min_relative_volume:g}"] = (
                market_data.relative_volume >= self.config.min_relative_volume
            )

        triggered = all(checks.values())

        return StrategyResult(
            name=self.name,
            category=self.category,
            triggered=triggered,
            score=self.config.triggered_score if triggered else 0,
            reason=(
                f"Price is bouncing from {anchor_label} with confirmation"
                if triggered
                else "Bounce conditions not met"
            ),
            checks=checks,
        )

    def _anchor_label(self) -> str:
        return self.config.anchor.upper()

    def _anchor_value(self, market_data: MarketData) -> float:
        if self.config.anchor == "ma20":
            return market_data.ma20

        return market_data.ma50

    def _closes_above_prior_day_high(self, market_data: MarketData) -> bool:
        if len(market_data.history) < 2 or "High" not in market_data.history.columns:
            return False

        prior_day_high = market_data.history["High"].iloc[-2].item()
        return market_data.price > prior_day_high
