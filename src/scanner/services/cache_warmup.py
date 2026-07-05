from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Callable

import pandas as pd

from scanner.config.settings import settings
from scanner.context import ScannerContext
from scanner.data.providers import CachedMarketDataProvider


RATE_LIMIT_PATTERNS = (
    "Too Many Requests",
    "Rate limited",
    "rate limit",
    "YFRateLimitError",
    "429",
)


@dataclass(frozen=True)
class CacheWarmupConfig:
    tickers: list[str]
    period: str = settings.scan_history_period
    batch_size: int = settings.cache_warmup_batch_size
    batch_delay_seconds: float = settings.cache_warmup_batch_delay_seconds
    max_provider_batches: int | None = settings.cache_warmup_max_provider_batches
    cache_only_preview: bool = False
    stop_on_rate_limit: bool = settings.cache_warmup_stop_on_rate_limit


@dataclass(frozen=True)
class CacheWarmupTickerStatus:
    ticker: str
    status: str
    rows: int = 0
    fetch_period: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CacheWarmupResult:
    statuses: list[CacheWarmupTickerStatus]
    period: str
    batch_size: int
    provider_batches_allowed: int | None
    provider_batches_planned: int
    provider_batches_attempted: int
    provider_symbols_planned: int
    provider_symbols_attempted: int
    provider_calls_before: int
    provider_calls_after: int
    stopped_for_rate_limit: bool
    cache_only_preview: bool
    elapsed_seconds: float

    @property
    def cached_count(self) -> int:
        return sum(1 for status in self.statuses if status.status == "cached")

    @property
    def fetched_count(self) -> int:
        return sum(1 for status in self.statuses if status.status == "fetched")

    @property
    def available_count(self) -> int:
        return sum(
            1
            for status in self.statuses
            if status.status in {"cached", "fetched"}
        )

    @property
    def skipped_count(self) -> int:
        return sum(
            1
            for status in self.statuses
            if status.status.startswith("skipped") or status.status == "empty"
        )

    @property
    def provider_calls_attempted(self) -> int:
        return self.provider_calls_after - self.provider_calls_before

    @property
    def available_tickers(self) -> list[str]:
        return [
            status.ticker
            for status in self.statuses
            if status.status in {"cached", "fetched"}
        ]

    def summary(self) -> str:
        return (
            "Cache warmup: "
            f"available={self.available_count}, "
            f"cached={self.cached_count}, "
            f"fetched={self.fetched_count}, "
            f"skipped={self.skipped_count}, "
            f"provider_batches={self.provider_batches_attempted}/"
            f"{self.provider_batches_planned}, "
            f"provider_calls={self.provider_calls_attempted}, "
            f"rate_limit_stopped={self.stopped_for_rate_limit}, "
            f"elapsed={self.elapsed_seconds:.2f}s"
        )


