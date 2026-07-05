from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import date, datetime
from pathlib import Path
import base64
import math
from typing import Any, Literal, get_args, get_origin

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import pandas as pd

from scanner.api.jobs import jobs
from scanner.api.schemas import (
    BacktestRequest,
    CacheWarmupRequest,
    HealthResponse,
    JobResponse,
    PortfolioSimulationRequest,
    ScanRequest,
    StrategyField,
    StrategyMetadata,
)
from scanner.backtesting.backtest_config import BacktestConfig
from scanner.backtesting.backtest_service import BacktestService
from scanner.config.settings import settings
from scanner.context import ScannerContext
from scanner.data.cache import SQLiteMarketDataCache
from scanner.services.cache_warmup import CacheWarmupConfig, CacheWarmupService
from scanner.services.scan_service import ScanConfig, ScanService
from scanner.strategies.strategy_registry import StrategyRegistry
from scanner.universe.universe_provider import UniverseProvider
from scanner.utils.cache_summary import format_cache_summary
from scanner.utils.logger import setup_logging


app = FastAPI(title="Swing Scanner API")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return _json_safe(asdict(settings))


@app.get("/api/cache/overview")
def get_cache_overview() -> dict[str, Any]:
    cache = SQLiteMarketDataCache(settings.market_data_cache_path)
    overview = cache.overview(provider=settings.market_data_provider)
    return _json_safe(asdict(overview))


@app.post("/api/cache/warmup", response_model=JobResponse)
def start_cache_warmup(request: CacheWarmupRequest) -> dict[str, Any]:
    job = jobs.start(
        "cache_warmup",
        lambda: _run_cache_warmup(request),
    )
    return job.to_dict()


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)

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
        lambda: _run_scan(request),
    )
    return job.to_dict()


@app.get("/api/scans/{job_id}", response_model=JobResponse)
def get_scan(job_id: str) -> dict[str, Any]:
    return get_job(job_id)


@app.get("/api/watchlist/latest")
def get_latest_watchlist() -> dict[str, Any]:
    path = Path(settings.output_file)

    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "rows": [],
        }

    dataframe = pd.read_csv(path)
    return {
        "exists": True,
        "path": str(path),
        "rows": _records_from_dataframe(dataframe),
    }


@app.post("/api/backtests", response_model=JobResponse)
def start_backtest(request: BacktestRequest) -> dict[str, Any]:
    if not request.ticker and not request.universe:
        raise HTTPException(
            status_code=422,
            detail="Either ticker or universe is required",
        )

    job = jobs.start(
        "backtest",
        lambda: _run_backtest(request),
    )
    return job.to_dict()


@app.get("/api/backtests/{job_id}", response_model=JobResponse)
def get_backtest(job_id: str) -> dict[str, Any]:
    return get_job(job_id)


@app.post("/api/portfolio/simulations")
def start_portfolio_simulation(_request: PortfolioSimulationRequest) -> None:
    raise HTTPException(
        status_code=501,
        detail="Portfolio simulation API endpoint is not implemented yet",
    )


@app.get("/api/reports")
def list_reports() -> list[dict[str, Any]]:
    output_dir = Path("output")

    if not output_dir.exists():
        return []

    reports = []

    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".html", ".csv"}:
            continue

        reports.append(_report_metadata(path))

    return reports


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


def _run_cache_warmup(request: CacheWarmupRequest) -> dict[str, Any]:
    logger = setup_logging()
    context = ScannerContext(
        settings=replace(settings, market_data_provider=request.market_data_provider),
        logger=logger,
        market_data_cache_enabled=True,
    )
    tickers = _resolve_tickers(request.universe, request.tickers)
    result = CacheWarmupService(context=context, logger=logger).run(
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


def _run_scan(request: ScanRequest) -> dict[str, Any]:
    logger = setup_logging()
    context = ScannerContext(
        settings=replace(settings, market_data_provider=request.market_data_provider),
        logger=logger,
        market_data_cache_enabled=True,
    )
    result = ScanService(context=context, logger=logger).run(
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
    return _json_safe(
        {
            "tickers": result.tickers,
            "analyses": len(result.analyses),
            "candidates": len(result.trade_candidates),
            "skipped": result.skipped,
            "watchlist_path": result.output_file,
            "elapsed_seconds": result.elapsed_seconds,
            "rows": _records_from_dataframe(result.dataframe),
            "cache_summary": result.cache_summary,
            "stopped_for_rate_limit": (
                cache_warmup_result.stopped_for_rate_limit
                if cache_warmup_result
                else False
            ),
        }
    )


def _run_backtest(request: BacktestRequest) -> dict[str, Any]:
    strategy = StrategyRegistry.get(request.strategy)
    result = BacktestService(
        config=BacktestConfig(
            history_period=request.history_period,
            hold_days=request.hold_days,
            min_history_days=request.min_history_days,
            allow_overlapping_trades=request.allow_overlapping_trades,
            entry_reset_policy=request.entry_reset_policy,
        )
    ).run(
        ticker=request.ticker,
        universe=request.universe,
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


def _records_from_dataframe(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    if dataframe.empty:
        return []

    safe_dataframe = dataframe.astype(object).where(pd.notna(dataframe), None)
    return _json_safe(safe_dataframe.to_dict(orient="records"))


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


def _report_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "id": _report_id(path),
        "name": path.name,
        "path": str(path),
        "type": _report_type(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


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
    if "backtest" in name and path.suffix == ".html":
        return "backtest"
    if "portfolio" in name and path.suffix == ".html":
        return "portfolio"
    if path.suffix == ".csv":
        return "csv_export"

    return "other"
