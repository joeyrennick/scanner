import json
import os
import re
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from scanner.data.providers.base import MarketDataProvider


class AlphaVantageMarketDataProvider(MarketDataProvider):
    name: str = "alpha_vantage"
    base_url: str = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        if not self.api_key:
            raise RuntimeError(
                "ALPHA_VANTAGE_API_KEY is required when market_data_provider=alpha_vantage"
            )

        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full",
            "datatype": "json",
            "apikey": self.api_key,
        }
        url = f"{self.base_url}?{urlencode(params)}"

        with urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if "Error Message" in payload:
            raise RuntimeError(payload["Error Message"])

        if "Note" in payload:
            raise RuntimeError(payload["Note"])

        series = payload.get("Time Series (Daily)")
        if not series:
            raise RuntimeError("Alpha Vantage response did not include daily price data")

        history = pd.DataFrame.from_dict(series, orient="index")
        history.index = pd.to_datetime(history.index)
        history = history.sort_index()
        history = history.rename(
            columns={
                "1. open": "Open",
                "2. high": "High",
                "3. low": "Low",
                "4. close": "Close",
                "5. adjusted close": "Adj Close",
                "6. volume": "Volume",
                "7. dividend amount": "Dividends",
                "8. split coefficient": "Stock Splits",
            }
        )

        for column in [
            "Open",
            "High",
            "Low",
            "Close",
            "Adj Close",
            "Volume",
            "Dividends",
            "Stock Splits",
        ]:
            if column in history.columns:
                history[column] = pd.to_numeric(history[column], errors="coerce")

        history = _apply_period(history, period)

        return history


def _apply_period(history: pd.DataFrame, period: str) -> pd.DataFrame:
    if period == "max":
        return history

    match = re.fullmatch(r"(\d+)(d|w|mo|y)", period)
    if not match:
        return history

    quantity = int(match.group(1))
    unit = match.group(2)

    offsets = {
        "d": pd.DateOffset(days=quantity),
        "w": pd.DateOffset(weeks=quantity),
        "mo": pd.DateOffset(months=quantity),
        "y": pd.DateOffset(years=quantity),
    }

    cutoff = history.index.max() - offsets[unit]
    return history.loc[history.index >= cutoff]
