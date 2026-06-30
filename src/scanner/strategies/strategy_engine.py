from scanner.models.market_data import MarketData
from scanner.models.strategy_result import StrategyResult


class StrategyEngine:

    def evaluate(self, market_data: MarketData, relative_strength: float) -> list[StrategyResult]:
        results = []

        results.append(
            self._evaluate_pullback_strategy(
                market_data=market_data,
                relative_strength=relative_strength,
            )
        )

        return results

    def _evaluate_pullback_strategy(
        self,
        market_data: MarketData,
        relative_strength: float,
    ) -> StrategyResult:
        near_20ma = abs(market_data.price - market_data.ma20) / market_data.ma20 <= 0.03

        triggered = (
            market_data.price > market_data.ma200
            and market_data.ma50 > market_data.ma200
            and near_20ma
            and market_data.relative_volume >= 1.0
            and relative_strength > 0
        )

        return StrategyResult(
            name="Pullback Strategy",
            triggered=triggered,
            score=20 if triggered else 0,
            reason="Price is in an uptrend and pulling back near the 20MA"
            if triggered
            else "Pullback conditions not met",
        )