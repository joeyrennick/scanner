# ADR 0001: Market Data Caching

## Status

Accepted

## Date

2026-07-05

## Context

Swing Scanner depends on daily OHLCV history for scanner runs, watchlist price
filters, backtests, portfolio simulations, and daily reports. The default market
data source is Yahoo Finance through `yfinance`, which is useful for a local
investor tool but does not provide a published, contractual request allowance.
Large scans can trigger rate-limit failures, especially when fetching thousands
of tickers or repeatedly rerunning the same analysis.

Most historical daily bars do not change after the provider has settled the
data. Re-fetching the same historical bars wastes request capacity and slows
down workflows. The product therefore needs a cache-first market-data layer that
reduces repeated provider calls while keeping strategy code independent of the
provider and cache implementation.

## Decision

Use a provider interface plus a local SQLite cache as the market-data boundary.

The canonical interface is `MarketDataProvider` in
`src/scanner/data/providers/base.py`. Strategies, scanners, backtests, and
reports should request market data through `download_price_data()` or
`download_price_data_batch()` in `src/scanner/data/market_data.py`, not by
calling `yfinance` directly.

The default provider is `YahooMarketDataProvider`. `AlphaVantageMarketDataProvider`
is available as a backup provider, and additional providers can be registered
through `register_market_data_provider()`.

When caching is enabled, `get_market_data_provider()` wraps the active provider
in `CachedMarketDataProvider`. The cache stores normalized daily bars in
`SQLiteMarketDataCache`, keyed by provider, ticker, interval, and bar date.
Fetch metadata is stored separately so the application can report cache
freshness, cache coverage, and days since the last successful refresh.

The cache uses a cache-first strategy:

- If cached bars cover the requested period and latest required trading date,
  return cached data.
- If history exists but may be stale, fetch a small refresh overlap window
  instead of the full period.
- If history is missing or does not cover the requested start date, fetch the
  requested period from the provider.
- Record successful and failed fetch attempts so the CLI can display cache
  health and troubleshooting information.

Batch download is part of the provider interface. Yahoo requests can combine
multiple tickers into one `yf.download()` call, and `CachedMarketDataProvider`
groups cache misses by refresh period before calling the provider. Price-filter
prefetching also supports batch size limits, provider batch limits, delay
between batches, and rate-limit stop behavior.

The initial implementation keeps existing CLI behavior intact by using the
global settings in `ScannerSettings`:

- `market_data_provider`
- `market_data_cache_enabled`
- `market_data_cache_path`
- `market_data_refresh_overlap_days`
- `price_filter_batch_size`
- `price_filter_batch_delay_seconds`
- `price_filter_max_provider_batches`
- `price_filter_max_provider_calls`
- `max_workers`

## Consequences

This design improves the product for investors because repeated scans,
backtests, and reports reuse local data instead of consuming provider capacity
for the same historical bars. It also makes results more reproducible because
the application can inspect and report which data is cached and when it was last
refreshed.

The provider interface keeps strategy code insulated from market-data vendors.
Switching from Yahoo to Alpha Vantage, or adding another provider later, should
not require changes to strategy logic.

The SQLite cache adds local persistence without requiring a separate database
server. This is appropriate for the current desktop/local CLI product and can
later be replaced or wrapped by a service layer if the UI becomes multi-user.

The tradeoff is added cache-invalidation complexity. Daily bars near the current
date may change after initial publication, and current quotes are not the same
thing as cached historical closes. User-facing daily scanner views must label
current-price data clearly and should refresh candidate quotes through the
market-data layer when the workflow requires current context.

## Known Limitations

- Yahoo Finance through `yfinance` is not an official guaranteed market-data
  API. Rate limits and throttling behavior may change without notice.
- Cached daily bars are not real-time quotes. They are suitable for historical
  strategy analysis and scanner context, but users should verify trade execution
  prices in their broker or trading platform.
- The cache currently stores daily bars. Intraday bars, quote snapshots,
  fundamentals, and corporate-action-specific workflows would need explicit
  schema and freshness rules.
- Existing CLIs still configure market data through module-level state to avoid
  behavior changes. New services should accept `ScannerContext` explicitly so
  settings, providers, caches, and loggers can be isolated in tests and UI
  workflows.
- Universe membership is based on the current ticker lists available to the
  application. Historical backtests may still have survivorship-bias limitations
  unless historical universe membership is added.
- Provider failures are still possible. The cache reduces repeat calls but
  cannot guarantee that a first-time full-universe cache warmup will avoid every
  provider throttle.

## Alternatives Considered

No local cache: simpler implementation, but repeated scans and backtests would
continue to waste provider calls and expose first-time users to rate-limit
failures.

Provider-specific calls throughout the application: quick to write, but it
would couple scanner and strategy code to Yahoo-specific behavior and make
backup providers harder to add.

Paid provider only: would provide clearer service guarantees, but it would make
the product harder for first-time users to run locally. The current approach
keeps Yahoo as the default and supports paid providers as opt-in backups.

CSV-file cache: easy to inspect manually, but SQLite gives stronger keys,
upserts, date filtering, fetch metadata, and future migration options with
little operational cost.

## Implementation References

- `src/scanner/data/providers/base.py`
- `src/scanner/data/providers/yahoo.py`
- `src/scanner/data/providers/alpha_vantage.py`
- `src/scanner/data/providers/cached.py`
- `src/scanner/data/cache.py`
- `src/scanner/data/market_data.py`
- `src/scanner/services/price_filter.py`
- `src/scanner/config/settings.py`
