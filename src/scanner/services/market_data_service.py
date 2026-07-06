from datetime import date

from scanner.config.settings import settings
from scanner.data.cache import SQLiteMarketDataCache
from scanner.data.market_data import download_price_data
from scanner.data.providers.cached import period_start_date
from scanner.indicators.atr import add_atr
from scanner.indicators.moving_averages import add_moving_averages
from scanner.indicators.volume import add_volume_indicators


class MarketDataService:
    def __init__(self, cache_only: bool = False):
        self._cache = {}
        self.cache_only = cache_only
        self.market_data_cache = SQLiteMarketDataCache(settings.market_data_cache_path)

    def get_history(self, ticker: str, period: str = "1y"):
        cache_key = (ticker.upper(), period)

        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.cache_only:
            history = self.market_data_cache.load_history(
                provider=settings.market_data_provider,
                ticker=ticker,
                interval="1d",
                start_date=period_start_date(period, date.today()),
            )
        else:
            history = download_price_data(ticker=ticker, period=period)

        if history.empty:
            self._cache[cache_key] = history
            return history

        history = add_moving_averages(history)
        history = add_atr(history)
        history = add_volume_indicators(history)

        self._cache[cache_key] = history

        return history
