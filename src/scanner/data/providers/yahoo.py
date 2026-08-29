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

    def download_price_data(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        return yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            session=self._session(),
        )

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        normalized_tickers = [ticker.upper() for ticker in tickers]

        if not normalized_tickers:
            return {}

        if len(normalized_tickers) == 1:
            ticker = normalized_tickers[0]
            return {
                ticker: self.download_price_data(ticker=ticker, period=period)
            }

        history = yf.download(
            tickers=" ".join(normalized_tickers),
            period=period,
            group_by="ticker",
            progress=False,
            session=self._session(),
        )

        return _split_batch_history(history, normalized_tickers)

    def provider_call_count_for_batch(self, tickers: list[str]) -> int:
        return 1 if tickers else 0


def _split_batch_history(
    history: pd.DataFrame,
    tickers: list[str],
) -> dict[str, pd.DataFrame]:
    if history.empty:
        return {ticker: pd.DataFrame() for ticker in tickers}

    if not isinstance(history.columns, pd.MultiIndex):
        return {
            tickers[0]: (
                history.dropna(how="all")
                if len(tickers) == 1
                else pd.DataFrame()
            )
            for ticker in tickers
        }

    results = {}

    for ticker in tickers:
        ticker_history = pd.DataFrame()

        if ticker in history.columns.get_level_values(0):
            ticker_history = history[ticker]
        elif ticker in history.columns.get_level_values(1):
            ticker_history = history.xs(ticker, axis=1, level=1)

        results[ticker] = ticker_history.dropna(how="all")

    return results
