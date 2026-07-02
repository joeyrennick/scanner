from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy
from scanner.strategies.strategy_category import StrategyCategory


class MinerviniTrendTemplate(BaseStrategy):
    name = "Minervini Trend Template"
    category = StrategyCategory.FILTER

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        checks = {
            "Price > 50MA": market_data.price > market_data.ma50,
            "Price > 150MA": market_data.price > market_data.ma150,
            "Price > 200MA": market_data.price > market_data.ma200,
            "50MA > 150MA": market_data.ma50 > market_data.ma150,
            "150MA > 200MA": market_data.ma150 > market_data.ma200,
            "200MA Rising": market_data.ma200_rising,
            "Price ≥ 30% Above 52W Low": market_data.percent_above_52_week_low >= 30,
            "Price Within 25% Of 52W High": market_data.percent_below_52_week_high <= 25,
            "Relative Strength > 0": relative_strength > 0,
        }

        triggered = all(checks.values())

        return StrategyResult(
            name=self.name,
            category=self.category,
            triggered=triggered,
            score=30 if triggered else 0,
            reason=(
                "Stock meets Minervini Trend Template criteria"
                if triggered
                else "Stock does not meet Minervini Trend Template criteria"
            ),
            checks=checks,
        )