from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
import logging
import time
from typing import Callable

import pandas as pd

from scanner.config.settings import settings
from scanner.context import ScannerContext
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.models.stock_analysis import StockAnalysis
from scanner.services.cache_warmup import (
    CacheWarmupConfig,
    CacheWarmupResult,
    CacheWarmupService,
)
from scanner.services.market_analyzer import MarketAnalyzer
from scanner.services.price_filter import PriceFilterResult, filter_tickers_by_price
from scanner.strategies.strategy_category import StrategyCategory
from scanner.universe.universe_provider import UniverseProvider
from scanner.utils.cache_summary import format_cache_summary


class ScanCancelled(Exception):
    pass


@dataclass(frozen=True)
class ScanConfig:
    universe: str = "all"
    market_data_provider: str = settings.market_data_provider
    history_period: str = settings.scan_history_period
    output_file: str = settings.output_file
    min_price: float | None = None
    max_price: float | None = None
    price_sample_period: str = settings.price_filter_sample_period
    price_filter_batch_size: int = settings.price_filter_batch_size
    price_filter_max_provider_calls: int | None = (
        settings.price_filter_max_provider_calls
    )
    price_filter_max_provider_batches: int | None = (
        settings.price_filter_max_provider_batches
    )
    price_filter_batch_delay_seconds: float = (
        settings.price_filter_batch_delay_seconds
    )
    warm_market_data_cache: bool = settings.cache_warmup_enabled
    cache_warmup_batch_size: int = settings.cache_warmup_batch_size
    cache_warmup_max_provider_batches: int | None = (
        settings.cache_warmup_max_provider_batches
    )
    cache_warmup_batch_delay_seconds: float = settings.cache_warmup_batch_delay_seconds
    cache_warmup_stop_on_rate_limit: bool = settings.cache_warmup_stop_on_rate_limit


@dataclass(frozen=True)
class ScanResult:
    tickers: list[str]
    analyses: list[StockAnalysis]
    trade_candidates: list[StockAnalysis]
    skipped: list[tuple[str, str]]
    dataframe: pd.DataFrame
    output_file: str
    elapsed_seconds: float
    price_filter_result: PriceFilterResult | None = None
    cache_warmup_result: CacheWarmupResult | None = None
    cache_summary: str | None = None
    scanner_run_id: int | None = None


