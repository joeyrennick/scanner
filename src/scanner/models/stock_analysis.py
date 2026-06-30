from dataclasses import dataclass


@dataclass
class StockAnalysis:
    ticker: str
    price: float
    ma20: float
    ma50: float
    ma200: float
    relative_strength: float
    atr14: float
    score: int

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
            "Score": self.score,
        }