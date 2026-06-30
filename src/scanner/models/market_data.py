from dataclasses import dataclass
import pandas as pd


@dataclass
class MarketData:
    ticker: str
    history: pd.DataFrame

    @property
    def latest(self) -> pd.Series:
        return self.history.iloc[-1]

    @property
    def price(self) -> float:
        return self.latest["Close"].item()

    @property
    def ma20(self) -> float:
        return self.latest["MA20"].item()

    @property
    def ma50(self) -> float:
        return self.latest["MA50"].item()

    @property
    def ma200(self) -> float:
        return self.latest["MA200"].item()

    @property
    def atr14(self) -> float:
        return self.latest["ATR14"].item()

    @property
    def avg_volume_20(self) -> float:
        return self.latest["AvgVolume20"].item()

    @property
    def relative_volume(self) -> float:
        return self.latest["RelativeVolume"].item()