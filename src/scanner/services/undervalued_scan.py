from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
import logging
import time
from typing import Any, Callable

import pandas as pd

from scanner.config.settings import settings
from scanner.context import ScannerContext
from scanner.data.providers.sec import SECFundamentalsProvider
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.fundamentals import FundamentalAnalysisService
from scanner.fundamentals.cache import FundamentalAnalysisCache
from scanner.services.scan_service import ScanCancelled
from scanner.strategies.undervalued_strategy import (
    UndervaluedStrategy,
    UndervaluedStrategyConfig,
)
from scanner.universe.universe_provider import UniverseProvider


RISK_LEVELS = {"low", "moderate", "high"}
VALIDATION_STATUSES = {"validated", "needs_review", "rejected"}


class IncompleteCandidateAssessment(RuntimeError):
    """Raised when a scanner candidate is missing its required assessment."""


@dataclass(frozen=True)
class UndervaluedScanConfig:
    universe: str = "all"
    market_data_provider: str = settings.market_data_provider
    output_file: str = settings.output_file
    price_period: str = "5d"
    risk_price_period: str = "5y"
    minimum_margin_of_safety: float = 0.15
    discount_rate: float | None = None
    terminal_growth_rate: float = 0.025
    projection_years: int = 5
    max_workers: int = settings.fundamental_scan_workers


@dataclass(frozen=True)
class UndervaluedScanResult:
    tickers: list[str]
    analyzed_count: int
    dataframe: pd.DataFrame
    skipped: list[tuple[str, str]]
    elapsed_seconds: float
    scanner_run_id: int
    excluded_non_common: list[tuple[str, str]] = field(default_factory=list)
    stopped_for_rate_limit: bool = False


