from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyResult:
    name: str
    triggered: bool
    score: int
    reason: str
    checks: dict[str, bool]