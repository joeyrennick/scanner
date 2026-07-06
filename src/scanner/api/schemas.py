from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from scanner.backtesting.backtest_config import ENTRY_RESET_POLICY_NONE
from scanner.config.settings import settings


class CacheWarmupRequest(BaseModel):
    universe: str = "all"
    tickers: list[str] | None = None
    market_data_provider: str = settings.market_data_provider
    history_period: str = settings.scan_history_period
    batch_size: int = settings.cache_warmup_batch_size
    max_provider_batches: int | None = settings.cache_warmup_max_provider_batches
    batch_delay_ms: int = int(settings.cache_warmup_batch_delay_seconds * 1000)
    cache_only_preview: bool = False
    stop_on_rate_limit: bool = settings.cache_warmup_stop_on_rate_limit


class ScanRequest(BaseModel):
    universe: str = "all"
    market_data_provider: str = settings.market_data_provider
    history_period: str = settings.scan_history_period
    min_price: float | None = None
    max_price: float | None = None
    warm_market_data_cache: bool = settings.cache_warmup_enabled
    cache_warmup_batch_size: int = settings.cache_warmup_batch_size
    cache_warmup_max_provider_batches: int | None = (
        settings.cache_warmup_max_provider_batches
    )
    cache_warmup_batch_delay_ms: int = int(
        settings.cache_warmup_batch_delay_seconds * 1000
    )


class WatchlistPriceRefreshRequest(BaseModel):
    rows: list[dict[str, Any]]
    market_data_provider: str = settings.market_data_provider
    period: str = "5d"
    reward_risk_multiple: float = 2.0
    suggested_hold_days: int = 5


class WatchlistPriceRefreshResponse(BaseModel):
    rows: list[dict[str, Any]]
    refreshed_count: int
    fallback_count: int


class BacktestRequest(BaseModel):
    ticker: str | None = None
    universe: str | None = None
    strategy: str = "pullback"
    history_period: str = settings.backtest_history_period
    hold_days: int = 5
    min_history_days: int = 252
    allow_overlapping_trades: bool = True
    entry_reset_policy: str = ENTRY_RESET_POLICY_NONE


class PortfolioSimulationRequest(BaseModel):
    trades_csv: str
    initial_cash: float = 100_000
    max_open_positions: int = 10
    position_size_percent: float = 0.10


class JobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: dict[str, Any]
    current_step: str | None = None
    total_steps: int | None = None
    symbols_total: int | None = None
    symbols_checked: int | None = None
    symbols_kept: int | None = None
    symbols_skipped: int | None = None
    provider_batches_attempted: int | None = None
    provider_batch_limit: int | None = None
    provider_symbols_attempted: int | None = None
    provider_symbol_limit: int | None = None
    elapsed_seconds: float | None = None
    estimated_seconds_remaining: float | None = None
    rate_limited: bool = False
    output_paths: dict[str, str] = Field(default_factory=dict)


class StrategyField(BaseModel):
    name: str
    type: str
    default: Any
    allowed_values: list[Any] | None = None


class StrategyMetadata(BaseModel):
    key: str
    display_name: str
    category: str
    default_config: dict[str, Any]
    fields: list[StrategyField]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
