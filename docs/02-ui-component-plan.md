# UI Component Plan

## Recommendation

Build the first UI as a local browser-based app in this repository.

Use a Python backend over the existing scanner services and a small frontend that runs in the user's browser. This works on both Mac and PC, avoids native desktop packaging complexity, and keeps the current CLI workflows intact.

Do not create a separate repository yet. The scanner, cache, backtester, portfolio simulator, journal, and report generator are still tightly coupled. Split the UI later only if deployment, permissions, or product ownership require it.

## Proposed Stack

- Backend: FastAPI
- Frontend: React + TypeScript + Vite
- Styling: plain CSS modules or a small component layer, no heavy design framework initially
- Charts: Recharts or lightweight charting library
- Server state: TanStack Query with a thin plain `fetch` API client underneath
- Storage: existing SQLite cache and CSV outputs
- Runtime: local dev server started from one command

FastAPI is a good fit because the app already has Python service logic. React/Vite is a good fit because the UI will need interactive tables, progress updates, cache status, filters, and reports.

## Frontend Data Layer

Use TanStack Query for all server state in the React app. Do not build custom `useEffect`/`useState` fetch hooks for normal API reads, polling, mutation state, or cache invalidation.

Keep a thin plain `fetch` wrapper underneath TanStack Query:

- `ui/src/lib/apiClient.ts`
  - owns base URL handling
  - sends JSON requests
  - parses JSON responses
  - turns HTTP failures into typed errors
  - supports `AbortSignal`
  - stays independent of React

Add typed API modules that call the shared client:

- `ui/src/api/cache.ts`
- `ui/src/api/scanner.ts`
- `ui/src/api/backtest.ts`
- `ui/src/api/portfolio.ts`
- `ui/src/api/reports.ts`
- `ui/src/api/journal.ts`
- `ui/src/api/settings.ts`

Wrap those API modules with TanStack Query hooks:

- `useCacheOverview()`
- `useCacheWarmupJob(jobId)`
- `useDailyScanJob(jobId)`
- `useWatchlistLatest(filters)`
- `useBacktestJob(jobId)`
- `useReportsIndex(filters)`
- `useJournalSummary(filters)`
- `useSettings()`

Use centralized query keys in `ui/src/api/queryKeys.ts`:

- `['cache', 'overview']`
- `['jobs', jobId]`
- `['scanner', 'watchlist', filters]`
- `['backtests', jobId]`
- `['reports', 'index', filters]`
- `['journal', 'summary', filters]`
- `['settings']`

Use mutations for commands:

- start cache warmup
- run daily scan
- run backtest
- run portfolio simulation
- save settings
- sync broker trades
- apply broker journal matches

After successful mutations, invalidate the related queries instead of manually pushing data through unrelated components. For example, saving settings invalidates `['settings']`, starting a scan invalidates scanner job/watchlist queries when the job completes, and applying broker matches invalidates journal summary and journal table queries.

Use TanStack Query polling for long-running jobs before adding WebSockets or server-sent events. Cache warmup, scanner runs, backtests, portfolio simulations, and broker sync should poll `GET /api/jobs/{job_id}` until the job reaches `complete`, `failed`, or `stopped`.

Testing expectations:

- Unit test the plain API client without React.
- Unit test query hooks with mocked API responses.
- Component-test loading, empty, success, and API error states.
- Component-test rate-limit and provider-warning states where the backend exposes them.

## First User Experience

The first screen should be the scanner workspace, not a marketing page.

Primary first-run workflow:

1. User chooses universe: `sp500`, `djia`, `nasdaq`, `nyse`, or `all`.
2. User chooses strategy from backend strategy metadata: all enabled strategies or one/more of Pullback, Breakout, Bounce, and future registered strategies.
3. User sets optional price range, for example `$20` to `$50`.
4. UI shows current cache status:
   - cached tickers
   - cached bars
   - latest cached bar
   - last successful refresh
   - days since refresh
5. User starts a cache warmup or scan.
   - Daily Scanner runs a pre-scan cache warmup/incremental refresh before strategy analysis when cache is enabled.
   - Fresh cached symbols do not call the provider.
   - Stale cached symbols fetch only the configured overlap window.
   - Missing symbols are fetched in controlled batches.
   - If Yahoo rate limiting is detected, provider calls stop and the scan only continues for symbols with usable cached history.
6. UI shows progress:
   - current batch
   - total planned batches
   - symbols checked
   - symbols kept/skipped
   - provider calls/batches attempted
   - estimated time remaining
   - whether rate limiting stopped the run
7. After candidates are identified, UI refreshes the latest available provider price for the final candidate list.
8. User reviews candidates in a sortable/filterable watchlist.
9. User can open detail for each candidate.

Daily Scanner price handling:

