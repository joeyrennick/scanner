from abc import ABC, abstractmethod

from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.strategy_category import StrategyCategory


class BaseStrategy(ABC):
    name: str
    category: StrategyCategory

    @abstractmethod
    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        pass