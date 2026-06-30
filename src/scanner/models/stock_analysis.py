from dataclasses import dataclass
from scanner.scoring.score_engine import ScoreBreakdown


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
        }