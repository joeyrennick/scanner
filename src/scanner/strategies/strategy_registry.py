from scanner.strategies.breakout_strategy import BreakoutStrategy
from scanner.strategies.minervini_trend_template import MinerviniTrendTemplate
from scanner.strategies.pullback_strategy import PullbackStrategy


class StrategyRegistry:

    _strategies = {
        "minervini": MinerviniTrendTemplate,
        "pullback": PullbackStrategy,
        "breakout": BreakoutStrategy,
    }

    @classmethod
    def get(cls, name: str):
        try:
            return cls._strategies[name.lower()]()

        except KeyError:
            supported = ", ".join(sorted(cls._strategies.keys()))
            raise ValueError(
                f"Unknown strategy '{name}'. "
                f"Supported strategies: {supported}"
            )

    @classmethod
    def all(cls):
        return [
            strategy_class()
            for strategy_class in cls._strategies.values()
        ]

    @classmethod
    def names(cls):
        return sorted(cls._strategies.keys())