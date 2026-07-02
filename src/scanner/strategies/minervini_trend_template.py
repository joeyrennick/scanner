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
        history = market_data.history

        high_52_week = history["High"].tail(252).max().item()
        low_52_week = history["Low"].tail(252).min().item()

        ma150 = history["Close"].rolling(window=150).mean().iloc[-1].item()
        ma200_today = market_data.ma200
        ma200_20_days_ago = history["MA200"].iloc[-20].item()

        checks = {
            "Price > 50MA": market_data.price > market_data.ma50,
            "Price > 150MA": market_data.price > ma150,
            "Price > 200MA": market_data.price > market_data.ma200,
            "50MA > 150MA": market_data.ma50 > ma150,
            "150MA > 200MA": ma150 > market_data.ma200,
            "200MA Rising": ma200_today > ma200_20_days_ago,
            "Price ≥ 30% Above 52W Low": market_data.price >= low_52_week * 1.30,
            "Price Within 25% Of 52W High": market_data.price >= high_52_week * 0.75,
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