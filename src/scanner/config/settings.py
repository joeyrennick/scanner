from dataclasses import dataclass, field
import os

from scanner.config.paths import ApplicationPaths


@dataclass(frozen=True)
class ScannerSettings:
    benchmark_ticker: str = "SPY"
    output_file: str = field(default_factory=lambda: str(ApplicationPaths.resolve().latest_watchlist))
    market_data_provider: str = os.environ.get("MARKET_DATA_PROVIDER", "massive")
    market_data_cache_enabled: bool = True
    market_data_cache_path: str = field(default_factory=lambda: str(ApplicationPaths.resolve().market_database))
    business_data_path: str | None = None
    credential_data_path: str | None = None
    market_data_cache_retention_years: int = 5
    market_data_refresh_overlap_days: int = 10
    scan_history_period: str = "1y"
    backtest_history_period: str = "1y"
    price_filter_sample_period: str = "5d"
    price_filter_max_cache_age_days: int = 7
    price_filter_workers: int = 5
    price_filter_max_provider_calls: int | None = 500
    price_filter_batch_size: int = 50
    price_filter_batch_delay_seconds: float = 0.5
    price_filter_max_provider_batches: int | None = 10
    cache_warmup_enabled: bool = True
    cache_warmup_batch_size: int = 50
    cache_warmup_batch_delay_seconds: float = 0.5
    cache_warmup_max_provider_batches: int | None = None
    cache_warmup_stop_on_rate_limit: bool = True
    massive_batch_workers: int = int(os.environ.get("MASSIVE_BATCH_WORKERS", "10"))
    # Explicit code override only. Providers resolve launcher/saved setup at
    # construction, so new requests see setup changes without a backend restart.
    sec_user_agent: str = ""
    sec_max_requests_per_second: float = float(
        os.environ.get("SEC_MAX_REQUESTS_PER_SECOND", "8")
    )
    sec_fundamentals_cache_ttl_hours: int = int(
        os.environ.get("SEC_FUNDAMENTALS_CACHE_TTL_HOURS", "24")
    )
    fundamental_scan_workers: int = int(
        os.environ.get("FUNDAMENTAL_SCAN_WORKERS", "8")
    )
    max_workers: int = 40
    backtest_max_workers: int = 80
    relative_strength_lookback_days: int = 63

    @property
    def application_paths(self) -> ApplicationPaths:
        return ApplicationPaths.resolve()

    @property
    def business_database_path(self) -> str:
        if self.business_data_path is not None:
            return self.business_data_path
        # Preserve explicit legacy/test overrides while default runtime separates caches.
        if self.market_data_cache_path != str(self.application_paths.market_database):
            return self.market_data_cache_path
        return str(self.application_paths.database)

    @property
    def credential_database_path(self) -> str:
        if self.credential_data_path is not None:
            return self.credential_data_path
        if self.market_data_cache_path != str(self.application_paths.market_database):
            return self.market_data_cache_path
        return str(self.application_paths.credential_database)


settings = ScannerSettings()
