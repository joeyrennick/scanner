from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        raise NotImplementedError

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        return {
            ticker: self.download_price_data(ticker=ticker, period=period)
            for ticker in tickers
        }