- Use cached historical bars for strategy calculations, indicators, ATR, moving averages, relative strength, and backtests.
- Do not rely on stale cached history for the displayed candidate price.
- After the candidate list is narrowed, make a small fresh provider quote/history request for those final tickers only.
- Display `Current Price`, `Price As Of`, and `Price Source` in scanner results, candidate detail, manual trade checklist, and the daily HTML report.
- The scanner table `Current Price` column should include an info tooltip explaining that Yahoo/latest provider prices may be delayed or stale and should be verified in the user's trading platform before placing a trade.
- If fresh price refresh fails because of provider errors or rate limits, fall back to the latest cached close and label it clearly as `Cached Close`.
- Treat Yahoo prices as latest available Yahoo data, not guaranteed real-time market data.

## Initial Screens

### Scanner

Purpose: generate today's watchlist.

Controls:

- universe selector
- strategy selector populated from backend strategy metadata
- min/max price
- history period
- cache-only toggle
- max provider batches
- batch size
- batch delay
- run button

Output:

- watchlist table
- score columns
- strategy flags, including Pullback, Breakout, Bounce, and future registered strategies
- current price, price as of, price source
- moving averages, ATR, volume, relative strength
- entry area, stop, target/exit, hold time
- cache and provider summary
- CSV export link
- daily HTML report link

The scanner table should not show the reward/risk column. Reward/risk belongs in Candidate Detail, where there is room to explain how the target was calculated.

Scanner values that come from Candidate Detail can be user-adjusted:

- Entry area, stop, target/exit, and hold time start from the app's suggested values.
- If the user adjusts entry, stop, or target in Candidate Detail, the Daily Scanner table should show the adjusted values for that candidate.
- Adjusted values should be visually marked, for example with an `Edited` indicator or tooltip.
- The user must be able to revert adjusted values back to the original app-suggested values.
- The Candidate Detail stock chart should be resizable so investors can enlarge it while adjusting trade levels.
- Resizing the chart should preserve visible draggable trade levels and should not hide or break the Manual Trade Checklist panel.

### Cache Warmup

Purpose: help a first-time user build cache safely without hitting Yahoo too hard.

Controls:

- universe selector
- price range
- batch size
- max batches
- delay between batches
- cache-only preview mode

Output:

- cached ticker count
- uncached ticker count
- latest cached bar
- days since refresh
- progress bar
- ETA
- skipped symbols
- rate-limit warning if detected

### Cache Warmup CLI

Add a dedicated cache warmup command in addition to the UI flow. The command should be safe for first-time users and should reuse the same service code as the UI/API.

Proposed command:

```bash
PYTHONPATH=src venv/bin/python src/warm_cache.py \
  --universe all \
  --history-period 6mo \
  --batch-size 100 \
  --max-provider-batches 10 \
  --batch-delay-ms 500
```

Preview command:

```bash
PYTHONPATH=src venv/bin/python src/warm_cache.py \
  --universe all \
  --cache-only-preview
```

CLI options:

- `--universe`: `sp500`, `djia`, `nasdaq`, `nyse`, or `all`
- `--tickers`: optional comma-separated ticker override
- `--history-period`: default `6mo`
- `--batch-size`: default from settings
- `--max-provider-batches`: optional cap for safe incremental warmups
- `--batch-delay-ms`: delay between provider batches in milliseconds
- `--cache-only-preview`: inspect existing cache only and make no provider calls
- `--refresh-market-data-cache`: force refreshes, for maintenance only; this can increase provider calls
- `--keep-going-on-rate-limit`: advanced override; default behavior stops provider calls immediately if rate limiting is detected

Shared service boundary:

- Create a cache warmup service under `src/scanner/services/`.
- The CLI, FastAPI endpoint, and future UI should call this same service.
- The service should own batching, stale-cache checks, cache-only preview, rate-limit handling, progress events, and summary output.
- The CLI should be a thin argument parser plus terminal progress renderer.
- The FastAPI endpoint should start the same service as a tracked background job.

Terminal output:

- show selected universe, history period, provider, and cache database path
- estimate symbols to inspect, maximum provider batches, and minimum wait time before starting
- show progress with current batch, symbols checked, kept, skipped, provider batches attempted, elapsed time, ETA, and rate-limit status
- clearly label cache-only preview as `no provider calls`
- print final cache summary, rows fetched, rows served from cache, provider calls avoided, skipped symbols, and output paths

Safety behavior:

- default to conservative batching and delay values from settings
- never continue provider calls after a detected Yahoo rate-limit error by default
- allow advanced users to override that behavior with `--keep-going-on-rate-limit`
- preserve all cached data if a provider error or rate limit occurs
- allow the user to resume later without refetching fresh cached data
- return a non-zero exit code only for hard failures, not for a controlled rate-limit stop

Tests:

- unit test cache-only preview makes zero provider calls
- unit test fresh-cache mode skips provider calls
- unit test provider batching respects `batch_size`, `max_provider_batches`, and `batch_delay_ms`
- unit test rate-limit handling stops subsequent provider calls and preserves cache
- unit test CLI argument parsing maps to the shared service request model
- integration test CLI summary output with a fake provider