class UndervaluedScanService:
    def __init__(
        self,
        context: ScannerContext,
        logger: logging.Logger | None = None,
        universe_provider: UniverseProvider | None = None,
        progress_callback: Callable[..., None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
        fundamentals_provider: SECFundamentalsProvider | None = None,
    ):
        self.context = context
        self.logger = logger or context.logger
        self.universe_provider = universe_provider or UniverseProvider()
        self.progress_callback = progress_callback
        self.cancel_checker = cancel_checker or (lambda: False)
        self.fundamentals_provider = fundamentals_provider or SECFundamentalsProvider(
            user_agent=context.settings.sec_user_agent,
            cache_path=context.settings.market_data_cache_path,
            cache_ttl_hours=context.settings.sec_fundamentals_cache_ttl_hours,
            include_submissions=False,
            max_requests_per_second=context.settings.sec_max_requests_per_second,
        )

    def run(self, config: UndervaluedScanConfig) -> UndervaluedScanResult:
        started_at = time.perf_counter()
        universe_tickers = self.universe_provider.get_universe_tickers(config.universe)
        common_equity_check = getattr(
            self.universe_provider,
            "is_fundamental_common_equity",
            lambda _ticker: True,
        )
        excluded_non_common = [
            (
                ticker,
                self.universe_provider.get_company_name(ticker)
                if hasattr(self.universe_provider, "get_company_name")
                else "",
            )
            for ticker in universe_tickers
            if not common_equity_check(ticker)
        ]
        excluded_tickers = {ticker for ticker, _name in excluded_non_common}
        tickers = [ticker for ticker in universe_tickers if ticker not in excluded_tickers]
        if excluded_non_common:
            self.logger.info(
                "Excluded %s preferred or depositary-share securities from DCF valuation",
                len(excluded_non_common),
            )
        self._raise_if_cancelled()
        self._progress(
            current_step="Loaded valuation universe",
            symbols_total=len(tickers),
            symbols_checked=0,
            symbols_kept=0,
            symbols_skipped=0,
            message=(
                f"Loaded {len(tickers)} common stocks with no price restriction; "
                f"excluded {len(excluded_non_common)} non-common securities"
            ),
        )

        if tickers:
            self.fundamentals_provider.prepare(tickers[0])

        strategy = UndervaluedStrategy(
            UndervaluedStrategyConfig(
                minimum_margin_of_safety=config.minimum_margin_of_safety,
                discount_rate=config.discount_rate,
                terminal_growth_rate=config.terminal_growth_rate,
                projection_years=config.projection_years,
            )
        )
        valuation_service = FundamentalAnalysisService(
            self.fundamentals_provider,
            self.context.get_market_data_provider(),
        )
        analysis_cache = FundamentalAnalysisCache(
            self.context.settings.market_data_cache_path
        )
        rows: list[dict[str, Any]] = []
        skipped: list[tuple[str, str]] = []
        analyzed_count = 0
        stopped_for_rate_limit = False

        def analyze_one(
            ticker: str,
        ) -> tuple[dict[str, Any], dict[str, Any]] | None:
            self._raise_if_cancelled()
            price_history = self.context.download_price_data(
                ticker,
                period=config.price_period,
            )
            current_price, price_as_of = _latest_price(price_history)
            if current_price is None:
                raise RuntimeError("Current market price is unavailable")
            analysis = valuation_service.screen_valuation(
                ticker,
                current_price,
                assumptions=strategy.assumptions(),
                price_history=price_history,
            )
            result = strategy.evaluate_valuation(analysis["valuation"])
            if not result.triggered:
                return None
            risk_history = self.context.download_price_data(
                ticker,
                period=config.risk_price_period,
            )
            analysis = valuation_service.add_screen_risk(analysis, risk_history)
            _require_complete_candidate_assessment(analysis)
            return (
                _candidate_row(
                    analysis,
                    result.checks,
                    result.score,
                    price_as_of,
                    config.minimum_margin_of_safety,
                ),
                analysis,
            )

        max_workers = max(1, min(config.max_workers, len(tickers) or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_one, ticker): ticker for ticker in tickers
            }
            completed = 0
            for future in as_completed(futures):
                if self.cancel_checker():
                    for pending in futures:
                        pending.cancel()
                    raise ScanCancelled("Scan cancelled")

                ticker = futures[future]
                completed += 1
                try:
                    candidate = future.result()
                    analyzed_count += 1
                    if candidate is not None:
                        row, analysis = candidate
                        analysis_cache.set(ticker, {}, analysis)
                        rows.append(row)
                except ScanCancelled:
                    for pending in futures:
                        pending.cancel()
                    raise
                except IncompleteCandidateAssessment as error:
                    message = str(error)
                    skipped.append((ticker, message))
                    self.logger.warning(
                        f"[{completed}/{len(tickers)}] Skipping {ticker}: {message}"
                    )
                except Exception as error:
                    message = str(error)
                    if "rate-limit" in message.lower():
                        stopped_for_rate_limit = True
                        for pending in futures:
                            pending.cancel()
                    elif "rejected the automated request" in message.lower():
                        for pending in futures:
                            pending.cancel()
                        raise
                    skipped.append((ticker, message))
                    self.logger.warning(
                        f"[{completed}/{len(tickers)}] Skipping {ticker}: {message}"
                    )

                self._progress(
                    current_step="Valuing and validating SEC candidates",
                    symbols_total=len(tickers),
                    symbols_checked=completed,
                    symbols_kept=len(rows),
                    symbols_skipped=len(skipped),
                    provider_symbols_attempted=completed,
                    rate_limited=stopped_for_rate_limit,
                    message=(
                        f"Processed {completed}/{len(tickers)} stocks; "
                        f"completed fundamental validation for {len(rows)} candidates"
                    ),
                )
                if stopped_for_rate_limit:
                    break

        dataframe = pd.DataFrame(rows)
        if not dataframe.empty:
            dataframe = dataframe.sort_values(
                by=["Margin of Safety", "Ticker"],
                ascending=[False, True],
            ).reset_index(drop=True)

        output_path = Path(config.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(output_path, index=False)
        scanner_run_id = SQLiteScannerResultStore(
            self.context.settings.business_database_path
        ).save_scan_results(
            dataframe,
            universe=config.universe,
            market_data_provider=config.market_data_provider,
            history_period=config.price_period,
            output_file=config.output_file,
            settings_snapshot={"strategy": "undervalued", **asdict(config)},
        )
        elapsed = time.perf_counter() - started_at
        self._progress(
            current_step="Valuation and fundamental validation complete",
            symbols_total=len(tickers),
            symbols_checked=analyzed_count + len(skipped),
            symbols_kept=len(dataframe),
            symbols_skipped=len(skipped),
            rate_limited=stopped_for_rate_limit,
            output_paths={"watchlist_csv": config.output_file},
            message=(
                "Valuation and fundamental validation complete for "
                f"{len(dataframe)} candidates"
            ),
        )
        return UndervaluedScanResult(
            tickers=tickers,
            analyzed_count=analyzed_count,
            dataframe=dataframe,
            skipped=skipped,
            elapsed_seconds=elapsed,
            scanner_run_id=scanner_run_id,
            excluded_non_common=excluded_non_common,
            stopped_for_rate_limit=stopped_for_rate_limit,
        )

    def _progress(self, **changes) -> None:
        if self.progress_callback is not None:
            self.progress_callback(**changes)

    def _raise_if_cancelled(self) -> None:
        if self.cancel_checker():
            raise ScanCancelled("Scan cancelled")


def _candidate_row(
    analysis: dict[str, Any],
    checks: dict[str, bool],
    strategy_score: int,
    price_as_of: str,
    minimum_margin_of_safety: float,
) -> dict[str, Any]:
    valuation = analysis["valuation"]
    quality = analysis.get("quality") or {}
    validation = analysis.get("validation") or {}
    scenarios = {
        scenario["name"]: scenario for scenario in valuation.get("scenarios") or []
    }
    latest = (analysis.get("financial_history") or [{}])[-1]
    margin = float(valuation["margin_of_safety"])
    row: dict[str, Any] = {
        "Ticker": analysis["ticker"],
        "Company Name": analysis["company"].get("name") or "",
        "Sector": analysis["company"].get("sector") or "",
        "Triggered Strategies": "Undervalued",
        "Strategy Score": strategy_score,
        "Composite Score": strategy_score,
        "Price": round(float(analysis["current_price"]), 2),
        "Current Price": round(float(analysis["current_price"]), 2),
        "Price As Of": price_as_of,
        "Price Source": _price_source(analysis.get("source")),
        "Fair Value": _scenario_value(scenarios, "base"),
        "Bear Fair Value": _scenario_value(scenarios, "bear"),
        "Bull Fair Value": _scenario_value(scenarios, "bull"),
        "Margin of Safety": round(margin * 100, 2),
        "Valuation Label": valuation.get("label") or "unknown",
        "Valuation Confidence": valuation.get("confidence") or "low",
        "Valuation Model": valuation.get("model") or "driver_based_fcff",
        "Quality Label": quality.get("label") or "unknown",
        "Quality Score": quality.get("score"),
        "Risk Level": analysis.get("risk", {}).get("label") or "unknown",
        "Risk Score": analysis.get("risk", {}).get("score"),
        "Risk Complete": analysis.get("risk", {}).get("complete") is True,
        "Validation Status": validation.get("status") or "not_calculated",
        "Validation Label": validation.get("label") or "Not calculated",
        "Validation Score": validation.get("score"),
        "Validation Reasons": " | ".join(validation.get("reasons") or []),
        "Validation Model": validation.get("model") or "unknown",
        "Validation Policy Version": validation.get("policy_version"),
        "SEC Data As Of": analysis.get("data_as_of"),
        "Free Cash Flow": latest.get("free_cash_flow"),
        "FCFF": latest.get("fcff"),
        "Revenue": latest.get("revenue"),
        "Diluted EPS": latest.get("diluted_eps"),
        "Diluted Shares": latest.get("diluted_shares"),
        "Diluted Shares Reported": latest.get("diluted_shares_reported"),
        "Diluted Shares Scale Factor": latest.get(
            "diluted_shares_scale_factor"
        ),
        "Price / Earnings": analysis.get("ratios", {}).get("price_to_earnings"),
        "Price / Free Cash Flow": analysis.get("ratios", {}).get(
            "price_to_free_cash_flow"
        ),
        "DCF Discount Rate": valuation["assumptions"].get("discount_rate"),
        "DCF Terminal Growth": valuation["assumptions"].get(
            "terminal_growth_rate"
        ),
        "DCF Projection Years": valuation["assumptions"].get("projection_years"),
        "DCF Terminal Value Share": (
            (scenarios.get("base") or {})
            .get("valuation_bridge", {})
            .get("terminal_value_share")
        ),
        "Minimum Margin of Safety": minimum_margin_of_safety,
        "Hold Time": "Long term",
        "Fundamental Source": analysis.get("source") or "SEC EDGAR",
        "Undervalued Strategy": "YES",
    }
    for check_name, passed in checks.items():
        row[f"Undervalued: {check_name}"] = "YES" if passed else "NO"
    return row


def _require_complete_candidate_assessment(analysis: dict[str, Any]) -> None:
    ticker = str(analysis.get("ticker") or "unknown")
    risk = analysis.get("risk") or {}
    validation = analysis.get("validation") or {}
    risk_label = str(risk.get("label") or "").strip().lower()
    validation_status = str(validation.get("status") or "").strip().lower()
    if risk.get("complete") is not True or risk_label not in RISK_LEVELS:
        raise IncompleteCandidateAssessment(
            f"Scanner cannot save {ticker}: risk assessment is incomplete"
        )
    if (
        validation_status not in VALIDATION_STATUSES
        or not validation.get("checks")
        or validation.get("policy_version") is None
    ):
        raise IncompleteCandidateAssessment(
            f"Scanner cannot save {ticker}: fundamental validation is incomplete"
        )


def _latest_price(history: pd.DataFrame) -> tuple[float | None, str]:
    if history.empty or "Close" not in history.columns:
        return None, "n/a"
    close = history["Close"].dropna()
    if close.empty:
        return None, "n/a"
    value = float(close.iloc[-1])
    index_value = close.index[-1]
    try:
        price_as_of = pd.Timestamp(index_value).date().isoformat()
    except (TypeError, ValueError):
        price_as_of = str(index_value)
    return value, price_as_of


def _scenario_value(
    scenarios: dict[str, dict[str, Any]],
    name: str,
) -> float | None:
    value = scenarios.get(name, {}).get("fair_value")
    return round(float(value), 2) if value is not None else None


def _price_source(source: object) -> str:
    text = str(source or "")
    marker = "; "
    return text.split(marker, 1)[1].replace(" (prices)", "") if marker in text else text
