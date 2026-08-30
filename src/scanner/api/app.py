from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import date, datetime
from pathlib import Path
import base64
import json
import math
import os
from uuid import uuid4
from typing import Any, Literal, get_args, get_origin

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import pandas as pd
from pandas.errors import EmptyDataError

from scanner.api.jobs import jobs
from scanner.api.schemas import (
    BacktestRequest,
    CacheWarmupRequest,
    CandidateTradeLevelsRequest,
    CandidateTradeLevelsResponse,
    DailyScannerReportRequest,
    DailyScannerReportResponse,
    FundamentalAnalysisRequest,
    FundamentalReportRequest,
    HealthResponse,
    JobResponse,
    MarketDataCredentialRequest,
    MarketDataCredentialStatus,
    MarketDataHistoryResponse,
    PortfolioSimulationRequest,
    ScanRequest,
    SavedWatchlistItemRequest,
    SavedWatchlistRequest,
    StrategyField,
    StrategyMetadata,
    WatchlistPriceRefreshRequest,
    WatchlistPriceRefreshResponse,
    WatchlistRiskClassificationRequest,
)
from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtest_service import BacktestService
from scanner.config.settings import settings
from scanner.context import ScannerContext
from scanner.data.cache import SQLiteMarketDataCache
from scanner.data.market_data import clear_market_data_provider_cache, create_market_data_provider
from scanner.data.providers.cached import period_start_date
from scanner.data.providers.massive import MASSIVE_API_KEY_SECRET, MassiveMarketDataProvider
from scanner.data.providers.sec import SECFundamentalsProvider
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.data.saved_watchlists import SQLiteSavedWatchlistStore
from scanner.portfolio.execution_model import ExecutionModel
from scanner.portfolio.portfolio_simulator import PortfolioSimulator
from scanner.portfolio.trade_csv_loader import load_trades_from_csv
from scanner.fundamentals import FundamentalAnalysisService
from scanner.fundamentals.cache import FundamentalAnalysisCache
from scanner.reports.daily_scanner_report import DailyScannerReport
from scanner.reports.fundamental_analysis_report import FundamentalAnalysisReport
from scanner.services.cache_warmup import CacheWarmupConfig, CacheWarmupService
from scanner.security.secret_store import SQLiteSecretStore
from scanner.services.scan_service import ScanCancelled, ScanConfig, ScanService
from scanner.services.undervalued_scan import (
    UndervaluedScanConfig,
    UndervaluedScanService,
)
from scanner.services.watchlist_risk import WatchlistRiskClassificationService
from scanner.strategies.strategy_registry import StrategyRegistry
from scanner.universe.universe_provider import UniverseProvider
from scanner.utils.cache_summary import format_cache_summary
from scanner.utils.logger import add_file_handler, remove_handler, setup_logging


app = FastAPI(title="Swing Scanner API")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return _json_safe(asdict(settings))


@app.get(
    "/api/market-data/massive/credential",
    response_model=MarketDataCredentialStatus,
)
def get_massive_credential_status() -> MarketDataCredentialStatus:
    return _massive_credential_status()


@app.put(
    "/api/market-data/massive/credential",
    response_model=MarketDataCredentialStatus,
)
def save_massive_credential(
    request: MarketDataCredentialRequest,
) -> MarketDataCredentialStatus:
    api_key = request.api_key.strip()

    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    _secret_store().set_secret(MASSIVE_API_KEY_SECRET, api_key)
    clear_market_data_provider_cache()
    return _massive_credential_status()


@app.delete(
    "/api/market-data/massive/credential",
    response_model=MarketDataCredentialStatus,
)
def delete_massive_credential() -> MarketDataCredentialStatus:
    _secret_store().delete_secret(MASSIVE_API_KEY_SECRET)
    clear_market_data_provider_cache()
    return _massive_credential_status()