### Backtest

Purpose: test a strategy over a selected universe, watchlist, or ticker.

Controls:

- ticker/universe/watchlist source
- strategy selector populated from backend strategy metadata
- hold days
- history period
- minimum history days, default `252`
- allow overlapping trades toggle, default on
- entry reset policy selector, default `None`
- price range
- parameter sweep controls:
  - hold day values
  - minimum history values
  - overlap modes
  - entry reset policies
  - strategy config field ranges from backend strategy metadata
  - ranking metric
  - minimum trades
- walk-forward controls:
  - date range
  - training window months
  - forward-test window months
  - step months
  - same parameter ranges and ranking metric used by parameter sweep
- export trades

Output:

- backtest summary
- backtest config context: hold days, history period, minimum history days, overlap mode, entry reset policy
- trade table
- return distribution
- monthly summary
- ticker summary
- analyzer bucket summaries:
  - strategy summary
  - composite score buckets
  - relative strength buckets
  - relative volume buckets
- parameter sweep results:
  - ranked configuration table
  - selected best configuration
  - apply-to-backtest action
  - sweep CSV export
- walk-forward results:
  - summary cards
  - window-by-window table
  - selected training configuration per window
  - forward-test metrics
  - walk-forward CSV export
- HTML report link

Analyzer bucket behavior:

- call the backend trade analyzer bucket API after a backtest completes or when a trade CSV is selected for analysis
- show only bucket sections supported by the available trade columns
- strategy summary should be available for normal exported backtest trades because they include `Strategy`
- composite score, relative strength, and relative volume summaries should appear when the trade source preserves scanner candidate metadata
- each bucket table should include trades, win rate, average return, median return, best trade, worst trade, and profit factor
- provide an `Export Analyzer Bucket CSVs` action that writes one CSV per available bucket table
- generated HTML trade analysis reports should include the same available bucket sections

Parameter sweep behavior:

- call the backend parameter sweep optimizer from Backtest Results or Backtest setup
- generate combinations from selected backtest config values and strategy config field values
- rank by expectancy by default, with alternatives for average return, win rate, profit factor, or trade count
- filter low-sample rows with a configurable minimum trade count
- show the current best row first and include its hold days, minimum history, overlap mode, entry reset policy, strategy config values, trades, win rate, average return, expectancy, profit factor, best trade, and worst trade
- `Apply Configuration` should copy the selected row values into the normal Backtest controls without rerunning automatically
- `Run Backtest` from a selected sweep row should run the full backtest using those values
- `Export Parameter Sweep CSV` should save the ranked sweep table
- long-running sweeps should use the same job/progress model as scanner and backtest jobs
- display a research disclaimer that optimized values are historical results and may overfit

Entry policy behavior:

- overlap mode controls whether another trade can open while a prior trade is still active
- entry reset policy controls whether another signal can count before the strategy setup has reset
- `None` keeps existing behavior and permits repeated signals according to overlap settings
- `Signal off` requires the strategy signal to become false before the next signal can open a new trade
- reset policy should be visible in normal backtest config, parameter sweep rows, walk-forward selected settings, and exported CSVs

Walk-forward behavior:

- expose walk-forward as a mode or tab inside Backtest, next to Standard Backtest and Parameter Sweep
- generate rolling windows from start date, end date, training months, forward-test months, and step months
- for each window, run parameter sweep only on the training period
- apply the winning training configuration to the next forward-test period without re-optimizing
- show windows tested, forward windows with trades, profitable forward windows, average forward return, average forward expectancy, and average forward profit factor
- window rows should show train period, test period, selected settings, training metrics, and forward-test metrics
- `Apply Stable Configuration` should copy a selected or most frequent successful configuration into Backtest controls without claiming future performance
- `Export Walk-Forward CSV` should save all window-level results
- display a disclaimer that walk-forward tests historical generalization and is not a forecast

### Portfolio Simulation

Purpose: convert trade CSV into portfolio-level results.

Controls:

- trade CSV selector
- source backtest config display when the source is a backtest result
- starting cash
- max positions
- position sizing
- commission
- slippage
- stop-loss/trailing-stop options

Output:

- total return
- CAGR
- max drawdown
- Sharpe ratio
- equity curve
- position/trade table
- report export

### Trade Journal

Purpose: track actual manual trades.

Controls:

- add trade
- close trade
- import/export journal

Output:

- open trades
- closed trades
- realized returns
- journal summary

## Reports Index Service

Keep reports file-based in version one. Do not add a reports database until there is a clear need for report annotations, sharing, retention automation, or multi-user access.

Create:

- `src/scanner/reports/report_index.py`

Purpose:

- scan configured report/output folders
- identify generated report and export files
- infer report metadata from filenames and file stats
- return a structured report list to the API/UI
- handle missing or moved files without crashing the Reports page

Default discovery roots:

- `output/`
- any configured report folders from settings

Included file types:

