from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging
import math
import time
from typing import Callable

import pandas as pd

from scanner.config.settings import settings
from scanner.data.cache import SQLiteMarketDataCache
from scanner.data.market_data import download_price_data_batch


RATE_LIMIT_PATTERNS = (
    "Too Many Requests",
    "Rate limited",
    "rate limit",
    "YFRateLimitError",
    "429",
)


@dataclass(frozen=True)
class PriceFilterDecision:
    ticker: str
    price: float | None
    passed: bool
    source: str
    reason: str | None = None


@dataclass(frozen=True)
class PriceFilterResult:
    tickers: list[str]
    decisions: list[PriceFilterDecision]
    provider_calls_allowed: int | None = None
    provider_calls_attempted: int = 0
    provider_batches_allowed: int | None = None
    provider_batches_attempted: int = 0
    stopped_for_rate_limit: bool = False
    cancelled: bool = False

    @property
    def checked_count(self) -> int:
        return len(self.decisions)

    @property
    def passed_count(self) -> int:
        return len(self.tickers)

    @property
    def skipped_count(self) -> int:
        return self.checked_count - self.passed_count


def filter_tickers_by_price(
    tickers: list[str],
    min_price: float | None = None,
    max_price: float | None = None,
    provider_name: str = "yahoo",
    cache_path: str | None = None,
    sample_period: str = "5d",
    max_cached_price_age_days: int = 7,
    max_workers: int | None = None,
    max_provider_calls: int | None = None,
    batch_size: int | None = None,
    batch_delay_seconds: float | None = None,
    max_provider_batches: int | None = None,
    logger: logging.Logger | None = None,
    cancel_checker: Callable[[], bool] | None = None,
) -> PriceFilterResult:
    cache_path = cache_path or settings.market_data_cache_path
    if min_price is None and max_price is None:
        return PriceFilterResult(
            tickers=tickers,
            decisions=[
                PriceFilterDecision(
                    ticker=ticker,
                    price=None,
                    passed=True,
                    source="not_applied",
                )
                for ticker in tickers
            ],
        )

    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError("min_price cannot be greater than max_price")

    symbol_limit = (
        settings.price_filter_max_provider_calls
        if max_provider_calls is None
        else max_provider_calls
    )
    batch_limit = (
        settings.price_filter_max_provider_batches
        if max_provider_batches is None
        else max_provider_batches
    )
    legacy_batch_size = max_workers if batch_size is None else None
    resolved_batch_size = max(
        1,
        batch_size or legacy_batch_size or settings.price_filter_batch_size,
    )
    resolved_delay_seconds = (
        settings.price_filter_batch_delay_seconds
        if batch_delay_seconds is None
        else max(0.0, batch_delay_seconds)
    )

    cache = SQLiteMarketDataCache(cache_path)
    today = date.today()
    decisions_by_ticker: dict[str, PriceFilterDecision] = {}
    provider_tickers: list[str] = []

    for ticker in tickers:
        cached = cache.load_latest_close(provider=provider_name, ticker=ticker)

        if cached is None:
            provider_tickers.append(ticker)
            continue

        cached_date, cached_price = cached
        age_days = (today - cached_date).days

        if age_days > max_cached_price_age_days:
            provider_tickers.append(ticker)
            continue

        decisions_by_ticker[ticker] = _decision_for_price(
            ticker=ticker,
            price=cached_price,
            min_price=min_price,
            max_price=max_price,
            source="cache",
        )

    provider_tickers_to_fetch, skipped_for_symbol_limit = _apply_symbol_limit(
        provider_tickers,
        symbol_limit,
    )
    provider_tickers_to_fetch, skipped_for_batch_limit = _apply_batch_limit(
        provider_tickers_to_fetch,
        resolved_batch_size,
        batch_limit,
    )

    for ticker in skipped_for_symbol_limit:
        decisions_by_ticker[ticker] = _not_checked(
            ticker,
            "Provider symbol limit reached",
        )

    for ticker in skipped_for_batch_limit:
        decisions_by_ticker[ticker] = _not_checked(
            ticker,
            "Provider batch limit reached",
        )

    provider_batches = _chunks(provider_tickers_to_fetch, resolved_batch_size)
    provider_calls_attempted = 0
    provider_batches_attempted = 0
    stopped_for_rate_limit = False
    cancelled = False
    started_at = time.perf_counter()
    should_cancel = cancel_checker or (lambda: False)

    if logger and provider_batches:
        estimated_seconds = _format_seconds(
            len(provider_batches) * resolved_delay_seconds
        )
        logger.info(
            "Price filter needs provider data for "
            f"{len(provider_tickers_to_fetch)} uncached tickers in "
            f"{len(provider_batches)} batches of up to {resolved_batch_size}. "
            f"Minimum wait from configured delays: {estimated_seconds}."
        )

    for batch_number, batch in enumerate(provider_batches, start=1):
        if should_cancel():
            cancelled = True
            break

        provider_calls_attempted += len(batch)
        provider_batches_attempted += 1

        try:
            histories = download_price_data_batch(
                tickers=batch,
                period=sample_period,
            )
        except Exception as error:
            reason = str(error)

            for ticker in batch:
                decisions_by_ticker[ticker] = PriceFilterDecision(
                    ticker=ticker,
                    price=None,
                    passed=False,
                    source="provider",
                    reason=reason,
                )

            stopped_for_rate_limit = _is_rate_limit_error(reason)

            if not stopped_for_rate_limit:
                raise
        else:
            for ticker in batch:
                decisions_by_ticker[ticker] = _decision_from_history(
                    ticker=ticker,
                    history=histories.get(ticker, pd.DataFrame()),
                    min_price=min_price,
                    max_price=max_price,
                )

            stopped_for_rate_limit = any(
                _is_rate_limit_error(decisions_by_ticker[ticker].reason)
                for ticker in batch
            )

            if not stopped_for_rate_limit and _entire_batch_missing_prices(
                batch,
                decisions_by_ticker,
            ):
                stopped_for_rate_limit = True

        if logger:
            _log_batch_progress(
                logger=logger,
                batch_number=batch_number,
                total_batches=len(provider_batches),
                batch_size=len(batch),
                provider_symbols_attempted=provider_calls_attempted,
                elapsed_seconds=time.perf_counter() - started_at,
            )

        if stopped_for_rate_limit:
            break

        if batch_number < len(provider_batches) and resolved_delay_seconds > 0:
            time.sleep(resolved_delay_seconds)

    if cancelled:
        for ticker in provider_tickers_to_fetch:
            if ticker in decisions_by_ticker:
                continue

            decisions_by_ticker[ticker] = _not_checked(
                ticker,
                "Cancelled",
            )

        if logger:
            logger.info("Price filter cancelled before completing provider fetches.")

    if stopped_for_rate_limit:
        for ticker in provider_tickers_to_fetch:
            if ticker in decisions_by_ticker:
                continue

            decisions_by_ticker[ticker] = _not_checked(
                ticker,
                "Stopped after provider rate limit",
            )

        if logger:
            logger.warning(
                "Price filter stopped provider fetches after a rate-limit response. "
                "Rerun later to continue filling the cache."
            )

    for ticker in tickers:
        if ticker in decisions_by_ticker:
            continue

        decisions_by_ticker[ticker] = _not_checked(ticker, "Not checked")

    decisions = [decisions_by_ticker[ticker] for ticker in tickers]
    return PriceFilterResult(
        tickers=[decision.ticker for decision in decisions if decision.passed],
        decisions=decisions,
        provider_calls_allowed=symbol_limit,
        provider_calls_attempted=provider_calls_attempted,
        provider_batches_allowed=batch_limit,
        provider_batches_attempted=provider_batches_attempted,
        stopped_for_rate_limit=stopped_for_rate_limit,
        cancelled=cancelled,
    )


