from dataclasses import dataclass
from typing import Any

from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy, StrategyConfig
from scanner.strategies.strategy_category import StrategyCategory


@dataclass(frozen=True)
class UndervaluedStrategyConfig(StrategyConfig):
    minimum_margin_of_safety: float = 0.15
    discount_rate: float | None = None
    terminal_growth_rate: float = 0.025
    projection_years: int = 5
    triggered_score: int = 20


class UndervaluedStrategy(BaseStrategy):
    name = "Undervalued Strategy"
    category = StrategyCategory.ENTRY
    config_class = UndervaluedStrategyConfig
    evaluation_mode = "fundamental"
    backtestable = False

    def __init__(self, config: UndervaluedStrategyConfig | None = None):
        self.config = config or UndervaluedStrategyConfig()

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        return StrategyResult(
            name=self.name,
            category=self.category,
            triggered=False,
            score=0,
            reason="Requires the SEC fundamentals scan mode",
            checks={"SEC valuation available": False},
        )

    def evaluate_valuation(self, valuation: dict[str, Any]) -> StrategyResult:
        fair_value = _number(valuation.get("scenarios"), "base", "fair_value")
        margin_of_safety = _finite(valuation.get("margin_of_safety"))
        checks = {
            "Base fair value available": fair_value is not None,
            (
                f"Margin of safety ≥ "
                f"{self.config.minimum_margin_of_safety * 100:g}%"
            ): (
                margin_of_safety is not None
                and margin_of_safety >= self.config.minimum_margin_of_safety
            ),
        }
        triggered = all(checks.values())
        return StrategyResult(
            name=self.name,
            category=self.category,
            triggered=triggered,
            score=self.config.triggered_score if triggered else 0,
            reason=(
                "Base DCF fair value provides the required margin of safety"
                if triggered
                else "The required DCF margin of safety is not present"
            ),
            checks=checks,
        )

    def assumptions(self) -> dict[str, float | int]:
        assumptions: dict[str, float | int] = {
            "terminal_growth_rate": self.config.terminal_growth_rate,
            "projection_years": self.config.projection_years,
        }
        if self.config.discount_rate is not None:
            assumptions["discount_rate"] = self.config.discount_rate
        return assumptions


def _number(
    scenarios: object,
    scenario_name: str,
    key: str,
) -> float | None:
    for scenario in list(scenarios or []):
        if isinstance(scenario, dict) and scenario.get("name") == scenario_name:
            return _finite(scenario.get(key))
    return None


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None