@app.get(
    "/api/market-data/history/{ticker}",
    response_model=MarketDataHistoryResponse,
)
def get_market_data_history(
    ticker: str,
    provider: str = settings.market_data_provider,
    period: str = settings.scan_history_period,
    interval: str = "1d",
) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()

    if not normalized_ticker:
        raise HTTPException(status_code=422, detail="Ticker is required")

    supported_intervals = {"5m", "15m", "1d"}
    if interval not in supported_intervals:
        supported = ", ".join(sorted(supported_intervals))
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported market data interval: {interval}. Supported: {supported}",
        )

    try:
        market_data_provider = create_market_data_provider(
            name=provider,
            cache_enabled=interval == "1d",
            cache_path=settings.market_data_cache_path,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        fetch_period = _moving_average_fetch_period(period=period, interval=interval)
        if interval == "1d":
            history = market_data_provider.download_price_data(
                ticker=normalized_ticker,
                period=fetch_period,
            )
        else:
            history = market_data_provider.download_price_data(
                ticker=normalized_ticker,
                period=fetch_period,
                interval=interval,
            )
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    if history.empty or "Close" not in history.columns:
        return {
            "ticker": normalized_ticker,
            "provider": provider,
            "period": period,
            "interval": interval,
            "rows": [],
        }

    history = _add_moving_averages(history)
    history = _trim_history_to_period(history, period=period)

    return _json_safe(
        {
            "ticker": normalized_ticker,
            "provider": provider,
            "period": period,
            "interval": interval,
            "rows": _history_points_from_dataframe(history, interval=interval),
        }
    )


@app.post("/api/fundamentals/{ticker}")
def analyze_fundamentals(
    ticker: str,
    request: FundamentalAnalysisRequest,
) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise HTTPException(status_code=422, detail="Ticker is required")

    try:
        cache = FundamentalAnalysisCache(settings.market_data_cache_path)
        analysis = cache.get(normalized_ticker, request.assumptions)
        if analysis is None:
            price_provider = create_market_data_provider(
                name=settings.market_data_provider,
                cache_enabled=True,
                cache_path=settings.market_data_cache_path,
            )
            analysis = FundamentalAnalysisService(
                SECFundamentalsProvider(
                    user_agent=settings.sec_user_agent,
                    cache_path=settings.market_data_cache_path,
                    cache_ttl_hours=settings.sec_fundamentals_cache_ttl_hours,
                    max_requests_per_second=settings.sec_max_requests_per_second,
                ),
                price_provider,
            ).analyze(
                normalized_ticker,
                assumptions=request.assumptions,
            )
            cache.set(normalized_ticker, request.assumptions, analysis)
        _persist_candidate_assessment(normalized_ticker, analysis, request.run_id)
        return _json_safe(analysis)
    except RuntimeError as error:
        status = 400 if "API_KEY" in str(error) else 502
        raise HTTPException(status_code=status, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to load fundamentals for {normalized_ticker}: {error}",
        ) from error


@app.get("/api/saved-watchlists")
def list_saved_watchlists() -> dict[str, Any]:
    return {
        "watchlists": [
            _saved_watchlist_payload(watchlist, include_items=False)
            for watchlist in _saved_watchlist_store().list_watchlists()
        ]
    }


@app.post("/api/saved-watchlists")
def create_saved_watchlist(request: SavedWatchlistRequest) -> dict[str, Any]:
    try:
        return _saved_watchlist_payload(
            _saved_watchlist_store().create_watchlist(request.name),
            include_items=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/saved-watchlists/{watchlist_id}")
def get_saved_watchlist(watchlist_id: int) -> dict[str, Any]:
    watchlist = _saved_watchlist_store().get_watchlist(watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Saved watchlist not found")
    return _saved_watchlist_payload(watchlist, include_items=True)


@app.patch("/api/saved-watchlists/{watchlist_id}")
def rename_saved_watchlist(
    watchlist_id: int,
    request: SavedWatchlistRequest,
) -> dict[str, Any]:
    try:
        watchlist = _saved_watchlist_store().rename_watchlist(watchlist_id, request.name)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _saved_watchlist_payload(watchlist, include_items=True)


@app.delete("/api/saved-watchlists/{watchlist_id}")
def delete_saved_watchlist(watchlist_id: int) -> dict[str, bool]:
    if not _saved_watchlist_store().delete_watchlist(watchlist_id):
        raise HTTPException(status_code=404, detail="Saved watchlist not found")
    return {"deleted": True}


@app.post("/api/saved-watchlists/{watchlist_id}/items")
def add_saved_watchlist_item(
    watchlist_id: int,
    request: SavedWatchlistItemRequest,
) -> dict[str, Any]:
    try:
        item = _saved_watchlist_store().add_item(
            watchlist_id,
            request.ticker,
            source=request.source,
            data=request.data,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _saved_watchlist_item_payload(item)


@app.delete("/api/saved-watchlists/{watchlist_id}/items/{ticker}")
def remove_saved_watchlist_item(watchlist_id: int, ticker: str) -> dict[str, bool]:
    try:
        removed = _saved_watchlist_store().remove_item(watchlist_id, ticker)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"deleted": removed}


@app.get("/api/cache/overview")
def get_cache_overview() -> dict[str, Any]:
    cache = SQLiteMarketDataCache(settings.market_data_cache_path)
    overview = cache.overview(provider=settings.market_data_provider)
    return _json_safe(asdict(overview))


@app.post("/api/cache/warmup", response_model=JobResponse)
def start_cache_warmup(request: CacheWarmupRequest) -> dict[str, Any]:
    job = jobs.start(
        "cache_warmup",
        lambda progress, _cancel: _run_cache_warmup(request, progress),
    )
    return job.to_dict()


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str) -> dict[str, Any]:
    job = jobs.cancel(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@app.get("/api/strategies", response_model=list[StrategyMetadata])
def get_strategies() -> list[StrategyMetadata]:
    return [_strategy_metadata(name) for name in StrategyRegistry.names()]


@app.post("/api/scans", response_model=JobResponse)
def start_scan(request: ScanRequest) -> dict[str, Any]:
    job = jobs.start(
        "scan",
        lambda progress, cancel: _run_scan(request, progress, cancel),
    )
    return job.to_dict()


@app.post("/api/watchlist/classify-risk", response_model=JobResponse)
def classify_watchlist_risk(
    request: WatchlistRiskClassificationRequest,
) -> dict[str, Any]:
    job = jobs.start(
        "watchlist_risk_classification",
        lambda progress, cancel: _run_watchlist_risk_classification(
            request,
            progress,
            cancel,
        ),
    )
    return job.to_dict()


@app.get("/api/scans/{job_id}", response_model=JobResponse)
def get_scan(job_id: str) -> dict[str, Any]:
    return get_job(job_id)


@app.get("/api/watchlist/latest")
def get_latest_watchlist() -> dict[str, Any]:
    store = _scanner_result_store()
    latest_run = store.latest_run()

    if latest_run is not None:
        return {
            "exists": True,
            "path": latest_run.output_file,
            "run_id": latest_run.id,
            "created_at": latest_run.created_at,
            "rows": _rows_with_cached_risk(latest_run.rows),
        }

    path = Path(settings.output_file)

    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "run_id": None,
            "created_at": None,
            "rows": [],
        }

    try:
        dataframe = pd.read_csv(path)
    except EmptyDataError:
        dataframe = pd.DataFrame()

    if not dataframe.empty:
        run_id = store.save_scan_results(
            dataframe,
            universe="csv_import",
            market_data_provider=settings.market_data_provider,
            history_period=settings.scan_history_period,
            output_file=str(path),
            settings_snapshot={"source": "watchlist_csv_backfill"},
        )
        imported_run = store.latest_run()

        if imported_run is not None and imported_run.id == run_id:
            return {
                "exists": True,
                "path": imported_run.output_file,
                "run_id": imported_run.id,
                "created_at": imported_run.created_at,
                "rows": _rows_with_cached_risk(imported_run.rows),
            }

    return {
        "exists": True,
        "path": str(path),
        "run_id": None,
        "created_at": None,
        "rows": _records_from_dataframe(dataframe),
    }


@app.get("/api/watchlist/runs/{run_id}")
def get_watchlist_run(run_id: int) -> dict[str, Any]:
    run = _scanner_result_store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scanner run not found")
    return {
        "exists": True,
        "path": run.output_file,
        "run_id": run.id,
        "created_at": run.created_at,
        "rows": _rows_with_cached_risk(run.rows),
    }


@app.post(
    "/api/watchlist/refresh-prices",
    response_model=WatchlistPriceRefreshResponse,
)
def refresh_watchlist_prices(
    request: WatchlistPriceRefreshRequest,
) -> dict[str, Any]:
    return _json_safe(_refresh_watchlist_prices(request))


@app.post(
    "/api/watchlist/candidates/{ticker}/trade-levels",
    response_model=CandidateTradeLevelsResponse,
)
def update_candidate_trade_levels(
    ticker: str,
    request: CandidateTradeLevelsRequest,
) -> dict[str, Any]:
    store = _scanner_result_store()
    run_id = request.run_id

    if run_id is None:
        latest_run = store.latest_run()
        if latest_run is None:
            raise HTTPException(status_code=404, detail="Scanner run not found")
        run_id = latest_run.id

    try:
        row = store.update_trade_levels(
            run_id=run_id,
            ticker=ticker,
            entry_area=request.entry_area,
            suggested_stop=request.suggested_stop,
            target_exit=request.target_exit,
            reset=request.reset,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return _json_safe(
        {
            "run_id": run_id,
            "ticker": ticker.upper(),
            "row": row,
        }
    )


@app.post("/api/backtests", response_model=JobResponse)
def start_backtest(request: BacktestRequest) -> dict[str, Any]:
    if not request.ticker and not request.universe and not request.tickers:
        raise HTTPException(
            status_code=422,
            detail="Either ticker, universe, or tickers is required",
        )

    job = jobs.start(
        "backtest",
        lambda progress, _cancel: _run_backtest(request, progress),
    )
    return job.to_dict()


@app.get("/api/backtests/{job_id}", response_model=JobResponse)
def get_backtest(job_id: str) -> dict[str, Any]:
    return get_job(job_id)


@app.post("/api/portfolio/simulations", response_model=JobResponse)
def start_portfolio_simulation(request: PortfolioSimulationRequest) -> dict[str, Any]:
    job = jobs.start(
        "portfolio_simulation",
        lambda progress, _cancel: _run_portfolio_simulation(request, progress),
    )
    return job.to_dict()


@app.get("/api/reports")
def list_reports() -> list[dict[str, Any]]:
    output_dir = Path("output")

    if not output_dir.exists():
        return []

    reports = []

    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".html", ".csv", ".log", ".pdf"}:
            continue

        reports.append(_report_metadata(path))

    return reports


@app.post("/api/reports/daily-scanner", response_model=DailyScannerReportResponse)
def generate_daily_scanner_report(
    request: DailyScannerReportRequest,
) -> dict[str, Any]:
    report_date = _parse_report_date(request.report_date)
    output_dir = Path("output/daily_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    watchlist_path = _daily_report_watchlist_path(request, output_dir, report_date)
    report_path = output_dir / f"daily_scanner_report_{report_date.isoformat()}.html"

    try:
        report = DailyScannerReport(
            watchlist_path=str(watchlist_path),
            report_date=report_date,
            account_size=request.account_size,
            risk_per_trade_percent=request.risk_per_trade_percent,
            suggested_hold_days=request.suggested_hold_days,
            reward_risk_multiple=request.reward_risk_multiple,
        )
        report.generate_html_report(report_path)
        archive_path = (
            report.archive_watchlist(output_dir) if request.archive_watchlist else None
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return _json_safe(
        {
            "report": _report_metadata(report_path),
            "archived_watchlist": str(archive_path) if archive_path else None,
        }
    )


@app.post("/api/reports/fundamental-analysis")
def generate_fundamental_analysis_report(
    request: FundamentalReportRequest,
) -> dict[str, Any]:
    ticker = request.ticker.strip().upper()
    analysis_ticker = str(request.analysis.get("ticker") or "").upper()
    if not ticker or analysis_ticker != ticker:
        raise HTTPException(status_code=422, detail="Report ticker does not match analysis")
    if request.analysis.get("schema_version") not in {1, 3, 4}:
        raise HTTPException(status_code=422, detail="Unsupported analysis schema version")

    output_dir = Path("output/fundamental_reports")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    stem = f"{ticker}_fundamental_analysis_{timestamp}"
    pdf_path = output_dir / f"{stem}.pdf"
    snapshot_path = output_dir / f"{stem}.json"
    FundamentalAnalysisReport(request.analysis, request.page_state).generate(
        pdf_path,
        snapshot_path,
    )
    return {
        "report": _report_metadata(pdf_path),
        "snapshot_path": str(snapshot_path),
    }


@app.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    path = _report_path(report_id)

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")

    return _report_metadata(path)


@app.get("/api/reports/{report_id}/download")
def download_report(report_id: str) -> FileResponse:
    path = _report_path(report_id)

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(path, filename=path.name)


@app.get("/api/reports/{report_id}/view")
def view_report(report_id: str) -> FileResponse:
    path = _report_path(report_id)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    media_type = "application/pdf" if path.suffix.lower() == ".pdf" else None
    return FileResponse(
        path,
        media_type=media_type,
        content_disposition_type="inline",
    )


def _refresh_watchlist_prices(
    request: WatchlistPriceRefreshRequest,
) -> dict[str, Any]:
    tickers = [_string_value(row.get("Ticker")).upper() for row in request.rows]
    tickers = [ticker for ticker in tickers if ticker]
    provider = create_market_data_provider(
        name=request.market_data_provider,
        cache_enabled=False,
    )
    histories = provider.download_price_data_batch(
        tickers=sorted(set(tickers)),
        period=request.period,
    )
    refreshed_rows = []
    refreshed_count = 0
    fallback_count = 0

    for row in request.rows:
        updated = dict(row)
        ticker = _string_value(updated.get("Ticker")).upper()
        latest = _latest_price_from_history(histories.get(ticker, pd.DataFrame()))

        if latest is None:
            fallback_count += 1
            price = _float_value(updated.get("Current Price")) or _float_value(
                updated.get("Price")
            )
            price_as_of = _string_value(updated.get("Price As Of")) or "Cached"
            price_source = "Cached Close"
            five_day_range = _float_value(updated.get("5D Range"))
        else:
            refreshed_count += 1
            price, price_as_of = latest
            price_source = _provider_display_name(request.market_data_provider)
            five_day_range = _five_day_range_percent(
                histories.get(ticker, pd.DataFrame())
            )

        if price is None:
            updated["Price Source"] = "Unavailable"
        else:
            _apply_refreshed_trade_levels(
                updated,
                price=price,
                price_as_of=price_as_of,
                price_source=price_source,
                five_day_range=five_day_range,
                reward_risk_multiple=request.reward_risk_multiple,
                suggested_hold_days=request.suggested_hold_days,
            )

        refreshed_rows.append(updated)

    run_id = request.run_id
    if run_id is None:
        latest_run = _scanner_result_store().latest_run()
        run_id = latest_run.id if latest_run is not None else None

    if run_id is not None:
        _scanner_result_store().update_rows_by_ticker(
            run_id=run_id,
            rows=refreshed_rows,
        )

    return {
        "rows": refreshed_rows,
        "refreshed_count": refreshed_count,
        "fallback_count": fallback_count,
    }


def _latest_price_from_history(history: pd.DataFrame) -> tuple[float, str] | None:
    if history.empty or "Close" not in history.columns:
        return None

    close = history["Close"].dropna()

    if close.empty:
        return None

    latest_timestamp = close.index[-1]
    latest_price = close.iloc[-1].item()

    return float(latest_price), str(latest_timestamp.date())


def _five_day_range_percent(history: pd.DataFrame) -> float | None:
    if history.empty or not {"High", "Low", "Close"}.issubset(history.columns):
        return None

    recent = history[["High", "Low", "Close"]].dropna().tail(5)

    if recent.empty:
        return None

    latest_close = recent["Close"].iloc[-1].item()

    if latest_close <= 0:
        return None

    high = recent["High"].max().item()
    low = recent["Low"].min().item()

    return ((high - low) / latest_close) * 100


def _apply_refreshed_trade_levels(
    row: dict[str, Any],
    price: float,
    price_as_of: str,
    price_source: str,
    five_day_range: float | None,
    reward_risk_multiple: float,
    suggested_hold_days: int,
) -> None:
    atr = _float_value(row.get("ATR14"))
    stop = price - (2 * atr) if atr is not None else None

    row["Price"] = round(price, 2)
    row["Current Price"] = round(price, 2)
    row["Price As Of"] = price_as_of
    row["Price Source"] = price_source
    row["Entry Area"] = round(price, 2)
    row["Suggested Hold Time"] = f"{suggested_hold_days} trading days"

    if five_day_range is not None:
        row["5D Range"] = round(five_day_range)

    if stop is None:
        return

    risk_per_share = price - stop
    target = price + (risk_per_share * reward_risk_multiple)
    stop_distance_percent = (risk_per_share / price) * 100
    row["Stop 2ATR"] = round(stop, 2)
    row["Suggested Stop"] = round(stop, 2)
    row["Risk / Share"] = round(risk_per_share, 2)
    row["Stop Distance %"] = round(stop_distance_percent, 2)
    row["Target/Exit"] = round(target, 2)
    row["Suggested Exit"] = round(target, 2)


def _float_value(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) else None

    if not isinstance(value, str):
        return None

    try:
        parsed = float(value.replace("$", "").replace(",", "").replace("%", ""))
    except ValueError:
        return None

    return parsed if math.isfinite(parsed) else None


def _string_value(value: Any) -> str:
    if value is None:
        return ""

    return str(value)


def _provider_display_name(provider: str) -> str:
    normalized = provider.lower()

    if normalized == "yahoo":
        return "Yahoo"
    if normalized in {"massive", "polygon"}:
        return "Massive/Polygon"
    if normalized == "alpha_vantage":
        return "Alpha Vantage"

    return provider.replace("_", " ").title()


def _run_cache_warmup(request: CacheWarmupRequest, progress) -> dict[str, Any]:
    logger = setup_logging()
    context = ScannerContext(
        settings=replace(settings, market_data_provider=request.market_data_provider),
        logger=logger,
        market_data_cache_enabled=True,
    )
    tickers = _resolve_tickers(request.universe, request.tickers)
    result = CacheWarmupService(
        context=context,
        logger=logger,
        progress_callback=progress,
    ).run(
        CacheWarmupConfig(
            tickers=[settings.benchmark_ticker] + tickers,
            period=request.history_period,
            batch_size=request.batch_size,
            batch_delay_seconds=request.batch_delay_ms / 1000,
            max_provider_batches=request.max_provider_batches,
            cache_only_preview=request.cache_only_preview,
            stop_on_rate_limit=request.stop_on_rate_limit,
        )
    )
    return _json_safe(
        {
            "summary": result.summary(),
            "available": result.available_count,
            "cached": result.cached_count,
            "fetched": result.fetched_count,
            "skipped": result.skipped_count,
            "provider_batches_attempted": result.provider_batches_attempted,
            "provider_batches_planned": result.provider_batches_planned,
            "provider_calls_attempted": result.provider_calls_attempted,
            "stopped_for_rate_limit": result.stopped_for_rate_limit,
            "cache_only_preview": result.cache_only_preview,
            "cache_summary": format_cache_summary(
                context.get_market_data_cache_stats(),
                context.get_market_data_cache_overview(),
            ),
        }
    )


def _run_watchlist_risk_classification(
    request: WatchlistRiskClassificationRequest,
    progress,
    cancel_checker,
) -> dict[str, Any]:
    context = ScannerContext(
        settings=replace(settings, market_data_provider=request.market_data_provider),
        logger=setup_logging(),
        market_data_cache_enabled=True,
    )
    result = WatchlistRiskClassificationService(
        context,
        _scanner_result_store(),
        progress_callback=progress,
        cancel_checker=cancel_checker,
        max_workers=settings.fundamental_scan_workers,
    ).run(request.run_id)
    return _json_safe(
        {
            "scanner_run_id": result.run_id,
            "classified_count": result.classified_count,
            "skipped": result.skipped,
            "cancelled": result.cancelled,
        }
    )


def _run_scan(request: ScanRequest, progress, cancel_checker) -> dict[str, Any]:
    logger = setup_logging()
    log_path = _scan_log_path()
    file_handler = add_file_handler(logger, log_path)
    scan_log_output = {"scan_log": str(log_path)}

    def scan_progress(**changes):
        output_paths = changes.get("output_paths")
        if isinstance(output_paths, dict):
            changes["output_paths"] = {**scan_log_output, **output_paths}
        else:
            changes["output_paths"] = scan_log_output

        progress(**changes)

    scan_progress(output_paths={})

    try:
        logger.info("Starting UI scanner run")
        logger.info(
            "Scan request: "
            f"universe={request.universe}, "
            f"strategy={request.strategy}, "
            f"provider={request.market_data_provider}, "
            f"history_period={request.history_period}, "
            f"min_price={request.min_price}, "
            f"max_price={request.max_price}, "
            f"warm_cache={request.warm_market_data_cache}"
        )
        context = ScannerContext(
            settings=replace(settings, market_data_provider=request.market_data_provider),
            logger=logger,
            market_data_cache_enabled=True,
        )
        if request.strategy.lower() == "undervalued":
            strategy = StrategyRegistry.get("undervalued")
            valuation_result = UndervaluedScanService(
                context=context,
                logger=logger,
                progress_callback=scan_progress,
                cancel_checker=cancel_checker,
            ).run(
                UndervaluedScanConfig(
                    universe=request.universe,
                    market_data_provider=request.market_data_provider,
                    output_file=settings.output_file,
                    minimum_margin_of_safety=(
                        strategy.config.minimum_margin_of_safety
                    ),
                    discount_rate=strategy.config.discount_rate,
                    terminal_growth_rate=strategy.config.terminal_growth_rate,
                    projection_years=strategy.config.projection_years,
                    max_workers=settings.fundamental_scan_workers,
                )
            )
            logger.info("UI undervalued scan complete")
            validation_status_counts = (
                valuation_result.dataframe["Validation Status"]
                .value_counts()
                .to_dict()
                if not valuation_result.dataframe.empty
                else {}
            )
            return _json_safe(
                {
                    "scanner_run_id": valuation_result.scanner_run_id,
                    "tickers": valuation_result.tickers,
                    "analyses": valuation_result.analyzed_count,
                    "candidates": len(valuation_result.dataframe),
                    "fundamental_validations": len(valuation_result.dataframe),
                    "validation_status_counts": validation_status_counts,
                    "skipped": valuation_result.skipped,
                    "excluded_non_common": valuation_result.excluded_non_common,
                    "watchlist_path": settings.output_file,
                    "log_path": str(log_path),
                    "elapsed_seconds": valuation_result.elapsed_seconds,
                    "rows": _records_from_dataframe(valuation_result.dataframe),
                    "stopped_for_rate_limit": (
                        valuation_result.stopped_for_rate_limit
                    ),
                    "output_paths": {
                        "watchlist_csv": settings.output_file,
                        "scan_log": str(log_path),
                    },
                }
            )
        result = ScanService(
            context=context,
            logger=logger,
            progress_callback=scan_progress,
            cancel_checker=cancel_checker,
        ).run(
            ScanConfig(
                universe=request.universe,
                market_data_provider=request.market_data_provider,
                history_period=request.history_period,
                min_price=request.min_price,
                max_price=request.max_price,
                warm_market_data_cache=request.warm_market_data_cache,
                cache_warmup_batch_size=request.cache_warmup_batch_size,
                cache_warmup_max_provider_batches=request.cache_warmup_max_provider_batches,
                cache_warmup_batch_delay_seconds=(
                    request.cache_warmup_batch_delay_ms / 1000
                ),
            )
        )
        cache_warmup_result = result.cache_warmup_result
        logger.info("UI scanner run complete")
        return _json_safe(
            {
                "scanner_run_id": result.scanner_run_id,
                "tickers": result.tickers,
                "analyses": len(result.analyses),
                "candidates": len(result.trade_candidates),
                "skipped": result.skipped,
                "watchlist_path": result.output_file,
                "log_path": str(log_path),
                "elapsed_seconds": result.elapsed_seconds,
                "rows": _records_from_dataframe(result.dataframe),
                "cache_summary": result.cache_summary,
                "stopped_for_rate_limit": (
                    cache_warmup_result.stopped_for_rate_limit
                    if cache_warmup_result
                    else False
                ),
                "output_paths": {
                    "watchlist_csv": result.output_file,
                    "scan_log": str(log_path),
                },
            }
        )
    except ScanCancelled:
        logger.info("UI scanner run cancelled")
        return _json_safe(
            {
                "cancelled": True,
                "log_path": str(log_path),
                "output_paths": scan_log_output,
            }
        )
    except Exception:
        logger.exception("UI scanner run failed")
        raise
    finally:
        remove_handler(logger, file_handler)


def _run_backtest(request: BacktestRequest, progress) -> dict[str, Any]:
    strategy = StrategyRegistry.get(request.strategy)
    if not getattr(strategy, "backtestable", True):
        raise ValueError(
            f"{strategy.name} is a point-in-time fundamental screen and cannot be "
            "tested by the technical price-history backtester."
        )
    result = BacktestService(
        config=BacktestConfig(
            history_period=request.history_period,
            hold_days=request.hold_days,
            min_history_days=request.min_history_days,
            allow_overlapping_trades=request.allow_overlapping_trades,
            entry_reset_policy=request.entry_reset_policy,
        ),
        progress_callback=progress,
    ).run(
        ticker=request.ticker,
        universe=request.universe,
        tickers=_normalize_request_tickers(request.tickers),
        result_ticker=_backtest_result_label(request),
        strategy=strategy,
    )
    statistics = result.statistics
    return _json_safe(
        {
            "ticker": result.ticker,
            "strategy": result.strategy_name,
            "statistics": {
                "total_trades": statistics.total_trades,
                "win_rate": statistics.win_rate,
                "average_return": statistics.average_return,
                "average_win": statistics.average_win,
                "average_loss": statistics.average_loss,
                "best_trade_return": statistics.best_trade_return,
                "worst_trade_return": statistics.worst_trade_return,
                "expectancy": statistics.expectancy,
                "profit_factor": statistics.profit_factor,
            },
            "trades": [trade.to_dict() for trade in result.trades],
        }
    )


def _run_portfolio_simulation(
    request: PortfolioSimulationRequest,
    progress,
) -> dict[str, Any]:
    progress(
        current_step="Loading trades",
        symbols_checked=0,
        message="Loading trades",
    )
    trades = load_trades_from_csv(request.trades_csv)
    progress(
        current_step="Simulating portfolio",
        symbols_total=len(trades),
        symbols_checked=0,
        message="Simulating portfolio",
    )
    execution_model = ExecutionModel(
        commission_per_trade=request.commission_per_trade,
        commission_per_share=request.commission_per_share,
        slippage_percent=request.slippage_percent,
        stop_loss_percent=request.stop_loss_percent,
        trailing_stop_percent=request.trailing_stop_percent,
    )
    simulator = PortfolioSimulator(
        initial_cash=request.initial_cash,
        max_open_positions=request.max_open_positions,
        max_positions_per_ticker=request.max_positions_per_ticker,
        position_size_percent=request.position_size_percent,
        execution_model=execution_model,
    )
    result = simulator.run(trades)
    progress(
        current_step="Portfolio simulation complete",
        symbols_total=len(trades),
        symbols_checked=len(trades),
        symbols_kept=len(result.positions),
        symbols_skipped=result.skipped_trades,
        message="Portfolio simulation complete",
    )
    equity_curve = (
        result.equity_curve.astype(object)
        .where(pd.notna(result.equity_curve), None)
        .to_dict(orient="records")
        if not result.equity_curve.empty
        else []
    )
    return _json_safe(
        {
            "summary": result.summary(),
            "equity_curve": equity_curve,
            "positions": _records_from_dataframe(result.positions_dataframe()),
        }
    )


def _strategy_metadata(name: str) -> StrategyMetadata:
    strategy = StrategyRegistry.get(name)
    config = StrategyRegistry.default_config(name)
    config_fields = []

    for field in fields(config):
        value = getattr(config, field.name)
        config_fields.append(
            StrategyField(
                name=field.name,
                type=_field_type_name(field.type),
                default=value,
                allowed_values=_allowed_values(field.type),
            )
        )

    return StrategyMetadata(
        key=name,
        display_name=strategy.name,
        category=strategy.category.value,
        evaluation_mode=getattr(strategy, "evaluation_mode", "technical"),
        backtestable=getattr(strategy, "backtestable", True),
        default_config=asdict(config),
        fields=config_fields,
    )


def _field_type_name(annotation: Any) -> str:
    origin = get_origin(annotation)

    if origin is None:
        return getattr(annotation, "__name__", str(annotation))

    if origin is Literal:
        return "literal"

    return str(annotation)


def _allowed_values(annotation: Any) -> list[Any] | None:
    if get_origin(annotation) is Literal:
        return list(get_args(annotation))

    return None


def _resolve_tickers(universe: str, tickers: list[str] | None) -> list[str]:
    if tickers:
        return [ticker.strip().upper() for ticker in tickers if ticker.strip()]

    return UniverseProvider().get_universe_tickers(universe)


def _normalize_request_tickers(tickers: list[str] | None) -> list[str] | None:
    if not tickers:
        return None

    normalized = []
    seen = set()

    for ticker in tickers:
        cleaned = ticker.strip().upper()

        if not cleaned or cleaned in seen:
            continue

        normalized.append(cleaned)
        seen.add(cleaned)

    return normalized or None


def _backtest_result_label(request: BacktestRequest) -> str | None:
    tickers = _normalize_request_tickers(request.tickers)

    if tickers:
        return f"{len(tickers)} Candidate Tickers"

    return None


def _records_from_dataframe(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    if dataframe.empty:
        return []

    safe_dataframe = dataframe.astype(object).where(pd.notna(dataframe), None)
    return _json_safe(safe_dataframe.to_dict(orient="records"))


def _scanner_result_store() -> SQLiteScannerResultStore:
    return SQLiteScannerResultStore(settings.market_data_cache_path)


def _saved_watchlist_store() -> SQLiteSavedWatchlistStore:
    return SQLiteSavedWatchlistStore(settings.market_data_cache_path)


def _saved_watchlist_payload(watchlist: Any, *, include_items: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": watchlist.id,
        "name": watchlist.name,
        "created_at": watchlist.created_at,
        "updated_at": watchlist.updated_at,
        "item_count": len(watchlist.items),
        "tickers": [item.ticker for item in watchlist.items],
    }
    if include_items:
        latest_run = _scanner_result_store().latest_run()
        latest_by_ticker = {
            str(row.get("Ticker") or row.get("Symbol") or "").strip().upper(): row
            for row in (latest_run.rows if latest_run else [])
        }
        payload["items"] = [
            _saved_watchlist_item_payload(
                item,
                latest_data=latest_by_ticker.get(item.ticker),
            )
            for item in watchlist.items
        ]
    return _json_safe(payload)


def _saved_watchlist_item_payload(
    item: Any,
    *,
    latest_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = {**item.data, **(latest_data or {})}
    data["Ticker"] = item.ticker
    return {
        "ticker": item.ticker,
        "source": item.source,
        "data": data,
        "added_at": item.added_at,
        "updated_at": item.updated_at,
    }


def _persist_candidate_assessment(
    ticker: str,
    analysis: dict[str, Any],
    run_id: int | None,
) -> None:
    risk = analysis.get("risk") or {}
    label = str(risk.get("label") or "").strip().lower()
    score = risk.get("score")
    validation = analysis.get("validation") or {}
    validation_status = str(validation.get("status") or "").strip().lower()
    if (
        label not in {"low", "moderate", "high"}
        and validation_status not in {"validated", "needs_review", "rejected"}
    ):
        return

    store = _scanner_result_store()
    run = store.get_run(run_id) if run_id is not None else store.latest_run()
    if run is None or not any(
        str(row.get("Ticker") or "").strip().upper() == ticker for row in run.rows
    ):
        return
    update: dict[str, Any] = {"Ticker": ticker}
    if label in {"low", "moderate", "high"} and isinstance(score, (int, float)):
        update.update({"Risk Level": label, "Risk Score": score})
    if validation_status in {"validated", "needs_review", "rejected"}:
        update.update(
            {
                "Validation Status": validation_status,
                "Validation Label": validation.get("label") or validation_status.replace("_", " ").title(),
                "Validation Score": validation.get("score"),
                "Validation Reasons": " | ".join(validation.get("reasons") or []),
                "Validation Model": validation.get("model") or "unknown",
            }
        )
    store.update_rows_by_ticker(run_id=run.id, rows=[update])


def _rows_with_cached_risk(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cache = FundamentalAnalysisCache(settings.market_data_cache_path)
    tickers = [str(row.get("Ticker") or "") for row in rows]
    cached_risks = cache.latest_risks(tickers)
    cached_validations = cache.latest_validations(tickers)
    if not cached_risks and not cached_validations:
        return rows

    enriched = []
    for row in rows:
        existing_label = str(row.get("Risk Level") or "").strip().lower()
        ticker = str(row.get("Ticker") or "").strip().upper()
        cached_risk = cached_risks.get(ticker)
        cached_validation = cached_validations.get(ticker)
        update: dict[str, Any] = {}
        if existing_label not in {"low", "moderate", "high"} and cached_risk is not None:
            update.update(
                {"Risk Level": cached_risk["label"], "Risk Score": cached_risk["score"]}
            )
        existing_validation = str(row.get("Validation Status") or "").strip().lower()
        if (
            existing_validation not in {"validated", "needs_review", "rejected"}
            and cached_validation is not None
        ):
            update.update(
                {
                    "Validation Status": cached_validation["status"],
                    "Validation Label": cached_validation["label"],
                    "Validation Score": cached_validation["score"],
                    "Validation Reasons": " | ".join(cached_validation["reasons"]),
                    "Validation Model": cached_validation["model"],
                }
            )
        enriched.append({**row, **update} if update else row)
    return enriched


def _parse_report_date(value: str | None) -> date:
    if not value:
        return date.today()

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="report_date must be in YYYY-MM-DD format",
        ) from error


def _scan_log_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("output/logs") / f"scanner_run_{timestamp}_{uuid4().hex[:8]}.log"


def _daily_report_watchlist_path(
    request: DailyScannerReportRequest,
    output_dir: Path,
    report_date: date,
) -> Path:
    if request.rows is not None:
        if not request.rows:
            raise HTTPException(
                status_code=422,
                detail="Daily scanner report requires at least one row",
            )

        watchlist_path = output_dir / f"watchlist_report_input_{report_date.isoformat()}.csv"
        pd.DataFrame(request.rows).to_csv(watchlist_path, index=False)
        return watchlist_path

    latest_run = _scanner_result_store().latest_run()

    if latest_run is not None and latest_run.rows:
        watchlist_path = output_dir / f"watchlist_report_input_{report_date.isoformat()}.csv"
        pd.DataFrame(latest_run.rows).to_csv(watchlist_path, index=False)
        return watchlist_path

    path = Path(settings.output_file)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return path


def _history_points_from_dataframe(
    dataframe: pd.DataFrame,
    interval: str = "1d",
) -> list[dict[str, Any]]:
    rows = []
    history = dataframe.sort_index()

    for index, row in history.iterrows():
        close = _float_value(row.get("Close"))

        if close is None:
            continue

        timestamp = pd.Timestamp(index)
        rows.append(
            {
                "date": (
                    timestamp.date().isoformat()
                    if interval == "1d"
                    else timestamp.isoformat()
                ),
                "open": _float_value(row.get("Open")),
                "high": _float_value(row.get("High")),
                "low": _float_value(row.get("Low")),
                "close": close,
                "volume": _float_value(row.get("Volume")),
                "sma_50": _float_value(row.get("SMA 50")),
                "sma_200": _float_value(row.get("SMA 200")),
            }
        )

    return rows


def _moving_average_fetch_period(period: str, interval: str) -> str:
    if interval == "5m" and period == "1d":
        return "10d"
    if interval == "15m" and period == "5d":
        return "1mo"
    if interval == "1d":
        return {
            "1mo": "1y",
            "ytd": "2y",
            "1y": "2y",
        }.get(period, period)
    return period


def _add_moving_averages(history: pd.DataFrame) -> pd.DataFrame:
    result = history.sort_index().copy()
    close = pd.to_numeric(result["Close"], errors="coerce")
    result["SMA 50"] = close.rolling(window=50, min_periods=50).mean()
    result["SMA 200"] = close.rolling(window=200, min_periods=200).mean()
    return result


def _trim_history_to_period(history: pd.DataFrame, period: str) -> pd.DataFrame:
    start_date = period_start_date(period=period, today=date.today())
    if start_date is None:
        return history

    mask = [pd.Timestamp(index).date() >= start_date for index in history.index]
    return history.loc[mask]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if hasattr(value, "item"):
        return _json_safe(value.item())

    return value


def _secret_store() -> SQLiteSecretStore:
    return SQLiteSecretStore(settings.market_data_cache_path)


def _massive_credential_status() -> MarketDataCredentialStatus:
    if os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY"):
        return MarketDataCredentialStatus(
            provider="massive",
            configured=True,
            source="environment",
            updated_at=None,
        )

    metadata = _secret_store().metadata(MASSIVE_API_KEY_SECRET)
    return MarketDataCredentialStatus(
        provider="massive",
        configured=metadata.configured,
        source="encrypted_sqlite" if metadata.configured else None,
        updated_at=metadata.updated_at.isoformat() if metadata.updated_at else None,
    )


def _report_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    metadata = {
        "id": _report_id(path),
        "name": path.name,
        "path": str(path),
        "type": _report_type(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }
    if path.suffix.lower() == ".pdf" and "_fundamental_analysis_" in path.name.lower():
        snapshot_path = path.with_suffix(".json")
        if snapshot_path.exists():
            try:
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                analysis = snapshot.get("analysis") or {}
                metadata.update(
                    {
                        "ticker": analysis.get("ticker"),
                        "data_as_of": analysis.get("data_as_of"),
                        "quality_label": (analysis.get("quality") or {}).get("label"),
                        "valuation_label": (analysis.get("valuation") or {}).get("label"),
                        "risk_label": (analysis.get("risk") or {}).get("label"),
                        "validation_label": (analysis.get("validation") or {}).get("label"),
                    }
                )
            except (ValueError, TypeError):
                pass
    return metadata


def _report_id(path: Path) -> str:
    relative = path.relative_to(Path("output"))
    return base64.urlsafe_b64encode(str(relative).encode()).decode()


def _report_path(report_id: str) -> Path:
    try:
        relative = base64.urlsafe_b64decode(report_id.encode()).decode()
    except Exception as error:
        raise HTTPException(status_code=404, detail="Report not found") from error

    path = Path("output") / relative
    resolved_output = Path("output").resolve()
    resolved_path = path.resolve()

    if resolved_output not in resolved_path.parents and resolved_path != resolved_output:
        raise HTTPException(status_code=404, detail="Report not found")

    return path


def _report_type(path: Path) -> str:
    name = path.name.lower()

    if name.startswith("daily_scanner_report_") and path.suffix == ".html":
        return "daily_scanner"
    if "_fundamental_analysis_" in name and path.suffix == ".pdf":
        return "fundamental_analysis"
    if "backtest" in name and path.suffix == ".html":
        return "backtest"
    if "portfolio" in name and path.suffix == ".html":
        return "portfolio"
    if path.suffix == ".csv":
        return "csv_export"
    if path.suffix == ".log":
        return "log"

    return "other"