class ScanService:
    def __init__(
        self,
        context: ScannerContext | None = None,
        logger: logging.Logger | None = None,
        universe_provider: UniverseProvider | None = None,
        progress_callback: Callable[..., None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
    ):
        self.context = context or ScannerContext()
        self.logger = logger or self.context.logger
        self.universe_provider = universe_provider or UniverseProvider()
        self.progress_callback = progress_callback
        self.cancel_checker = cancel_checker or (lambda: False)

    def run(self, config: ScanConfig) -> ScanResult:
        start = time.perf_counter()
        tickers = self.universe_provider.get_universe_tickers(config.universe)
        self._raise_if_cancelled()
        self._progress(
            current_step="Loaded universe",
            symbols_total=len(tickers),
            symbols_checked=0,
            symbols_kept=0,
            symbols_skipped=0,
            message=f"Loaded {len(tickers)} tickers",
        )
        price_filter_result = None

        if config.min_price is not None or config.max_price is not None:
            self._progress(
                current_step="Applying price filter",
                symbols_total=len(tickers),
                message="Applying price filter",
            )
            self.logger.info(
                "Applying price filter: "
                f"min={config.min_price if config.min_price is not None else 'none'}, "
                f"max={config.max_price if config.max_price is not None else 'none'}"
            )
            self._raise_if_cancelled()
            price_filter_result = filter_tickers_by_price(
                tickers=tickers,
                min_price=config.min_price,
                max_price=config.max_price,
                provider_name=config.market_data_provider,
                cache_path=self.context.settings.market_data_cache_path,
                sample_period=config.price_sample_period,
                max_cached_price_age_days=(
                    self.context.settings.price_filter_max_cache_age_days
                ),
                max_provider_calls=config.price_filter_max_provider_calls,
                batch_size=config.price_filter_batch_size,
                batch_delay_seconds=config.price_filter_batch_delay_seconds,
                max_provider_batches=config.price_filter_max_provider_batches,
                logger=self.logger,
                cancel_checker=self.cancel_checker,
            )
            self._raise_if_cancelled()
            if price_filter_result.cancelled:
                raise ScanCancelled("Scan cancelled")
            tickers = price_filter_result.tickers
            self._progress(
                current_step="Price filter complete",
                symbols_total=price_filter_result.checked_count,
                symbols_checked=price_filter_result.checked_count,
                symbols_kept=price_filter_result.passed_count,
                symbols_skipped=price_filter_result.skipped_count,
                provider_batches_attempted=(
                    price_filter_result.provider_batches_attempted
                ),
                provider_batch_limit=price_filter_result.provider_batches_allowed,
                provider_symbols_attempted=(
                    price_filter_result.provider_calls_attempted
                ),
                provider_symbol_limit=price_filter_result.provider_calls_allowed,
                rate_limited=price_filter_result.stopped_for_rate_limit,
                message="Price filter complete",
            )
            self.logger.info(
                "Price filter kept "
                f"{price_filter_result.passed_count}/{price_filter_result.checked_count} "
                f"tickers; skipped={price_filter_result.skipped_count}; "
                f"provider_calls_attempted={price_filter_result.provider_calls_attempted}; "
                f"provider_call_limit={price_filter_result.provider_calls_allowed}; "
                f"provider_batches_attempted={price_filter_result.provider_batches_attempted}; "
                f"provider_batch_limit={price_filter_result.provider_batches_allowed}"
            )

        cache_warmup_result = None
        cache_enabled = (
            self.context.settings.market_data_cache_enabled
            if self.context.market_data_cache_enabled is None
            else self.context.market_data_cache_enabled
        )
        if (
            config.warm_market_data_cache
            and not self.context.market_data_cache_force_refresh
            and cache_enabled
        ):
            warmup_tickers = [self.context.settings.benchmark_ticker] + tickers
            self._raise_if_cancelled()
            cache_warmup_result = CacheWarmupService(
                context=self.context,
                logger=self.logger,
                progress_callback=self._prefixed_cache_progress,
                cancel_checker=self.cancel_checker,
            ).run(
                CacheWarmupConfig(
                    tickers=warmup_tickers,
                    period=config.history_period,
                    batch_size=config.cache_warmup_batch_size,
                    batch_delay_seconds=config.cache_warmup_batch_delay_seconds,
                    max_provider_batches=config.cache_warmup_max_provider_batches,
                    stop_on_rate_limit=config.cache_warmup_stop_on_rate_limit,
                )
            )
            self._raise_if_cancelled()
            if cache_warmup_result.cancelled:
                raise ScanCancelled("Scan cancelled")
            self.logger.info(cache_warmup_result.summary())
            self._progress(
                current_step="Cache warmup complete",
                symbols_total=len(tickers),
                provider_batches_attempted=(
                    cache_warmup_result.provider_batches_attempted
                ),
                provider_batch_limit=cache_warmup_result.provider_batches_allowed,
                provider_symbols_attempted=(
                    cache_warmup_result.provider_symbols_attempted
                ),
                rate_limited=cache_warmup_result.stopped_for_rate_limit,
                message="Cache warmup complete",
            )

            if cache_warmup_result.stopped_for_rate_limit:
                available_tickers = set(cache_warmup_result.available_tickers)
                tickers = [ticker for ticker in tickers if ticker in available_tickers]
                self.logger.warning(
                    "Scan will continue using only tickers with usable cached data "
                    f"after cache warmup stopped: {len(tickers)} tickers"
                )
                self._progress(
                    current_step="Cache warmup stopped",
                    symbols_total=len(available_tickers),
                    symbols_skipped=(
                        cache_warmup_result.skipped_count
                    ),
                    rate_limited=True,
                    message="Cache warmup stopped for rate limit",
                )

        benchmark_ticker = self.context.settings.benchmark_ticker.upper()
        if (
            cache_warmup_result is not None
            and cache_warmup_result.stopped_for_rate_limit
            and benchmark_ticker not in set(cache_warmup_result.available_tickers)
        ):
            self.logger.warning(
                "Scan cannot continue because benchmark data is not available "
                "after cache warmup stopped."
            )
            tickers = []
            benchmark_data = pd.DataFrame()
        else:
            self._raise_if_cancelled()
            benchmark_data = self.context.download_price_data(
                self.context.settings.benchmark_ticker,
                period=config.history_period,
            )
            self._raise_if_cancelled()

        analyses: list[StockAnalysis] = []
        skipped: list[tuple[str, str]] = []

        self.logger.info(f"Loaded {len(tickers)} tickers")
        self.logger.info(
            f"Starting scan with {self.context.settings.max_workers} workers"
        )
        self._progress(
            current_step="Analyzing symbols",
            symbols_total=len(tickers),
            symbols_checked=0,
            symbols_kept=0,
            symbols_skipped=0,
            message="Analyzing symbols",
        )

        with ThreadPoolExecutor(max_workers=self.context.settings.max_workers) as executor:
            futures = {
                executor.submit(
                    self._analyze_one,
                    ticker,
                    benchmark_data,
                    config.history_period,
                ): ticker
                for ticker in tickers
            }

            completed = 0

            for future in as_completed(futures):
                if self.cancel_checker():
                    for pending_future in futures:
                        pending_future.cancel()
                    raise ScanCancelled("Scan cancelled")

                completed += 1
                ticker = futures[future]

                try:
                    analyses.append(future.result())
                    self.logger.info(f"[{completed}/{len(tickers)}] Finished {ticker}")

                except Exception as error:
                    skipped.append((ticker, str(error)))
                    self.logger.warning(
                        f"[{completed}/{len(tickers)}] Skipping {ticker}: {error}"
                    )
                self._progress(
                    current_step="Analyzing symbols",
                    symbols_total=len(tickers),
                    symbols_checked=completed,
                    symbols_kept=len(self._trade_candidates(analyses)),
                    symbols_skipped=len(skipped),
                    message=f"Analyzed {completed}/{len(tickers)} symbols",
                )

        self._raise_if_cancelled()
        trade_candidates = self._trade_candidates(analyses)
        dataframe = self._dataframe_for_candidates(trade_candidates)

        if dataframe.empty:
            self.logger.info("No trade candidates found.")

        self._write_watchlist(dataframe, config.output_file)
        scanner_run_id = self._save_scanner_results(dataframe, config)
        self._progress(
            current_step="Writing watchlist",
            symbols_total=len(tickers),
            symbols_checked=len(tickers),
            symbols_kept=len(trade_candidates),
            symbols_skipped=len(skipped),
            output_paths={"watchlist_csv": config.output_file},
            message="Writing watchlist",
        )

        elapsed = time.perf_counter() - start
        cache_summary = format_cache_summary(
            self.context.get_market_data_cache_stats(),
            self.context.get_market_data_cache_overview(),
        )

        self.logger.info("=" * 50)
        self.logger.info(f"Total tickers: {len(tickers)}")
        self.logger.info(f"Successfully analyzed: {len(analyses)}")
        self.logger.info(f"Trade candidates: {len(trade_candidates)}")
        self.logger.info(f"Skipped: {len(skipped)}")
        self.logger.info(f"Scan completed in {elapsed:.2f} seconds")

        if cache_summary:
            self.logger.info(cache_summary)

        if skipped:
            self.logger.info("Skipped tickers:")
            for ticker, reason in skipped:
                self.logger.info(f"  - {ticker}: {reason}")
        self._progress(
            current_step="Scan complete",
            symbols_total=len(tickers),
            symbols_checked=len(tickers),
            symbols_kept=len(trade_candidates),
            symbols_skipped=len(skipped),
            output_paths={"watchlist_csv": config.output_file},
            message="Scan complete",
        )

        return ScanResult(
            tickers=tickers,
            analyses=analyses,
            trade_candidates=trade_candidates,
            skipped=skipped,
            dataframe=dataframe,
            output_file=config.output_file,
            elapsed_seconds=elapsed,
            price_filter_result=price_filter_result,
            cache_warmup_result=cache_warmup_result,
            cache_summary=cache_summary,
            scanner_run_id=scanner_run_id,
        )

    def _analyze_one(
        self,
        ticker: str,
        benchmark_data,
        period: str,
    ) -> StockAnalysis:
        analyzer = MarketAnalyzer(context=self.context, logger=self.logger)
        return analyzer.analyze(ticker, benchmark_data, period=period)

    def _trade_candidates(
        self,
        analyses: list[StockAnalysis],
    ) -> list[StockAnalysis]:
        return [
            analysis
            for analysis in analyses
            if any(
                strategy.triggered and strategy.category == StrategyCategory.ENTRY
                for strategy in analysis.strategy_results
            )
        ]

    def _dataframe_for_candidates(
        self,
        trade_candidates: list[StockAnalysis],
    ) -> pd.DataFrame:
        if not trade_candidates:
            return pd.DataFrame()

        dataframe = pd.DataFrame(
            [candidate.to_dict() for candidate in trade_candidates]
        )
        return dataframe.sort_values(by="Composite Score", ascending=False)

    def _write_watchlist(self, dataframe: pd.DataFrame, output_file: str) -> None:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(output_path, index=False)

    def _save_scanner_results(
        self,
        dataframe: pd.DataFrame,
        config: ScanConfig,
    ) -> int:
        return SQLiteScannerResultStore(
            self.context.settings.market_data_cache_path
        ).save_scan_results(
            dataframe,
            universe=config.universe,
            market_data_provider=config.market_data_provider,
            history_period=config.history_period,
            output_file=config.output_file,
            settings_snapshot=asdict(config),
        )

    def _progress(self, **changes) -> None:
        if self.progress_callback is not None:
            self.progress_callback(**changes)

    def _raise_if_cancelled(self) -> None:
        if self.cancel_checker():
            self.logger.info("Scan cancellation requested")
            self._progress(
                current_step="Cancelling scan",
                message="Cancelling scan",
            )
            raise ScanCancelled("Scan cancelled")

    def _prefixed_cache_progress(self, **changes) -> None:
        current_step = changes.get("current_step")
        if current_step:
            changes["current_step"] = f"Cache warmup: {current_step}"

        self._progress(**changes)
