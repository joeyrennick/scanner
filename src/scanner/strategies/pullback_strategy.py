from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy
from scanner.strategies.strategy_category import StrategyCategory


class PullbackStrategy(BaseStrategy):
    name = "Pullback Strategy"
    category = StrategyCategory.ENTRY

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        checks = {
            "Price > 200MA": market_data.price > market_data.ma200,
            "50MA > 200MA": market_data.ma50 > market_data.ma200,
            "Near 20MA ≤ 3%": abs(market_data.price - market_data.ma20) / market_data.ma20 <= 0.03,
            "Relative Volume ≥ 1": market_data.relative_volume >= 1.0,
            "Relative Strength > 0": relative_strength > 0,
        }

        triggered = all(checks.values())

        return StrategyResult(
            name=self.name,
            category=self.category,
            triggered=triggered,
            score=20 if triggered else 0,
            reason=(
                "Price is in an uptrend and pulling back near the 20MA"
                if triggered
                else "Pullback conditions not met"
            ),
            checks=checks,
        )