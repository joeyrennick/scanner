from abc import ABC, abstractmethod
from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult


class BaseStrategy(ABC):
    name: str

    @abstractmethod
    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        pass