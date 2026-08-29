from abc import ABC, abstractmethod
from dataclasses import dataclass

from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult
from scanner.strategies.strategy_category import StrategyCategory


@dataclass(frozen=True)
class StrategyConfig:
    pass


class BaseStrategy(ABC):
    name: str
    category: StrategyCategory
    config_class: type[StrategyConfig] = StrategyConfig
    evaluation_mode: str = "technical"
    backtestable: bool = True

    @abstractmethod
    def evaluate(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        pass