class CacheWarmupService:
    def __init__(
        self,
        context: ScannerContext | None = None,
        logger: logging.Logger | None = None,
        progress_callback: Callable[..., None] | None = None,
    ):
        self.context = context or ScannerContext()
        self.logger = logger or self.context.logger
        self.progress_callback = progress_callback

    def run(self, config: CacheWarmupConfig) -> CacheWarmupResult:
        if config.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        if config.max_provider_batches is not None and config.max_provider_batches < 0:
            raise ValueError("max_provider_batches cannot be negative")

        if config.batch_delay_seconds < 0:
            raise ValueError("batch_delay_seconds cannot be negative")

        started_at = time.perf_counter()
        provider = self.context.get_market_data_provider()
        stats = self.context.get_market_data_cache_stats()
        provider_calls_before = stats.provider_calls if stats is not None else 0
        statuses_by_ticker: dict[str, CacheWarmupTickerStatus] = {}
        unique_tickers = _dedupe_tickers(config.tickers)

        if isinstance(provider, CachedMarketDataProvider):
            requirements = provider.cache_requirements(
                tickers=unique_tickers,
                period=config.period,
            )
            provider_tickers = []

            for requirement in requirements:
                if requirement.needs_provider:
                    provider_tickers.append(requirement.ticker)
                    continue

                statuses_by_ticker[requirement.ticker] = CacheWarmupTickerStatus(
                    ticker=requirement.ticker,
                    status="cached",
                    rows=requirement.cached_rows,
                    fetch_period=requirement.fetch_period,
                    reason=requirement.reason,
                )
        else:
            provider_tickers = unique_tickers

        provider_batches = _chunks(provider_tickers, config.batch_size)
        provider_batches_planned = len(provider_batches)

        if config.max_provider_batches is not None:
            allowed_batches = provider_batches[: config.max_provider_batches]
            skipped_batches = provider_batches[config.max_provider_batches :]
        else:
            allowed_batches = provider_batches
            skipped_batches = []

        for batch in skipped_batches:
            for ticker in batch:
                statuses_by_ticker[ticker] = CacheWarmupTickerStatus(
                    ticker=ticker,
                    status="skipped_limit",
                    reason="Provider batch limit reached",
                )

        self._progress(
            current_step="Planning cache warmup",
            total_steps=len(allowed_batches),
            symbols_total=len(unique_tickers),
            symbols_checked=len(statuses_by_ticker),
            symbols_kept=sum(
                1
                for status in statuses_by_ticker.values()
                if status.status == "cached"
            ),
            symbols_skipped=sum(
                1
                for status in statuses_by_ticker.values()
                if status.status.startswith("skipped")
            ),
            provider_batches_attempted=0,
            provider_batch_limit=config.max_provider_batches,
            provider_symbols_attempted=0,
            provider_symbol_limit=None,
            rate_limited=False,
            message="Planning cache warmup",
        )

        if config.cache_only_preview:
            for batch in allowed_batches:
                for ticker in batch:
                    statuses_by_ticker[ticker] = CacheWarmupTickerStatus(
                        ticker=ticker,
                        status="skipped_preview",
                        reason="Would require provider data",
                    )

            self._progress(
                current_step="Cache-only preview complete",
                symbols_checked=len(unique_tickers),
                symbols_kept=sum(
                    1
                    for status in statuses_by_ticker.values()
                    if status.status == "cached"
                ),
                symbols_skipped=sum(
                    1
                    for status in statuses_by_ticker.values()
                    if status.status.startswith("skipped")
                ),
                provider_batches_attempted=0,
                provider_symbols_attempted=0,
                message="Cache-only preview complete",
            )
            return self._result(
                config=config,
                statuses_by_ticker=statuses_by_ticker,
                unique_tickers=unique_tickers,
                provider_batches_planned=provider_batches_planned,
                provider_batches_attempted=0,
                provider_symbols_planned=len(provider_tickers),
                provider_symbols_attempted=0,
                provider_calls_before=provider_calls_before,
                stopped_for_rate_limit=False,
                started_at=started_at,
            )

        provider_batches_attempted = 0
        provider_symbols_attempted = 0
        stopped_for_rate_limit = False

        if allowed_batches:
            self.logger.info(
                "Cache warmup needs provider data for "
                f"{sum(len(batch) for batch in allowed_batches)} symbols in "
                f"{len(allowed_batches)} batches of up to {config.batch_size}. "
                f"Minimum configured delay: "
                f"{_format_seconds(max(0, len(allowed_batches) - 1) * config.batch_delay_seconds)}."
            )

        for batch_number, batch in enumerate(allowed_batches, start=1):
            provider_batches_attempted += 1
            provider_symbols_attempted += len(batch)
            self._progress(
                current_step="Fetching cache warmup batch",
                provider_batches_attempted=provider_batches_attempted,
                provider_symbols_attempted=provider_symbols_attempted,
                symbols_checked=len(statuses_by_ticker),
                message=(
                    f"Fetching cache warmup batch "
                    f"{batch_number}/{len(allowed_batches)}"
                ),
            )

            try:
                histories = self.context.download_price_data_batch(
                    tickers=batch,
                    period=config.period,
                )
            except Exception as error:
                reason = str(error)
                stopped_for_rate_limit = _is_rate_limit_error(reason)

                for ticker in batch:
                    statuses_by_ticker[ticker] = CacheWarmupTickerStatus(
                        ticker=ticker,
                        status="skipped_rate_limit" if stopped_for_rate_limit else "error",
                        reason=reason,
                    )

                if stopped_for_rate_limit and config.stop_on_rate_limit:
                    self._mark_remaining_rate_limited(
                        statuses_by_ticker=statuses_by_ticker,
                        provider_batches=allowed_batches[batch_number:],
                    )
                    self.logger.warning(
                        "Cache warmup stopped after a provider rate-limit response. "
                        "Rerun later to resume from the cache."
                    )
                    self._progress(
                        current_step="Stopped for rate limit",
                        symbols_checked=len(statuses_by_ticker),
                        symbols_skipped=sum(
                            1
                            for status in statuses_by_ticker.values()
                            if status.status.startswith("skipped")
                        ),
                        rate_limited=True,
                        message="Stopped for rate limit",
                    )
                    break

                raise

            for ticker in batch:
                history = histories.get(ticker, pd.DataFrame())
                statuses_by_ticker[ticker] = CacheWarmupTickerStatus(
                    ticker=ticker,
                    status="fetched" if not history.empty else "empty",
                    rows=len(history),
                    reason=None if not history.empty else "No rows returned",
                )

            if config.stop_on_rate_limit and _entire_batch_empty(
                batch,
                statuses_by_ticker,
            ):
                stopped_for_rate_limit = True
                self._mark_remaining_rate_limited(
                    statuses_by_ticker=statuses_by_ticker,
                    provider_batches=allowed_batches[batch_number:],
                )
                self.logger.warning(
                    "Cache warmup stopped after a provider batch returned no "
                    "price rows. This is treated as a possible rate-limit response."
                )
                self._progress(
                    current_step="Stopped for possible rate limit",
                    symbols_checked=len(statuses_by_ticker),
                    symbols_skipped=sum(
                        1
                        for status in statuses_by_ticker.values()
                        if status.status.startswith("skipped")
                        or status.status == "empty"
                    ),
                    rate_limited=True,
                    message="Stopped for possible rate limit",
                )
                break

            self.logger.info(
                f"Cache warmup batch {batch_number}/{len(allowed_batches)} "
                f"finished: symbols={len(batch)}, "
                f"elapsed={_format_seconds(time.perf_counter() - started_at)}"
            )
            self._progress(
                current_step="Cache warmup batch complete",
                symbols_checked=len(statuses_by_ticker),
                symbols_kept=sum(
                    1
                    for status in statuses_by_ticker.values()
                    if status.status in {"cached", "fetched"}
                ),
                symbols_skipped=sum(
                    1
                    for status in statuses_by_ticker.values()
                    if status.status.startswith("skipped")
                    or status.status == "empty"
                ),
                message=(
                    f"Cache warmup batch {batch_number}/"
                    f"{len(allowed_batches)} complete"
                ),
            )

            if (
                batch_number < len(allowed_batches)
                and config.batch_delay_seconds > 0
            ):
                time.sleep(config.batch_delay_seconds)

        result = self._result(
            config=config,
            statuses_by_ticker=statuses_by_ticker,
            unique_tickers=unique_tickers,
            provider_batches_planned=provider_batches_planned,
            provider_batches_attempted=provider_batches_attempted,
            provider_symbols_planned=len(provider_tickers),
            provider_symbols_attempted=provider_symbols_attempted,
            provider_calls_before=provider_calls_before,
            stopped_for_rate_limit=stopped_for_rate_limit,
            started_at=started_at,
        )
        self._progress(
            current_step="Cache warmup complete",
            symbols_checked=len(unique_tickers),
            symbols_kept=result.available_count,
            symbols_skipped=result.skipped_count,
            provider_batches_attempted=result.provider_batches_attempted,
            provider_symbols_attempted=result.provider_symbols_attempted,
            rate_limited=result.stopped_for_rate_limit,
            message="Cache warmup complete",
        )
        return result

    def _result(
        self,
        config: CacheWarmupConfig,
        statuses_by_ticker: dict[str, CacheWarmupTickerStatus],
        unique_tickers: list[str],
        provider_batches_planned: int,
        provider_batches_attempted: int,
        provider_symbols_planned: int,
        provider_symbols_attempted: int,
        provider_calls_before: int,
        stopped_for_rate_limit: bool,
        started_at: float,
    ) -> CacheWarmupResult:
        stats = self.context.get_market_data_cache_stats()
        provider_calls_after = stats.provider_calls if stats is not None else 0

        for ticker in unique_tickers:
            if ticker in statuses_by_ticker:
                continue

            statuses_by_ticker[ticker] = CacheWarmupTickerStatus(
                ticker=ticker,
                status="skipped_unknown",
                reason="Not checked",
            )

        return CacheWarmupResult(
            statuses=[statuses_by_ticker[ticker] for ticker in unique_tickers],
            period=config.period,
            batch_size=config.batch_size,
            provider_batches_allowed=config.max_provider_batches,
            provider_batches_planned=provider_batches_planned,
            provider_batches_attempted=provider_batches_attempted,
            provider_symbols_planned=provider_symbols_planned,
            provider_symbols_attempted=provider_symbols_attempted,
            provider_calls_before=provider_calls_before,
            provider_calls_after=provider_calls_after,
            stopped_for_rate_limit=stopped_for_rate_limit,
            cache_only_preview=config.cache_only_preview,
            elapsed_seconds=time.perf_counter() - started_at,
        )

    def _mark_remaining_rate_limited(
        self,
        statuses_by_ticker: dict[str, CacheWarmupTickerStatus],
        provider_batches: list[list[str]],
    ) -> None:
        for batch in provider_batches:
            for ticker in batch:
                statuses_by_ticker[ticker] = CacheWarmupTickerStatus(
                    ticker=ticker,
                    status="skipped_rate_limit",
                    reason="Stopped after provider rate limit",
                )

    def _progress(self, **changes) -> None:
        if self.progress_callback is not None:
            self.progress_callback(**changes)


def _chunks(tickers: list[str], size: int) -> list[list[str]]:
    return [tickers[index : index + size] for index in range(0, len(tickers), size)]


def _dedupe_tickers(tickers: list[str]) -> list[str]:
    deduped = []
    seen = set()

    for ticker in tickers:
        normalized = ticker.strip().upper()

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        deduped.append(normalized)

    return deduped


def _format_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"

    minutes, remaining_seconds = divmod(int(seconds), 60)
    return f"{minutes}m {remaining_seconds}s"


def _is_rate_limit_error(reason: str | None) -> bool:
    if reason is None:
        return False

    return any(pattern in reason for pattern in RATE_LIMIT_PATTERNS)


def _entire_batch_empty(
    batch: list[str],
    statuses_by_ticker: dict[str, CacheWarmupTickerStatus],
) -> bool:
    return bool(batch) and all(
        statuses_by_ticker[ticker].status == "empty" for ticker in batch
    )
