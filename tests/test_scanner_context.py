import pandas as pd

from scanner.config.settings import ScannerSettings
from scanner.context import ScannerContext
from scanner.data import market_data


def create_history(close: float = 100.0):
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=4)
    return pd.DataFrame(
        {
            "Open": [close] * len(dates),
            "High": [close + 1] * len(dates),
            "Low": [close - 1] * len(dates),
            "Close": [close] * len(dates),
            "Adj Close": [close] * len(dates),
            "Volume": [1_000_000] * len(dates),
        },
        index=dates,
    )


class FakeProvider:
    name = "fake_context"

    def __init__(self, history):
        self.history = history
        self.calls = []

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        self.calls.append((ticker, period))
        return self.history

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        self.calls.append((" ".join(tickers), period))
        return {ticker: self.history for ticker in tickers}


def test_scanner_context_can_use_isolated_injected_provider():
    first_provider = FakeProvider(create_history(close=100.0))
    second_provider = FakeProvider(create_history(close=200.0))

    first_context = ScannerContext(market_data_provider=first_provider)
    second_context = ScannerContext(market_data_provider=second_provider)

    first_history = first_context.download_price_data("AAPL", period="5d")
    second_history = second_context.download_price_data("AAPL", period="5d")

    assert first_history["Close"].iloc[-1] == 100.0
    assert second_history["Close"].iloc[-1] == 200.0
    assert first_provider.calls == [("AAPL", "5d")]
    assert second_provider.calls == [("AAPL", "5d")]


def test_scanner_context_builds_isolated_cached_provider(tmp_path):
    provider = FakeProvider(create_history(close=123.0))
    provider_name = "fake_context_cache"
    market_data.register_market_data_provider(provider_name, lambda: provider)

    context = ScannerContext(
        settings=ScannerSettings(
            market_data_provider=provider_name,
            market_data_cache_enabled=True,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        )
    )

    first_history = context.download_price_data("AAPL", period="5d")
    second_history = context.download_price_data("AAPL", period="5d")
    stats = context.get_market_data_cache_stats()
    overview = context.get_market_data_cache_overview()

    assert first_history.equals(second_history)
    assert provider.calls == [("AAPL", "5d")]
    assert stats is not None
    assert stats.misses == 1
    assert stats.hits == 1
    assert overview is not None
    assert overview.cached_tickers == 1
