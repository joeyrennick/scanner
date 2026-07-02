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
    def ma150(self) -> float:
        return self.history["Close"].rolling(window=150).mean().iloc[-1].item()

    @property
    def ma200(self) -> float:
        return self.latest["MA200"].item()

    @property
    def ma200_20_days_ago(self) -> float:
        return self.history["MA200"].iloc[-20].item()

    @property
    def ma200_rising(self) -> bool:
        return self.ma200 > self.ma200_20_days_ago

    @property
    def high_52_week(self) -> float:
        return self.history["High"].tail(252).max().item()

    @property
    def low_52_week(self) -> float:
        return self.history["Low"].tail(252).min().item()

    @property
    def percent_above_52_week_low(self) -> float:
        return ((self.price - self.low_52_week) / self.low_52_week) * 100

    @property
    def percent_below_52_week_high(self) -> float:
        return ((self.high_52_week - self.price) / self.high_52_week) * 100

    @property
    def atr14(self) -> float:
        return self.latest["ATR14"].item()

    @property
    def avg_volume_20(self) -> float:
        return self.latest["AvgVolume20"].item()

    @property
    def relative_volume(self) -> float:
        return self.latest["RelativeVolume"].item()