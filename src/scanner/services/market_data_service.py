from scanner.data.market_data import download_price_data
from scanner.indicators.atr import add_atr
from scanner.indicators.moving_averages import add_moving_averages
from scanner.indicators.volume import add_volume_indicators


class MarketDataService:
    def __init__(self):
        self._cache = {}

    def get_history(self, ticker: str, period: str = "1y"):
        cache_key = (ticker.upper(), period)

        if cache_key in self._cache:
            return self._cache[cache_key]

        history = download_price_data(ticker=ticker, period=period)

        history = add_moving_averages(history)
        history = add_atr(history)
        history = add_volume_indicators(history)

        self._cache[cache_key] = history

        return history