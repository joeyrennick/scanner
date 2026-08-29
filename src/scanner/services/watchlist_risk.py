from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from scanner.context import ScannerContext
from scanner.data.providers.sec import SECFundamentalsProvider
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.fundamentals import FundamentalAnalysisService


RISK_LEVELS = {"low", "moderate", "high"}
VALIDATION_STATUSES = {"validated", "needs_review", "rejected"}


@dataclass(frozen=True)
class WatchlistRiskResult:
    run_id: int
    classified_count: int
    skipped: list[tuple[str, str]]
    cancelled: bool = False


class WatchlistRiskClassificationService:
    def __init__(
        self,
        context: ScannerContext,
        store: SQLiteScannerResultStore,
        *,
        fundamentals_provider: SECFundamentalsProvider | None = None,
        progress_callback: Callable[..., None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
        max_workers: int = 4,
    ):
        self.context = context
        self.store = store
        self.fundamentals_provider = fundamentals_provider or SECFundamentalsProvider(
            user_agent=context.settings.sec_user_agent,
            cache_path=context.settings.market_data_cache_path,
            cache_ttl_hours=context.settings.sec_fundamentals_cache_ttl_hours,
            include_submissions=False,
            max_requests_per_second=context.settings.sec_max_requests_per_second,
        )
        self.progress_callback = progress_callback
        self.cancel_checker = cancel_checker or (lambda: False)
        self.max_workers = max(1, max_workers)

    def run(self, run_id: int | None = None) -> WatchlistRiskResult:
        run = self.store.get_run(run_id) if run_id is not None else self.store.latest_run()
        if run is None:
            raise ValueError("Scanner run not found")

        pending = [
            row
            for row in run.rows
            if str(row.get("Ticker") or "").strip()
            and (
                str(row.get("Risk Level") or "").strip().lower()
                not in RISK_LEVELS
                or str(row.get("Validation Status") or "").strip().lower()
                not in VALIDATION_STATUSES
            )
        ]
        if not pending:
            self._progress(
                current_step="Risk and validation classifications are current",
                symbols_total=0,
                symbols_checked=0,
                symbols_kept=0,
                symbols_skipped=0,
                message="Risk and validation classifications are current",
            )
            return WatchlistRiskResult(run.id, 0, [])

        self.fundamentals_provider.prepare(str(pending[0]["Ticker"]))
        analysis_service = FundamentalAnalysisService(
            self.fundamentals_provider,
            self.context.get_market_data_provider(),
        )
        classified: list[dict[str, Any]] = []
        skipped: list[tuple[str, str]] = []
        cancelled = False

        def classify(row: dict[str, Any]) -> dict[str, Any]:
            ticker = str(row["Ticker"]).strip().upper()
            history = self.context.download_price_data(ticker, period="5y")
            current_price = _current_price(row, history)
            if current_price is None:
                raise RuntimeError("Current market price is unavailable")
            analysis = analysis_service.screen_valuation(
                ticker,
                current_price,
                price_history=history,
            )
            risk = analysis["risk"]
            validation = analysis.get("validation") or {}
            return {
                "Ticker": ticker,
                "Risk Level": risk["label"],
                "Risk Score": risk["score"],
                "Validation Status": validation.get("status") or "not_calculated",
                "Validation Label": validation.get("label") or "Not calculated",
                "Validation Score": validation.get("score"),
                "Validation Reasons": " | ".join(validation.get("reasons") or []),
                "Validation Model": validation.get("model") or "unknown",
            }

        workers = min(self.max_workers, len(pending))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(classify, row): row for row in pending}
            for completed, future in enumerate(as_completed(futures), start=1):
                if self.cancel_checker():
                    cancelled = True
                    for queued in futures:
                        queued.cancel()
                    break
                ticker = str(futures[future]["Ticker"]).strip().upper()
                try:
                    classified.append(future.result())
                except Exception as error:
                    skipped.append((ticker, str(error)))
                self._progress(
                    current_step="Classifying candidate risk and validation",
                    symbols_total=len(pending),
                    symbols_checked=completed,
                    symbols_kept=len(classified),
                    symbols_skipped=len(skipped),
                    provider_symbols_attempted=completed,
                    message=f"Classified risk and validation for {completed}/{len(pending)} candidates",
                )

        if classified:
            self.store.update_rows_by_ticker(run_id=run.id, rows=classified)

        return WatchlistRiskResult(
            run_id=run.id,
            classified_count=len(classified),
            skipped=skipped,
            cancelled=cancelled,
        )

    def _progress(self, **changes: Any) -> None:
        if self.progress_callback is not None:
            self.progress_callback(**changes)


def _current_price(row: dict[str, Any], history: pd.DataFrame) -> float | None:
    for key in ("Current Price", "Price"):
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    if history.empty or "Close" not in history:
        return None
    close = history["Close"].dropna()
    return float(close.iloc[-1]) if not close.empty else None
