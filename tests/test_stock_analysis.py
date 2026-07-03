from scanner.models.stock_analysis import StockAnalysis
from scanner.models.strategy_result import StrategyResult
from scanner.scoring.score_engine import ScoreBreakdown
from scanner.strategies.strategy_category import StrategyCategory


def test_to_dict_includes_strategy_passed_and_failed_checks():
    analysis = StockAnalysis(
        ticker="TEST",
        price=100,
        ma20=101,
        ma50=95,
        ma200=90,
        relative_strength=10,
        atr14=2,
        avg_volume_20=1_000_000,
        relative_volume=0.8,
        score_breakdown=ScoreBreakdown(
            trend_score=50,
            relative_strength_score=15,
            volume_score=-5,
            volatility_score=10,
        ),
        strategy_results=[
            StrategyResult(
                name="Pullback Strategy",
                category=StrategyCategory.ENTRY,
                triggered=False,
                score=0,
                reason="Pullback conditions not met",
                checks={
                    "Price > 200MA": True,
                    "Relative Volume >= 1": False,
                },
            )
        ],
    )

    result = analysis.to_dict()

    assert result["Pullback: Passed Checks"] == "Price > 200MA"
    assert result["Pullback: Failed Checks"] == "Relative Volume >= 1"
    assert result["Pullback Strategy"] == "NO"
