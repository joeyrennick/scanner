from dataclasses import dataclass

from scanner.strategies.strategy_category import StrategyCategory


@dataclass
class StrategyResult:
    name: str
    category: StrategyCategory
    triggered: bool
    score: int
    reason: str
    checks: dict[str, bool]