- `.html`
- `.csv`
- `.json`
- `.png` only if generated chart/report assets need to be shown later

Ignored files:

- hidden files
- temp files
- cache databases
- lock files
- unknown binary files
- partial downloads
- files outside configured report roots

Report type inference:

- `daily_scanner_report_*.html` -> `daily_scanner`
- `backtest_*.html` -> `backtest`
- `portfolio_report*.html` -> `portfolio`
- `trade_analysis*.html` -> `trade_analysis`
- `journal*.html` -> `journal`
- `ticker_summary*.csv` -> `ticker_summary_csv`
- `strategy_summary.csv` -> `analyzer_bucket_csv`
- `*_buckets.csv` -> `analyzer_bucket_csv`
- `parameter_sweep*.csv` -> `parameter_sweep_csv`
- `*_sweep_results.csv` -> `parameter_sweep_csv`
- `walk_forward*.csv` -> `walk_forward_csv`
- `*_walk_forward_results.csv` -> `walk_forward_csv`
- `*.csv` -> `csv_export`
- unknown included file -> `other`

Report metadata model:

```python
class ReportMetadata:
    id: str
    name: str
    type: str
    created_at: datetime | None
    modified_at: datetime
    path: str
    relative_path: str
    size_bytes: int
    source: str | None
    strategy: str | None
    ticker_or_scope: str | None
    exists: bool
    openable: bool
```

Report IDs:

- use a stable id derived from normalized relative path plus modified timestamp or content hash
- do not expose arbitrary absolute paths as public API ids
- reject path traversal attempts when opening or downloading files

API behavior:

- `GET /api/reports` returns indexed report metadata with optional filters
- `GET /api/reports/{report_id}` returns one report metadata object
- `GET /api/reports/{report_id}/download` streams the file
- `POST /api/reports/{report_id}/open` opens the local file in the default browser/app where supported
- `POST /api/reports/{report_id}/reveal` opens Finder/Explorer to the file location where supported
- if reveal is not practical on a platform, return the local path and let the UI offer `Copy Path`

UI behavior:

- Reports page indexes files without rerunning analysis
- `Open` opens HTML reports in the browser and CSVs in the default app where supported
- `Download` streams the file through the local API
- `Reveal File` opens Finder/Explorer when available
- broken or missing files should show a clear `File not found` state
- filtered report tables should not fail if one file disappears between index and open

Retention:

- do not auto-delete reports in version one
- show file size and modified date so users can manually manage files
- defer retention settings until users need cleanup automation
- future retention options can include keep forever, keep last N days, or keep last N reports

Tests:

- unit test indexing from a temp `output/` folder
- unit test ignored files are excluded
- unit test report type inference
- unit test stable report ids
- unit test path traversal is rejected
- unit test missing files return a clean not-found result
- API test `GET /api/reports`
- API test download returns 404 for missing files
- component-test Reports page broken file state
- component-test Open, Download, and Reveal/Copy Path actions

## Backend API Design

Create `src/scanner/api/`.

Initial endpoints:

- `GET /api/health`
- `GET /api/settings`
- `GET /api/cache/overview`
- `POST /api/cache/warmup`
- `GET /api/jobs/{job_id}`
- `GET /api/strategies`
- `POST /api/scans`
- `GET /api/scans/{job_id}`
- `GET /api/watchlist/latest`
- `POST /api/backtests`
- `GET /api/backtests/{job_id}`
- `POST /api/portfolio/simulations`
- `GET /api/reports`
- `GET /api/reports/{report_id}`

Long-running work should run as tracked jobs. The UI should poll job status first; WebSockets or server-sent events can be added later.

`GET /api/strategies` should return strategy metadata used by scanner, backtest, and settings screens: strategy key, display name, category, default config values, configurable fields, allowed enum values, and field labels/help text. The UI should render strategy selectors and Strategy Rules settings from this response instead of hard-coding strategy names.

## Job Progress Model

Create a shared progress object:

- `job_id`
- `status`: queued, running, complete, failed, stopped
- `started_at`
- `finished_at`
- `message`
- `current_step`
- `total_steps`
- `symbols_total`
- `symbols_checked`
- `symbols_kept`
- `symbols_skipped`
- `provider_batches_attempted`
- `provider_batch_limit`
- `provider_symbols_attempted`
- `provider_symbol_limit`
- `elapsed_seconds`
- `estimated_seconds_remaining`
- `rate_limited`
- `output_paths`

This gives the UI enough information to show meaningful first-run progress.

## Implementation Phases

### Phase 1: Backend Wrapper

- Add FastAPI dependency.
- Create API app entry point.
- Wrap existing scanner/cache/backtest functions without changing CLI behavior.
- Add job registry for long-running tasks.
- Add cache overview endpoint.
- Add tests for API health, cache overview, and job lifecycle.

### Phase 2: Cache Warmup UI

- Create Vite React app under `ui/`.
- Add cache overview card.
- Add cache warmup form.
- Add batch progress display with ETA.
- Add rate-limit warning state.
- Add tests for progress formatting and API client behavior.