def _decision_from_history(
    ticker: str,
    history: pd.DataFrame,
    min_price: float | None,
    max_price: float | None,
) -> PriceFilterDecision:
    if history.empty or "Close" not in history:
        return PriceFilterDecision(
            ticker=ticker,
            price=None,
            passed=False,
            source="provider",
            reason="No close price returned",
        )

    close = history["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    close = close.dropna()

    if close.empty:
        return PriceFilterDecision(
            ticker=ticker,
            price=None,
            passed=False,
            source="provider",
            reason="No close price returned",
        )

    price = float(close.iloc[-1])
    return _decision_for_price(
        ticker=ticker,
        price=price,
        min_price=min_price,
        max_price=max_price,
        source="provider",
    )


def _decision_for_price(
    ticker: str,
    price: float,
    min_price: float | None,
    max_price: float | None,
    source: str,
) -> PriceFilterDecision:
    if min_price is not None and price < min_price:
        return PriceFilterDecision(
            ticker=ticker,
            price=price,
            passed=False,
            source=source,
            reason=f"Price below {min_price}",
        )

    if max_price is not None and price > max_price:
        return PriceFilterDecision(
            ticker=ticker,
            price=price,
            passed=False,
            source=source,
            reason=f"Price above {max_price}",
        )

    return PriceFilterDecision(
        ticker=ticker,
        price=price,
        passed=True,
        source=source,
    )


def _not_checked(ticker: str, reason: str) -> PriceFilterDecision:
    return PriceFilterDecision(
        ticker=ticker,
        price=None,
        passed=False,
        source="not_checked",
        reason=reason,
    )


def _apply_symbol_limit(
    tickers: list[str],
    symbol_limit: int | None,
) -> tuple[list[str], list[str]]:
    if symbol_limit is None:
        return tickers, []

    return tickers[:symbol_limit], tickers[symbol_limit:]


def _apply_batch_limit(
    tickers: list[str],
    batch_size: int,
    batch_limit: int | None,
) -> tuple[list[str], list[str]]:
    if batch_limit is None:
        return tickers, []

    allowed_count = batch_size * batch_limit
    return tickers[:allowed_count], tickers[allowed_count:]


def _chunks(tickers: list[str], batch_size: int) -> list[list[str]]:
    return [
        tickers[index : index + batch_size]
        for index in range(0, len(tickers), batch_size)
    ]


def _is_rate_limit_error(reason: str | None) -> bool:
    if not reason:
        return False

    return any(pattern in reason for pattern in RATE_LIMIT_PATTERNS)


def _entire_batch_missing_prices(
    batch: list[str],
    decisions_by_ticker: dict[str, PriceFilterDecision],
) -> bool:
    if len(batch) <= 1:
        return False

    return all(
        decisions_by_ticker[ticker].reason == "No close price returned"
        for ticker in batch
    )


def _log_batch_progress(
    logger: logging.Logger,
    batch_number: int,
    total_batches: int,
    batch_size: int,
    provider_symbols_attempted: int,
    elapsed_seconds: float,
) -> None:
    average_seconds = elapsed_seconds / batch_number
    remaining_batches = total_batches - batch_number
    eta_seconds = average_seconds * remaining_batches
    logger.info(
        "Price filter batch "
        f"{batch_number}/{total_batches} complete; "
        f"symbols={batch_size}; "
        f"provider_symbols_attempted={provider_symbols_attempted}; "
        f"elapsed={_format_seconds(elapsed_seconds)}; "
        f"eta={_format_seconds(eta_seconds)}"
    )


def _format_seconds(seconds: float) -> str:
    if math.isinf(seconds) or math.isnan(seconds):
        return "unknown"

    total_seconds = max(0, int(round(seconds)))
    minutes, remaining_seconds = divmod(total_seconds, 60)

    if minutes:
        return f"{minutes}m {remaining_seconds}s"

    return f"{remaining_seconds}s"
