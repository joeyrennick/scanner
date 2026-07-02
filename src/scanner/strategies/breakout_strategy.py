from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy
from scanner.strategies.strategy_category import StrategyCategory


class BreakoutStrategy(BaseStrategy):
    name = "Breakout Strategy"
    category = StrategyCategory.ENTRY

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        high_52_week = market_data.history["High"].tail(252).max().item()

        near_52_week_high = market_data.price >= high_52_week * 0.97

        checks = {
            "Near 52-Week High": near_52_week_high,
            "Price > 50MA": market_data.price > market_data.ma50,
            "Price > 200MA": market_data.price > market_data.ma200,
            "Relative Volume ≥ 1.2": market_data.relative_volume >= 1.2,
            "Relative Strength > 0": relative_strength > 0,
        }

        triggered = all(checks.values())

        return StrategyResult(
            name=self.name,
            category=self.category,
            triggered=triggered,
            score=25 if triggered else 0,
            reason=(
                "Price is near a 52-week high with strong volume and relative strength"
                if triggered
                else "Breakout conditions not met"
            ),
            checks=checks,
        )