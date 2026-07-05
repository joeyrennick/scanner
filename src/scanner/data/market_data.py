from dataclasses import dataclass
from functools import lru_cache
import random
import time
from typing import Callable

import pandas as pd
from yfinance.exceptions import YFRateLimitError

from scanner.config.settings import settings
from scanner.data.cache import CacheOverview, SQLiteMarketDataCache
from scanner.data.providers import (
    AlphaVantageMarketDataProvider,
    CachedMarketDataProvider,
    MarketDataProvider,
    YahooMarketDataProvider,
)


@dataclass(frozen=True)
class MarketDataConnectivityResult:
    ticker: str
    period: str
    rows: int
    elapsed_seconds: float
    first_timestamp: str | None
    last_timestamp: str | None


MAX_DOWNLOAD_ATTEMPTS = 4
BASE_RETRY_DELAY_SECONDS = 1.5
RETRYABLE_ERROR_PATTERNS = (
    "Too Many Requests",
    "Rate limited",
    "rate limit",
    "429",
)

_ACTIVE_PROVIDER_NAME = settings.market_data_provider
_CACHE_ENABLED = settings.market_data_cache_enabled
_CACHE_FORCE_REFRESH = False
_CACHE_PATH = settings.market_data_cache_path
_CACHE_RETENTION_YEARS = settings.market_data_cache_retention_years
_CACHE_REFRESH_OVERLAP_DAYS = settings.market_data_refresh_overlap_days
_PROVIDER_FACTORIES: dict[str, Callable[[], MarketDataProvider]] = {
    "yahoo": YahooMarketDataProvider,
    "alpha_vantage": AlphaVantageMarketDataProvider,
}


def register_market_data_provider(
    name: str,
    factory: Callable[[], MarketDataProvider],
) -> None:
    _PROVIDER_FACTORIES[name.lower()] = factory
    _get_market_data_provider.cache_clear()


def configure_market_data_provider(name: str) -> None:
    normalized = name.lower()

    if normalized not in _PROVIDER_FACTORIES:
        supported = ", ".join(sorted(_PROVIDER_FACTORIES))
        raise ValueError(
            f"Unsupported market data provider: {name}. Supported: {supported}"
        )

    global _ACTIVE_PROVIDER_NAME
    _ACTIVE_PROVIDER_NAME = normalized
    _get_market_data_provider.cache_clear()


def configure_market_data_cache(
    enabled: bool | None = None,
    force_refresh: bool | None = None,
    cache_path: str | None = None,
    retention_years: int | None = None,
) -> None:
    global _CACHE_ENABLED, _CACHE_FORCE_REFRESH, _CACHE_PATH, _CACHE_RETENTION_YEARS

    if enabled is not None:
        _CACHE_ENABLED = enabled

    if force_refresh is not None:
        _CACHE_FORCE_REFRESH = force_refresh

    if cache_path is not None:
        _CACHE_PATH = cache_path

    if retention_years is not None:
        _CACHE_RETENTION_YEARS = retention_years

    _get_market_data_provider.cache_clear()
    _get_market_data_cache.cache_clear()


def get_market_data_provider(
    provider: str | MarketDataProvider | None = None,
) -> MarketDataProvider:
    if provider is None:
        return _get_market_data_provider(_ACTIVE_PROVIDER_NAME)

    if isinstance(provider, str):
        return _get_market_data_provider(provider.lower())

    return provider


@lru_cache(maxsize=None)
def _get_market_data_provider(provider_name: str) -> MarketDataProvider:
    return create_market_data_provider(
        name=provider_name,
        cache_enabled=_CACHE_ENABLED,
        force_refresh=_CACHE_FORCE_REFRESH,
        cache_path=_CACHE_PATH,
        refresh_overlap_days=_CACHE_REFRESH_OVERLAP_DAYS,
    )


