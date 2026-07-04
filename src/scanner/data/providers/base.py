from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        raise NotImplementedError
