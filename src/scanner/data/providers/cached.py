from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from typing import Callable

import pandas as pd

from scanner.data.cache import CacheFetchRequest, SQLiteMarketDataCache
from scanner.data.providers.base import MarketDataProvider

START_COVERAGE_GRACE_DAYS = 4


@dataclass
class MarketDataCacheStats:
    hits: int = 0
    misses: int = 0
    provider_calls: int = 0
    rows_loaded_from_cache: int = 0
    rows_fetched_from_provider: int = 0


@dataclass(frozen=True)
class CacheRequirement:
    ticker: str
    cached_rows: int
    needs_provider: bool
    fetch_period: str
    reason: str


class CachedMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        provider: MarketDataProvider,
        cache: SQLiteMarketDataCache,
        refresh_overlap_days: int = 10,
        retention_years: int | None = None,
        force_refresh: bool = False,
        enabled: bool = True,
        now: Callable[[], datetime] | None = None,
    ):
        self.provider = provider
        self.cache = cache
        self.refresh_overlap_days = refresh_overlap_days
        self.retention_years = retention_years
        self.force_refresh = force_refresh
        self.enabled = enabled
        self.now = now or datetime.now
        self.stats = MarketDataCacheStats()
        self.name = getattr(provider, "name", provider.__class__.__name__).lower()

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        if not self.enabled:
            return self._fetch_from_provider(ticker=ticker, period=period)

        interval = "1d"
        today = self.now().date()
        start_date = period_start_date(period=period, today=today)
        request = CacheFetchRequest(
            provider=self.name,
            ticker=ticker,
            interval=interval,
            period=period,
            start_date=start_date,
            end_date=None,
            auto_adjust=True,
        )
        cached_history = self.cache.load_history(
            provider=self.name,
            ticker=ticker,
            interval=interval,
            start_date=start_date,
        )

        if not self.force_refresh and self._can_use_cache(cached_history, request):
            self.stats.hits += 1
            self.stats.rows_loaded_from_cache += len(cached_history)
            return cached_history

        self.stats.misses += 1

        fetch_period = self._refresh_period(
            cached_history=cached_history,
            requested_period=period,
            requested_start_date=start_date,
        )

        try:
            fetched_history = self._fetch_from_provider(
                ticker=ticker,
                period=fetch_period,
            )
        except Exception as error:
            self.cache.record_fetch(
                request=request,
                status="error",
                error_message=str(error),
            )
            raise

        rows_stored = self.cache.store_history(
            provider=self.name,
            ticker=ticker,
            interval=interval,
            history=fetched_history,
        )
        self._prune_retained_history(ticker=ticker, interval=interval)
        self.cache.record_fetch(
            request=request,
            status="success",
            rows_returned=rows_stored,
        )

        refreshed_history = self.cache.load_history(
            provider=self.name,
            ticker=ticker,
            interval=interval,
            start_date=start_date,
        )
        return refreshed_history if not refreshed_history.empty else fetched_history

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        if not self.enabled:
            return self._fetch_batch_from_provider(tickers=tickers, period=period)

        interval = "1d"
        today = self.now().date()
        start_date = period_start_date(period=period, today=today)
        results: dict[str, pd.DataFrame] = {}
        misses_by_fetch_period: dict[str, list[tuple[str, CacheFetchRequest]]] = {}

        for ticker in tickers:
            request = CacheFetchRequest(
                provider=self.name,
                ticker=ticker,
                interval=interval,
                period=period,
                start_date=start_date,
                end_date=None,
                auto_adjust=True,
            )
            cached_history = self.cache.load_history(
                provider=self.name,
                ticker=ticker,
                interval=interval,
                start_date=start_date,
            )

            if not self.force_refresh and self._can_use_cache(cached_history, request):
                self.stats.hits += 1
                self.stats.rows_loaded_from_cache += len(cached_history)
                results[ticker] = cached_history
                continue

            self.stats.misses += 1
            fetch_period = self._refresh_period(
                cached_history=cached_history,
                requested_period=period,
                requested_start_date=start_date,
            )
            misses_by_fetch_period.setdefault(fetch_period, []).append((ticker, request))

        for fetch_period, misses in misses_by_fetch_period.items():
            miss_tickers = [ticker for ticker, _request in misses]

            try:
                fetched_histories = self._fetch_batch_from_provider(
                    tickers=miss_tickers,
                    period=fetch_period,
                )
            except Exception as error:
                for _ticker, request in misses:
                    self.cache.record_fetch(
                        request=request,
                        status="error",
                        error_message=str(error),
                    )
                raise

            for ticker, request in misses:
                fetched_history = fetched_histories.get(ticker, pd.DataFrame())
                rows_stored = self.cache.store_history(
                    provider=self.name,
                    ticker=ticker,
                    interval=interval,
                    history=fetched_history,
                )
                self._prune_retained_history(ticker=ticker, interval=interval)
                self.cache.record_fetch(
                    request=request,
                    status="success",
                    rows_returned=rows_stored,
                )

                refreshed_history = self.cache.load_history(
                    provider=self.name,
                    ticker=ticker,
                    interval=interval,
                    start_date=start_date,
                )
                results[ticker] = (
                    refreshed_history
                    if not refreshed_history.empty
                    else fetched_history
                )

        return {ticker: results.get(ticker, pd.DataFrame()) for ticker in tickers}

    def cache_requirement(self, ticker: str, period: str = "1y") -> CacheRequirement:
        interval = "1d"
        today = self.now().date()
        start_date = period_start_date(period=period, today=today)
        request = CacheFetchRequest(
            provider=self.name,
            ticker=ticker,
            interval=interval,
            period=period,
            start_date=start_date,
            end_date=None,
            auto_adjust=True,
        )
        cached_history = self.cache.load_history(
            provider=self.name,
            ticker=ticker,
            interval=interval,
            start_date=start_date,
        )

        fetch_period = self._refresh_period(
            cached_history=cached_history,
            requested_period=period,
            requested_start_date=start_date,
        )

        if not self.enabled:
            return CacheRequirement(
                ticker=ticker,
                cached_rows=len(cached_history),
                needs_provider=True,
                fetch_period=fetch_period,
                reason="cache_disabled",
            )

        if self.force_refresh:
            return CacheRequirement(
                ticker=ticker,
                cached_rows=len(cached_history),
                needs_provider=True,
                fetch_period=fetch_period,
                reason="force_refresh",
            )

        if self._can_use_cache(cached_history, request):
            return CacheRequirement(
                ticker=ticker,
                cached_rows=len(cached_history),
                needs_provider=False,
                fetch_period=fetch_period,
                reason="fresh_cache",
            )

        reason = "missing_cache" if cached_history.empty else "stale_cache"
        if start_date is not None and not cached_history.empty:
            if not cache_covers_start(cached_history, start_date):
                reason = "incomplete_cache"

        return CacheRequirement(
            ticker=ticker,
            cached_rows=len(cached_history),
            needs_provider=True,
            fetch_period=fetch_period,
            reason=reason,
        )

    def cache_requirements(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> list[CacheRequirement]:
        return [
            self.cache_requirement(ticker=ticker, period=period)
            for ticker in tickers
        ]

    def _fetch_from_provider(self, ticker: str, period: str) -> pd.DataFrame:
        self.stats.provider_calls += 1
        history = self.provider.download_price_data(ticker=ticker, period=period)
        self.stats.rows_fetched_from_provider += len(history)
        return history

    def _fetch_batch_from_provider(
        self,
        tickers: list[str],
        period: str,
    ) -> dict[str, pd.DataFrame]:
        if not tickers:
            return {}

        self.stats.provider_calls += 1
        histories = self.provider.download_price_data_batch(
            tickers=tickers,
            period=period,
        )
        self.stats.rows_fetched_from_provider += sum(
            len(history) for history in histories.values()
        )
        return histories

    def _refresh_period(
        self,
        cached_history: pd.DataFrame,
        requested_period: str,
        requested_start_date: date | None,
    ) -> str:
        if self.force_refresh:
            return requested_period

        if cached_history.empty or requested_start_date is None:
            return requested_period

        if not cache_covers_start(cached_history, requested_start_date):
            return requested_period

        overlap_days = max(1, self.refresh_overlap_days)
        return f"{overlap_days}d"

    def _prune_retained_history(self, ticker: str, interval: str) -> None:
        if self.retention_years is None:
            return

        if self.retention_years <= 0:
            return

        cutoff_date = (
            pd.Timestamp(self.now().date())
            - pd.DateOffset(years=self.retention_years)
        ).date()
        self.cache.prune_price_bars_before(
            provider=self.name,
            ticker=ticker,
            interval=interval,
            cutoff_date=cutoff_date,
        )

    def _can_use_cache(
        self,
        cached_history: pd.DataFrame,
        request: CacheFetchRequest,
    ) -> bool:
        if cached_history.empty:
            return False

        if request.start_date is not None and not cache_covers_start(
            cached_history,
            request.start_date,
        ):
            return False

        today = self.now().date()

        if self.cache.has_successful_fetch_today(request=request, today=today):
            return True

        return cache_covers_latest(cached_history, self.now())


def period_start_date(period: str, today: date) -> date | None:
    if period == "max":
        return None

    match = re.fullmatch(r"(\d+)(d|w|mo|y)", period)

    if not match:
        return None

    quantity = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return today - timedelta(days=quantity)
    if unit == "w":
        return today - timedelta(weeks=quantity)
    if unit == "mo":
        return (pd.Timestamp(today) - pd.DateOffset(months=quantity)).date()
    if unit == "y":
        return (pd.Timestamp(today) - pd.DateOffset(years=quantity)).date()

    return None


def cache_covers_start(
    cached_history: pd.DataFrame,
    requested_start_date: date,
) -> bool:
    earliest_cached_date = cached_history.index.min().date()

    if earliest_cached_date <= requested_start_date:
        return True

    latest_acceptable_start = requested_start_date + timedelta(
        days=START_COVERAGE_GRACE_DAYS
    )
    return earliest_cached_date <= latest_acceptable_start


def cache_covers_latest(
    cached_history: pd.DataFrame,
    now: datetime,
) -> bool:
    latest_cached_date = cached_history.index.max().date()
    earliest_acceptable_latest = latest_required_bar_date(now) - timedelta(
        days=START_COVERAGE_GRACE_DAYS
    )
    return latest_cached_date >= earliest_acceptable_latest


def latest_required_bar_date(now: datetime) -> date:
    market_close = time(18, 0)
    candidate = now.date()

    if now.weekday() < 5 and now.time() < market_close:
        candidate = candidate - timedelta(days=1)

    while candidate.weekday() >= 5:
        candidate = candidate - timedelta(days=1)

    return candidate