### Phase 3: Scanner UI

- Add scanner form.
- Run scan as a background job.
- Display watchlist table.
- Add CSV/report links.
- Add cache/provider summary.

### Phase 4: Backtest UI

- Add backtest form.
- Display summary metrics.
- Display trade table and charts.
- Link/export trade CSV and HTML report.

### Phase 5: Portfolio And Journal UI

- Add portfolio simulation form and result charts.
- Add manual trade journal screens.
- Keep CSV compatibility.

### Phase 6: Broker Connections

- Add Settings / Broker Connections screen.
- Support read-only broker credentials or OAuth, depending on broker.
- Validate connection and show account identity.
- Show paper/live account mode clearly.
- Store credentials locally.
- Add journal sync from broker executions and positions.
- Require user confirmation before applying matched fills to journal.
- Do not place trades from this app in version one.

### Phase 7: Packaging

- Add one command to run the local web UI.
- Add frontend production build command.
- Serve the built frontend from the FastAPI backend for normal local use.
- Document Mac and PC setup.
- Defer Electron, Tauri, or other native desktop packaging until the local web UI is stable.

## Local Web UI Launch Strategy

Build the UI as a local browser-based application first. Version one should run on Mac and PC without requiring a hosted server or native desktop packaging.

Development mode:

- backend runs with `uvicorn` from the existing Python environment
- frontend runs with Vite dev server from `ui/`
- Vite proxies API requests to the local FastAPI backend
- frontend hot reload stays available for UI development

Production/local-user mode:

- build the frontend with `npm run build`
- write static assets to `ui/dist/`
- serve `ui/dist/` from the FastAPI app
- keep API routes under `/api/...`
- route all non-API paths back to the frontend app shell
- run everything from one Python command

The final launch command should be:

```bash
PYTHONPATH=src venv/bin/python src/run_ui.py
```

`src/run_ui.py` should:

- verify required Python dependencies are installed
- verify the frontend build exists, or print the command needed to build it
- start the FastAPI backend on a local port, default `127.0.0.1:8000`
- detect if the default port is busy and either choose the next available port or show a clear error
- print the local URL, for example `http://127.0.0.1:8000`
- optionally open the browser automatically unless `--no-browser` is passed
- write backend logs to the terminal and preserve existing CLI logging behavior
- shut down cleanly on Ctrl+C

Useful launch options:

- `--host`, default `127.0.0.1`
- `--port`, default `8000`
- `--no-browser`
- `--reload` for development
- `--frontend-dev-server` to point at Vite during development

Native desktop packaging is explicitly deferred. Reevaluate packaging only after the local web UI proves stable and one of these needs becomes real:

- non-technical users need a double-click installer
- users struggle with Python/Node setup
- background/tray behavior is needed
- file association or OS-level notifications become important
- credential storage requires tighter OS integration
- distributing to multiple machines becomes a normal workflow

If packaging becomes necessary later, evaluate:

- Tauri, if small bundle size and OS integration matter most
- Electron, if the team needs the broadest mature desktop ecosystem
- a Python launcher or installer, if the main goal is easier startup while keeping the browser UI

## Testing Strategy

- Backend unit tests for API handlers.
- Service tests should continue covering scanner/backtest/cache behavior.
- Frontend component tests for forms, tables, and progress states.
- Playwright smoke tests for:
  - cache overview page
  - cache warmup progress
  - scanner run flow
  - backtest run flow

## Suggested First Commands

Development backend:

```bash
PYTHONPATH=src venv/bin/uvicorn scanner.api.app:app --reload
```

Development frontend:

```bash
cd ui
npm run dev
```

Final user command should eventually become:

```bash
PYTHONPATH=src venv/bin/python src/run_ui.py
```

## Resolved Implementation Decisions

- Use TanStack Query for UI server state, polling, cache invalidation, and long-running job status. Keep a small plain `fetch` API client underneath it so API calls stay testable.
- View reports as generated local HTML/files in version one. The UI should index, open, download, and reveal report files instead of rebuilding every report as native UI.
- Add a dedicated cache warmup CLI command in addition to the UI flow. The CLI and UI should call the same backend/cache service code so request throttling, cache-only preview, and rate-limit handling stay consistent.
- Build the local web UI first. Defer native desktop packaging until the web UI stabilizes and there is a clear need for installation, tray integration, file association, or simpler non-technical setup.
- Support Fidelity as a first-class broker workflow because the primary user trades there. Implement Fidelity support through a guaranteed file-import connector first, then add authorized data-sharing sync if a practical Fidelity Access or aggregator integration is available. Keep Interactive Brokers as the first direct API broker connector because it supports the read-only API model needed for automated positions, executions, and closed-trade sync.
- Store broker credentials in the OS keychain/keyring where practical. Use encrypted local config only as a fallback when keychain/keyring support is unavailable.
- Do not add app login while the application remains local-only. Add app accounts, sessions, roles, and hosted authentication only if the app becomes hosted or multi-user.

