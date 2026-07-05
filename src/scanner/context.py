from __future__ import annotations

from dataclasses import dataclass, field
import logging

import pandas as pd

from scanner.config.settings import ScannerSettings, settings
from scanner.data.cache import CacheOverview
from scanner.data.market_data import (
    create_market_data_provider,
    download_price_data,
    download_price_data_batch,
)
from scanner.data.providers import CachedMarketDataProvider, MarketDataProvider


@dataclass
class ScannerContext:
    settings: ScannerSettings = field(default_factory=lambda: settings)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("scanner"))
    market_data_provider: MarketDataProvider | None = None
    market_data_cache_enabled: bool | None = None
    market_data_cache_force_refresh: bool = False
    _resolved_market_data_provider: MarketDataProvider | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def get_market_data_provider(self) -> MarketDataProvider:
        if self.market_data_provider is not None:
            return self.market_data_provider

        if self._resolved_market_data_provider is None:
            cache_enabled = (
                self.settings.market_data_cache_enabled
                if self.market_data_cache_enabled is None
                else self.market_data_cache_enabled
            )
            self._resolved_market_data_provider = create_market_data_provider(
                name=self.settings.market_data_provider,
                cache_enabled=cache_enabled,
                force_refresh=self.market_data_cache_force_refresh,
                cache_path=self.settings.market_data_cache_path,
                refresh_overlap_days=self.settings.market_data_refresh_overlap_days,
                retention_years=self.settings.market_data_cache_retention_years,
            )

        return self._resolved_market_data_provider

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        return download_price_data(
            ticker=ticker,
            period=period,
            provider=self.get_market_data_provider(),
        )

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        return download_price_data_batch(
            tickers=tickers,
            period=period,
            provider=self.get_market_data_provider(),
        )

    def get_market_data_cache_stats(self):
        provider = self.get_market_data_provider()

        if isinstance(provider, CachedMarketDataProvider):
            return provider.stats

        return None

    def get_market_data_cache_overview(self) -> CacheOverview | None:
        provider = self.get_market_data_provider()

        if isinstance(provider, CachedMarketDataProvider):
            return provider.cache.overview(provider=provider.name)

        return None
