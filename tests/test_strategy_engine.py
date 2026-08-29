from scanner.strategies.configurable_bounce_strategy import (
    ConfigurableBounceStrategy,
    ConfigurableBounceStrategyConfig,
)
from scanner.strategies.pullback_strategy import (
    PullbackStrategy,
    PullbackStrategyConfig,
)
from scanner.strategies.strategy_engine import StrategyEngine
from scanner.strategies.strategy_registry import StrategyRegistry
from scanner.strategies.undervalued_strategy import UndervaluedStrategy
from tests.market_data_factory import create_market_data


def test_pullback_strategy_triggers():
    engine = StrategyEngine(strategies=[PullbackStrategy()])

    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=95,
        ma200=80,
    )

    results = engine.evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    pullback = next(result for result in results if result.name == "Pullback Strategy")

    assert pullback.triggered
    assert pullback.score == 20


def test_pullback_strategy_does_not_trigger_when_below_200ma():
    engine = StrategyEngine(strategies=[PullbackStrategy()])

    market_data = create_market_data(
        start_price=75,
        ma20=76,
        ma50=74,
        ma200=80,
    )

    results = engine.evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    pullback = next(result for result in results if result.name == "Pullback Strategy")

    assert not pullback.triggered


def test_pullback_strategy_requires_price_above_200ma_persistence():
    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=95,
        ma200=80,
    )
    recent_index = market_data.history.index[-20:]
    market_data.history.loc[recent_index[:3], "Close"] = 79

    result = PullbackStrategy().evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not result.triggered
    assert not result.checks["Price > 200MA ≥ 18/20 Sessions"]


def test_pullback_strategy_requires_ma50_above_200ma_persistence():
    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=95,
        ma200=80,
    )
    market_data.history.loc[market_data.history.index[-2], "MA50"] = 79

    result = PullbackStrategy().evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not result.triggered
    assert not result.checks["50MA > 200MA ≥ 20/20 Sessions"]


def test_pullback_strategy_rejects_marginal_ma_spread():
    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=80.5,
        ma200=80,
    )

    result = PullbackStrategy().evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not result.triggered
    assert not result.checks["50MA ≥ 1% Above 200MA"]


def test_pullback_strategy_rejects_price_ma200_whipsaw():
    market_data = create_market_data(
        start_price=100,
        ma20=126,
        ma50=95,
        ma200=80,
    )
    recent_index = market_data.history.index[-60:-20]
    alternating_prices = [79 if index % 2 == 0 else 81 for index in range(40)]
    market_data.history.loc[recent_index, "Close"] = alternating_prices

    result = PullbackStrategy().evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not result.triggered
    assert not result.checks["Price/200MA Crosses ≤ 2 In 60 Sessions"]


def test_pullback_strategy_config_can_modify_threshold():
    market_data = create_market_data(
        start_price=100,
        ma20=120,
        ma50=95,
        ma200=80,
    )

    default_result = PullbackStrategy().evaluate(
        market_data=market_data,
        relative_strength=15,
    )
    configured_result = PullbackStrategy(
        config=PullbackStrategyConfig(max_distance_from_ma20=0.05),
    ).evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not default_result.triggered
    assert configured_result.triggered
    assert configured_result.score == 20


def test_strategy_registry_instantiates_default_config():
    config = StrategyRegistry.default_config("pullback")
    strategy = StrategyRegistry.get("pullback", config=config)

    assert isinstance(config, PullbackStrategyConfig)
    assert isinstance(strategy, PullbackStrategy)
    assert strategy.config == config


def test_strategy_registry_returns_default_configs_for_all_strategies():
    configs = StrategyRegistry.default_configs()

    assert set(configs) == {
        "bounce",
        "breakout",
        "minervini",
        "pullback",
        "undervalued",
    }
    assert isinstance(configs["bounce"], ConfigurableBounceStrategyConfig)
    assert isinstance(configs["pullback"], PullbackStrategyConfig)


def test_undervalued_strategy_requires_fifteen_percent_margin_of_safety():
    strategy = UndervaluedStrategy()

    passing = strategy.evaluate_valuation(
        {
            "margin_of_safety": 0.15,
            "scenarios": [{"name": "base", "fair_value": 115.0}],
        }
    )
    failing = strategy.evaluate_valuation(
        {
            "margin_of_safety": 0.149,
            "scenarios": [{"name": "base", "fair_value": 114.9}],
        }
    )

    assert passing.triggered is True
    assert passing.score == 20
    assert failing.triggered is False
    assert strategy.evaluation_mode == "fundamental"
    assert strategy.backtestable is False


def test_configurable_bounce_strategy_triggers_on_default_ma20_anchor():
    market_data = create_market_data(
        start_price=100,
        ma20=124,
        ma50=95,
        ma200=80,
        relative_volume=0.8,
    )

    result = ConfigurableBounceStrategy().evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert result.triggered
    assert result.score == 20
    assert result.checks["Price ≥ MA20"]
    assert result.checks["Within 3% Of MA20"]
    assert "Relative Volume ≥" not in " ".join(result.checks)


def test_configurable_bounce_strategy_supports_ma50_anchor():
    market_data = create_market_data(
        start_price=100,
        ma20=140,
        ma50=124,
        ma200=80,
    )

    result = ConfigurableBounceStrategy(
        config=ConfigurableBounceStrategyConfig(anchor="ma50"),
    ).evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert result.triggered
    assert result.checks["Price ≥ MA50"]
    assert result.checks["Within 3% Of MA50"]


def test_configurable_bounce_strategy_uses_distance_threshold():
    market_data = create_market_data(
        start_price=100,
        ma20=118,
        ma50=95,
        ma200=80,
    )

    default_result = ConfigurableBounceStrategy().evaluate(
        market_data=market_data,
        relative_strength=15,
    )
    configured_result = ConfigurableBounceStrategy(
        config=ConfigurableBounceStrategyConfig(max_distance_from_anchor=0.08),
    ).evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not default_result.triggered
    assert configured_result.triggered
    assert configured_result.checks["Within 8% Of MA20"]


def test_configurable_bounce_strategy_supports_prior_day_high_confirmation():
    market_data = create_market_data(
        start_price=100,
        ma20=124,
        ma50=95,
        ma200=80,
    )
    market_data.history.loc[market_data.history.index[-2], "High"] = (
        market_data.price - 1
    )

    result = ConfigurableBounceStrategy(
        config=ConfigurableBounceStrategyConfig(
            require_prior_day_high_confirmation=True,
        ),
    ).evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert result.triggered
    assert result.checks["Close > Prior Day High"]


def test_configurable_bounce_strategy_supports_relative_volume_threshold():
    market_data = create_market_data(
        start_price=100,
        ma20=124,
        ma50=95,
        ma200=80,
        relative_volume=1.1,
    )

    result = ConfigurableBounceStrategy(
        config=ConfigurableBounceStrategyConfig(min_relative_volume=1.5),
    ).evaluate(
        market_data=market_data,
        relative_strength=15,
    )

    assert not result.triggered
    assert not result.checks["Relative Volume ≥ 1.5"]
