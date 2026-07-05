from scanner.strategies.base_strategy import StrategyConfig
from scanner.strategies.breakout_strategy import BreakoutStrategy
from scanner.strategies.configurable_bounce_strategy import ConfigurableBounceStrategy
from scanner.strategies.minervini_trend_template import MinerviniTrendTemplate
from scanner.strategies.pullback_strategy import PullbackStrategy


class StrategyRegistry:

    _strategies = {
        "minervini": MinerviniTrendTemplate,
        "pullback": PullbackStrategy,
        "breakout": BreakoutStrategy,
        "bounce": ConfigurableBounceStrategy,
    }

    @classmethod
    def get(cls, name: str, config: StrategyConfig | None = None):
        try:
            strategy_class = cls._strategies[name.lower()]
            return strategy_class(config=config) if config is not None else strategy_class()

        except KeyError:
            supported = ", ".join(sorted(cls._strategies.keys()))
            raise ValueError(
                f"Unknown strategy '{name}'. "
                f"Supported strategies: {supported}"
            )

    @classmethod
    def all(cls, configs: dict[str, StrategyConfig] | None = None):
        configs = configs or {}
        return [
            strategy_class(config=configs[name])
            if name in configs
            else strategy_class()
            for name, strategy_class in cls._strategies.items()
        ]

    @classmethod
    def names(cls):
        return sorted(cls._strategies.keys())

    @classmethod
    def default_config(cls, name: str) -> StrategyConfig:
        try:
            strategy_class = cls._strategies[name.lower()]
            return strategy_class.config_class()

        except KeyError:
            supported = ", ".join(sorted(cls._strategies.keys()))
            raise ValueError(
                f"Unknown strategy '{name}'. "
                f"Supported strategies: {supported}"
            )

    @classmethod
    def default_configs(cls) -> dict[str, StrategyConfig]:
        return {
            name: strategy_class.config_class()
            for name, strategy_class in cls._strategies.items()
        }