## Broker Connector Strategy

Broker support should be adapter-based. The Journal, Broker Connections UI, and matching logic should work against normalized broker models, not against a broker-specific API.

Version-one priority:

1. Fidelity file import connector for the user's current brokerage workflow.
2. Interactive Brokers direct API connector for automated read-only sync.
3. Fidelity authorized data-sharing connector if a practical Fidelity Access or aggregator path is available.

This avoids blocking Fidelity users on direct API availability while still preserving the long-term read-only broker-sync architecture.

## Fidelity Connector

Fidelity must work for journal review even if direct automated sync is limited. Public Fidelity material describes Fidelity Access as a way for customers to share account data with authorized third-party websites and applications. Treat this as an account-data sharing path, not as a guaranteed retail trading/execution API for this app.

Initial Fidelity support should be file-import based:

- add `FidelityImportConnector`
- allow the user to import Fidelity activity/history exports from the local filesystem
- parse executions, positions, closed trades, fees, and account identifiers when present in the export
- normalize imported rows into the same broker models used by direct broker connectors
- show an import preview before journal data changes
- match imported Fidelity executions to planned trades by ticker, side, date/time window, quantity, and expected entry area
- route matched active trades to `Open Trades`
- route matched closed trades to `Historical Ledger`
- keep imported actual execution fields read-only after confirmation
- support repeated imports without duplicating previously imported executions

Fidelity import UI:

- Settings / Broker Connections should include broker selector option `Fidelity`
- Fidelity connection mode should show `File Import` initially
- user selects one or more Fidelity export files
- UI shows detected account, date range, row counts, matched trades, unmatched executions, and duplicate rows
- user reviews and applies selected matches
- app stores import history and source file metadata locally, but not the user's Fidelity website credentials

Fidelity future sync path:

- investigate Fidelity Access or a supported data aggregator only for read-only account/transaction sync
- use a broker-hosted or approved-provider-hosted authorization flow
- user should authenticate on Fidelity's or the approved provider's page, not in this app
- app should receive only an authorization result, token, or connection reference
- do not ask users to paste Fidelity website credentials into this app
- do not screen-scrape Fidelity
- do not build trade placement for Fidelity
- if an authorized sync path is added, keep the same `BrokerConnector` interface and journal matching flow

Fidelity-specific failure states:

- unsupported export format
- missing required columns
- ambiguous account
- date range already imported
- duplicate execution detected
- unmatched symbol or option contract
- split/partial fill requiring manual review
- import file contains no trades for selected range

Fidelity tests:

- unit test Fidelity export parsing with representative fixture files
- unit test duplicate detection across repeated imports
- unit test partial-fill grouping
- unit test matching imported executions to planned trades
- unit test missing-column and unsupported-format errors
- integration-test import preview and apply flow with fake Fidelity export data
- component-test Fidelity import mode in Broker Connections

## Interactive Brokers Connector

Implement Interactive Brokers as the first direct API broker connector for read-only journal sync. The connector should be isolated behind the same broker adapter interface so the Journal, Broker Connections UI, and matching logic do not depend directly on IBKR-specific API calls.

Initial integration path:

- Start with IBKR's current API documentation on IBKR Campus.
- Prefer an HTTP/API-gateway style integration for the local app where practical.
- Keep the connector design compatible with TWS API / IB Gateway if a local gateway is required for reliable positions, executions, or paper-account support.
- Do not use deprecated standalone TWS API documentation as the source of truth when implementing.

Connector interface:

```python
class BrokerConnector:
    def validate_connection(self) -> BrokerConnectionStatus: ...
    def list_accounts(self) -> list[BrokerAccount]: ...
    def get_account_profile(self, account_id: str) -> BrokerAccountProfile: ...
    def list_open_positions(self, account_id: str) -> list[BrokerPosition]: ...
    def list_orders(self, account_id: str, start_date: date, end_date: date) -> list[BrokerOrder]: ...
    def list_executions(self, account_id: str, start_date: date, end_date: date) -> list[BrokerExecution]: ...
    def list_closed_trades(self, account_id: str, start_date: date, end_date: date) -> list[BrokerClosedTrade]: ...
```

Version one must not expose connector methods for placing, modifying, or canceling orders.

Connection setup:

- add `src/scanner/brokers/`
- add `InteractiveBrokersConnector`
- add Settings / Broker Connections API endpoints for connection test, account list, sync preview, and apply matches
- support paper/live account labeling
- show connected account identifier, account mode, last sync time, token/session status, and read-only status
- require the user to confirm the connected account before syncing journal data

Credential/session handling:

- store secrets in the OS keychain/keyring where practical
- store only non-secret connection metadata in local app config
- do not write API secrets, session tokens, or passwords into CSV, logs, reports, or screenshots
- mask credentials in the UI
- support disconnect/revoke locally by deleting stored credentials/session data
- handle expired sessions with a clear reconnect prompt

