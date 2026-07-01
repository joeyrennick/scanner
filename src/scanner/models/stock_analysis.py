from dataclasses import dataclass
from scanner.scoring.score_engine import ScoreBreakdown
from scanner.models.strategy_result import StrategyResult


@dataclass
class StockAnalysis:
    ticker: str
    price: float
    ma20: float
    ma50: float
    ma200: float
    relative_strength: float
    atr14: float
    avg_volume_20: float
    relative_volume: float
    score_breakdown: ScoreBreakdown
    strategy_results: list[StrategyResult]

    def to_dict(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Price": round(self.price, 2),
            "20MA": round(self.ma20, 2),
            "50MA": round(self.ma50, 2),
            "200MA": round(self.ma200, 2),
            "Relative Strength": round(self.relative_strength, 2),
            "ATR14": round(self.atr14, 2),
            "Stop 2ATR": round(self.price - (2 * self.atr14), 2),
            "Avg Volume 20": f"{self.avg_volume_20:,.0f}",
            "Relative Volume": round(self.relative_volume, 2),
            "Trend Score": self.score_breakdown.trend_score,
            "RS Score": self.score_breakdown.relative_strength_score,
            "Volume Score": self.score_breakdown.volume_score,
            "Volatility Score": self.score_breakdown.volatility_score,
            "Score": self.score_breakdown.total_score,
            "Pullback: Price > 200MA": self.strategy_check("Pullback Strategy", "Price > 200MA"),
            "Pullback: 50MA > 200MA": self.strategy_check("Pullback Strategy", "50MA > 200MA"),
            "Pullback: Near 20MA ≤ 3%": self.strategy_check("Pullback Strategy", "Near 20MA ≤ 3%"),
            "Pullback: Relative Volume ≥ 1": self.strategy_check("Pullback Strategy", "Relative Volume ≥ 1"),
            "Pullback: Relative Strength > 0": self.strategy_check("Pullback Strategy", "Relative Strength > 0"),
            "Pullback Strategy": "YES" if self.strategy_triggered("Pullback Strategy") else "NO",
            "Breakout: Near 52W High": self.strategy_check("Breakout Strategy", "Near 52-Week High"),
            "Breakout: Price > 50MA": self.strategy_check("Breakout Strategy", "Price > 50MA"),
            "Breakout: Price > 200MA": self.strategy_check("Breakout Strategy", "Price > 200MA"),
            "Breakout: Relative Volume ≥ 1.2": self.strategy_check("Breakout Strategy", "Relative Volume ≥ 1.2"),
            "Breakout: Relative Strength > 0": self.strategy_check("Breakout Strategy", "Relative Strength > 0"),
            "Breakout Strategy": self.strategy_triggered("Breakout Strategy")
        }
    
    def strategy_triggered(self, strategy_name: str) -> bool:
        return any(
            result.name == strategy_name and result.triggered
            for result in self.strategy_results
        )
    
    def strategy_check(self, strategy_name: str, check_name: str) -> str:
        for result in self.strategy_results:
            if result.name == strategy_name:
                return "YES" if result.checks.get(check_name, False) else "NO"

        return "NO"
    
    def strategy_triggered(self, strategy_name: str) -> str:
        for result in self.strategy_results:
            if result.name == strategy_name:
                return "YES" if result.triggered else "NO"

        return "NO"
