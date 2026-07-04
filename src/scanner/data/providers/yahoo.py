from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
import yfinance as yf
from yfinance._http import new_session

from scanner.data.providers.base import MarketDataProvider


@dataclass(frozen=True)
class YahooMarketDataProvider(MarketDataProvider):
    name: str = "yahoo"

    @lru_cache(maxsize=1)
    def _session(self):
        return new_session()

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        return yf.download(
            ticker,
            period=period,
            progress=True,
            session=self._session(),
        )