Broker data models:

- `BrokerAccount`
- `BrokerAccountProfile`
- `BrokerConnectionStatus`
- `BrokerPosition`
- `BrokerOrder`
- `BrokerExecution`
- `BrokerClosedTrade`
- `BrokerSyncPreview`
- `BrokerSyncMatch`

Normalize IBKR data before it reaches the journal:

- ticker/symbol
- instrument type
- side
- quantity
- average fill price
- order id
- execution id
- commission/fees when available
- trade date/time with timezone
- account id
- paper/live mode
- source broker

Sync flow:

1. User opens Settings / Broker Connections.
2. User connects Interactive Brokers in read-only sync mode.
3. App validates connection and lists available accounts.
4. User selects account and confirms paper/live mode.
5. User opens Journal and clicks Sync Broker Trades.
6. App fetches open positions, recent orders, executions, and closed trades for the selected date range.
7. App builds a sync preview before changing journal data.
8. App matches broker executions to planned trades by ticker, side, date/time window, and expected entry area.
9. User reviews matched and unmatched broker records.
10. App applies selected matches only after user confirmation.

Journal update rules:

- matched active positions appear in `Open Trades`
- matched closed trades appear in `Historical Ledger`
- broker-synced actual execution fields are read-only in journal tables
- planned trades remain editable until matched to broker activity
- unmatched executions can be linked manually to a planned trade
- unmatched planned trades remain planned unless the user cancels/deletes them
- corrections to actual fills happen through broker sync review, matching/linking, or broker-side correction

Failure states:

- not connected
- session expired
- invalid credentials
- insufficient permissions
- paper/live account mismatch
- no accounts found
- no executions found for selected date range
- API unavailable
- partial sync completed
- duplicate broker execution already imported

Testing:

- unit test IBKR connector mapping from raw broker payloads into normalized broker models
- unit test connection-state handling for valid, expired, invalid, and insufficient-permission states
- unit test matching planned trades to broker executions by ticker, side, date window, and entry area
- unit test duplicate execution detection
- unit test that no order-placement methods exist on the version-one connector interface
- integration-test sync preview with fake broker data
- component-test Broker Connections states and Journal sync preview/apply flow

## Local Credential Storage

Broker credential storage should be local-only and broker-specific. The app should never require a hosted account system just to store broker credentials.

Storage rules by broker mode:

- Fidelity file import mode stores no Fidelity login credentials.
- Fidelity file import mode may store non-secret import metadata such as source file name, import timestamp, detected account label, date range, row count, and import hash.
- Direct API broker connectors may store API keys, secrets, refresh tokens, or session references only in the OS keychain/keyring where practical.
- Encrypted local config is allowed only as a fallback when OS keychain/keyring support is unavailable or explicitly disabled.
- Plaintext local config must never contain broker API secrets, session tokens, refresh tokens, or brokerage passwords.

Implementation plan:

- add `src/scanner/security/credential_store.py`
- expose a small `CredentialStore` interface:
  - `set_secret(service, account, value)`
  - `get_secret(service, account)`
  - `delete_secret(service, account)`
  - `has_secret(service, account)`
  - `list_metadata()`
- implement an OS keychain/keyring backend first
- implement encrypted local fallback only after keychain/keyring behavior is defined
- keep non-secret connection metadata in app settings, not in the secret store
- separate secret identifiers by broker, account id, environment, and credential type

Suggested secret identifiers:

- service: `swing-scanner.broker.interactive-brokers`
- account: `{account_id}:api_key`
- account: `{account_id}:api_secret`
- account: `{account_id}:refresh_token`
- account: `{account_id}:session_token`

Non-secret metadata allowed in local config:

- broker name
- account label
- masked account id
- paper/live mode
- connection mode, for example `file_import`, `api`, or `oauth`
- last sync timestamp
- last import timestamp
- import file hash
- read-only permission status
- credential presence flags, for example `has_api_key: true`

UI behavior:

- mask all credential fields by default
- never display full stored secrets after save
- show whether credentials are present, missing, expired, or invalid
- provide `Test Connection`, `Disconnect`, and `Delete Stored Credentials` actions
- explain that Fidelity file import does not require Fidelity website credentials
- require confirmation before deleting stored credentials or disconnecting an account

Logging and export rules:

- never log secrets or full tokens
- never include secrets in reports, CSV exports, screenshots, or debug bundles
- redact suspicious credential-shaped values in error messages where practical
- include only masked account ids and broker labels in user-facing logs

Fallback behavior:

- if OS keychain/keyring is unavailable, show a warning before using encrypted local fallback
- if encrypted local fallback is unavailable, allow file-import broker modes but disable direct API broker connection save
- if credentials cannot be read, mark the broker connection as `Reauthentication required`

Tests:

