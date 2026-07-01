from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy
from scanner.strategies.pullback_strategy import PullbackStrategy
from scanner.strategies.breakout_strategy import BreakoutStrategy


class StrategyEngine:

    def __init__(self, strategies: list[BaseStrategy] | None = None):
        self.strategies = strategies or [
            PullbackStrategy(),
            BreakoutStrategy(),
        ]

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> list[StrategyResult]:
        return [
            strategy.evaluate(
                market_data=market_data,
                relative_strength=relative_strength,
            )
            for strategy in self.strategies
        ]