def create_market_data_provider(
    name: str,
    cache_enabled: bool | None = None,
    force_refresh: bool = False,
    cache_path: str | None = None,
    refresh_overlap_days: int | None = None,
    retention_years: int | None = None,
) -> MarketDataProvider:
    provider_name = name.lower()
    factory = _PROVIDER_FACTORIES.get(provider_name)

    if factory is None:
        supported = ", ".join(sorted(_PROVIDER_FACTORIES))
        raise ValueError(
            f"Unsupported market data provider: {name}. Supported: {supported}"
        )

    provider = factory()
    resolved_cache_enabled = _CACHE_ENABLED if cache_enabled is None else cache_enabled

    if not resolved_cache_enabled:
        return provider

    return CachedMarketDataProvider(
        provider=provider,
        cache=SQLiteMarketDataCache(cache_path or _CACHE_PATH),
        refresh_overlap_days=(
            _CACHE_REFRESH_OVERLAP_DAYS
            if refresh_overlap_days is None
            else refresh_overlap_days
        ),
        retention_years=(
            _CACHE_RETENTION_YEARS if retention_years is None else retention_years
        ),
        force_refresh=force_refresh,
        enabled=resolved_cache_enabled,
    )


@lru_cache(maxsize=None)
def _get_market_data_cache(cache_path: str) -> SQLiteMarketDataCache:
    return SQLiteMarketDataCache(cache_path)


def get_market_data_cache_stats():
    provider = get_market_data_provider()

    if isinstance(provider, CachedMarketDataProvider):
        return provider.stats

    return None


def get_market_data_cache_overview() -> CacheOverview | None:
    if not _CACHE_ENABLED:
        return None

    return _get_market_data_cache(_CACHE_PATH).overview(provider=_ACTIVE_PROVIDER_NAME)


def download_price_data(
    ticker: str,
    period: str = "1y",
    provider: str | MarketDataProvider | None = None,
) -> pd.DataFrame:
    last_error = None
    market_data_provider = get_market_data_provider(provider)

    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            return market_data_provider.download_price_data(ticker=ticker, period=period)
        except Exception as error:
            if not _should_retry(error) or attempt == MAX_DOWNLOAD_ATTEMPTS:
                raise

            last_error = error
            delay_seconds = BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
            delay_seconds += random.uniform(0, 0.5)
            time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError("Failed to download market data")


def download_price_data_batch(
    tickers: list[str],
    period: str = "1y",
    provider: str | MarketDataProvider | None = None,
) -> dict[str, pd.DataFrame]:
    last_error = None
    market_data_provider = get_market_data_provider(provider)

    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            return market_data_provider.download_price_data_batch(
                tickers=tickers,
                period=period,
            )
        except Exception as error:
            if not _should_retry(error) or attempt == MAX_DOWNLOAD_ATTEMPTS:
                raise

            last_error = error
            delay_seconds = BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
            delay_seconds += random.uniform(0, 0.5)
            time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError("Failed to download market data")


def check_market_data_connectivity(
    ticker: str = "SPY",
    period: str = "5d",
    provider: str | MarketDataProvider | None = None,
) -> MarketDataConnectivityResult:
    started_at = time.perf_counter()
    history = download_price_data(ticker=ticker, period=period, provider=provider)
    elapsed_seconds = time.perf_counter() - started_at

    if history.empty:
        raise RuntimeError(
            f"No rows returned for {ticker} over period {period}; market data connectivity is not healthy"
        )

    first_timestamp = history.index[0].isoformat() if len(history.index) else None
    last_timestamp = history.index[-1].isoformat() if len(history.index) else None

    return MarketDataConnectivityResult(
        ticker=ticker,
        period=period,
        rows=len(history),
        elapsed_seconds=elapsed_seconds,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
    )


def _should_retry(error: Exception) -> bool:
    if isinstance(error, YFRateLimitError):
        return True

    message = str(error)
    return any(pattern in message for pattern in RETRYABLE_ERROR_PATTERNS)
