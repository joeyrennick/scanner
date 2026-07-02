from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.base_strategy import BaseStrategy
from scanner.strategies.strategy_category import StrategyCategory
from scanner.strategies.strategy_registry import StrategyRegistry


class StrategyEngine:

    def __init__(self, strategies: list[BaseStrategy] | None = None):
        self.strategies = strategies or StrategyRegistry.all()

    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> list[StrategyResult]:
        filter_results = self._evaluate_by_category(
            category=StrategyCategory.FILTER,
            market_data=market_data,
            relative_strength=relative_strength,
        )

        if any(not result.triggered for result in filter_results):
            return filter_results

        entry_results = self._evaluate_by_category(
            category=StrategyCategory.ENTRY,
            market_data=market_data,
            relative_strength=relative_strength,
        )

        return filter_results + entry_results

    def _evaluate_by_category(
        self,
        category: StrategyCategory,
        market_data: MarketData,
        relative_strength: float,
    ) -> list[StrategyResult]:
        return [
            strategy.evaluate(
                market_data=market_data,
                relative_strength=relative_strength,
            )
            for strategy in self.strategies
            if strategy.category == category
        ]