- unit test keychain-backed `CredentialStore` with a fake backend
- unit test metadata is separated from secrets
- unit test secrets are not written to local settings files
- unit test disconnect deletes stored secrets and preserves non-secret journal history
- unit test logs and errors redact known secret values
- component-test masked credential fields and delete confirmation flow

## Authentication Model

## Settings

Settings should include scanner and recommendation defaults that affect generated trade plans.

Recommendation defaults:

- default reward/risk multiple, initially `2.0`
- default suggested hold period, initially `5` trading days
- default stop method, initially `2 * ATR`

The default reward/risk multiple should be configurable under Settings and used when calculating the suggested target/exit shown in Candidate Detail, the manual trade checklist, journal planned trades, exports, and daily HTML reports. The Daily Scanner table should not display reward/risk directly.

### Strategy Rules

Purpose: let users tune strategy thresholds without editing code.

Implementation notes:

- expose strategy settings from backend strategy config metadata where possible
- do not hard-code the frontend to Pullback/Breakout only
- persist rule changes locally and apply them to future scanner runs, backtests, and generated recommendations
- store the strategy config snapshot with planned trades so old recommendations do not silently change

Initial rule controls:

- Pullback: max distance from MA20, minimum relative volume, minimum relative strength
- Breakout: max distance from 52-week high, minimum relative volume, minimum relative strength
- Bounce: anchor MA segmented control (`MA20` / `MA50`), max distance from anchor, prior-day-high confirmation toggle, optional relative-volume threshold, minimum relative strength

There are two separate authentication concerns.

### Local App Access

For version one, do not add user login if the app runs locally on the user's machine.

The app should bind to loopback by default:

```text
http://127.0.0.1:8000
```

The user's operating system login is enough for local access. App accounts, sessions, roles, password reset, and hosted authentication are out of scope for version one.

Implementation rules:

- default host is `127.0.0.1`, not `0.0.0.0`
- `src/run_ui.py` should print the exact local URL it starts
- browser auto-open should open the loopback URL only
- API routes should assume a local trusted user, not an authenticated web session
- do not add app user tables, password storage, login forms, sessions, roles, email verification, or password reset flows in version one
- do not expose the local API over the public network by default
- if a user explicitly overrides `--host`, show a warning when the host is not loopback

App login should be reconsidered only if one of these becomes true:

- the app is hosted outside the user's machine
- more than one user shares the same running app instance
- the app is exposed on a LAN or public network
- roles or permissions are needed
- remote browser access becomes a supported workflow
- broker or journal data is stored on a shared server

Broker authentication is separate from app login. Even without app login, broker sync can still require API credentials, OAuth, tokens, or file imports, depending on the selected broker.

Tests:

- unit test `run_ui.py` defaults to `127.0.0.1`
- unit test non-loopback `--host` shows a warning
- API smoke test should not require an app login session in local mode
- component tests should not include app login screens for version one
- broker connection tests should still require broker-specific authentication or import files where applicable

### Broker Authentication

Broker authentication is required for broker sync.

Create a Settings / Broker Connections flow where the user can:

1. Choose broker.
2. Enter API credentials or start OAuth, depending on broker.
3. Validate connection.
4. Select account if multiple accounts are available.
5. Confirm paper vs live mode.
6. Confirm read-only sync.
7. Store credentials locally.

Broker-hosted authentication:

- If a broker supports OAuth, Fidelity Access-style data sharing, or an approved aggregator login, the app should open that broker/provider-hosted authorization flow.
- The user enters brokerage username/password only on the broker or approved provider page.
- The app receives only the authorization result, token, or connection reference needed for read-only sync.
- The app must not render its own username/password form for Fidelity or any other brokerage website login.
- The app must not ask users to paste brokerage website credentials into settings.
- The app must not automate browser login or screen-scrape brokerage websites.

Allowed connection modes:

- file import, such as Fidelity activity/history exports
- broker-hosted OAuth or equivalent approved authorization
- approved data-sharing aggregator flow
- direct API key/secret only where the broker intentionally provides API credentials for client applications

Disallowed connection modes:

- collecting brokerage website username/password in this app
- storing brokerage website passwords
- logging into Fidelity on the user's behalf
- screen scraping brokerage websites
- bypassing broker multi-factor authentication

Version one broker sync should be read-only:

- fetch open positions
- fetch orders
- fetch executions/fills
- fetch closed trades where supported
- update journal only after user confirmation
- never place, modify, or cancel trades

Journal data ownership:

- `Planned Trades` is the user-editable planning view.
- Daily Scanner and Candidate Detail `Add To Journal` actions create rows in `Planned Trades`.
- Users can edit or delete/cancel planned trades before they become actual broker positions.
- `Open Trades` is a read-only view populated from broker-synced open positions and executions.
- `Historical Ledger` is a read-only view populated from broker-synced closed trades and matched executions.
- Actual entry, exit, shares, fees, and realized P/L should not be edited inline in `Open Trades` or `Historical Ledger`.
- Corrections to actual trade data should happen through broker sync review, matching/linking, or broker-side correction.
