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
- State: React Query or simple fetch hooks
- Storage: existing SQLite cache and CSV outputs
- Runtime: local dev server started from one command

FastAPI is a good fit because the app already has Python service logic. React/Vite is a good fit because the UI will need interactive tables, progress updates, cache status, filters, and reports.

## First User Experience

The first screen should be the scanner workspace, not a marketing page.

Primary first-run workflow:

1. User chooses universe: `sp500`, `djia`, `nasdaq`, `nyse`, or `all`.
2. User chooses strategy: pullback, breakout, or both.
3. User sets optional price range, for example `$20` to `$50`.
4. UI shows current cache status:
   - cached tickers
   - cached bars
   - latest cached bar
   - last successful refresh
   - days since refresh
5. User starts a cache warmup or scan.
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
- strategy selector
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
- pullback/breakout flags
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

### Backtest

Purpose: test a strategy over a selected universe, watchlist, or ticker.

Controls:

- ticker/universe/watchlist source
- strategy
- hold days
- history period
- price range
- export trades

Output:

- backtest summary
- trade table
- return distribution
- monthly summary
- ticker summary
- HTML report link

### Portfolio Simulation

Purpose: convert trade CSV into portfolio-level results.

Controls:

- trade CSV selector
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

## Backend API Design

Create `src/scanner/api/`.

Initial endpoints:

- `GET /api/health`
- `GET /api/settings`
- `GET /api/cache/overview`
- `POST /api/cache/warmup`
- `GET /api/jobs/{job_id}`
- `POST /api/scans`
- `GET /api/scans/{job_id}`
- `GET /api/watchlist/latest`
- `POST /api/backtests`
- `GET /api/backtests/{job_id}`
- `POST /api/portfolio/simulations`
- `GET /api/reports`
- `GET /api/reports/{report_id}`

Long-running work should run as tracked jobs. The UI should poll job status first; WebSockets or server-sent events can be added later.

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

- Add one command to run backend and frontend in development.
- Add production build command.
- Document Mac and PC setup.
- Consider Electron or Tauri only if users need a double-click desktop app.

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

## Open Decisions

- Whether to use React Query or plain fetch hooks.
- Whether reports should be viewed as generated HTML files or rendered as native UI screens.
- Whether cache warmup should have a dedicated CLI command in addition to the UI flow.
- Whether a later packaged desktop app is worth the maintenance cost.
- Which broker connector to implement first.
- Whether broker credentials should be stored in the OS keychain/keyring or encrypted local config.
- Whether the UI needs app login if the app remains local-only.

## Authentication Model

## Settings

Settings should include scanner and recommendation defaults that affect generated trade plans.

Recommendation defaults:

- default reward/risk multiple, initially `2.0`
- default suggested hold period, initially `5` trading days
- default stop method, initially `2 * ATR`

The default reward/risk multiple should be configurable under Settings and used when calculating the suggested target/exit shown in Candidate Detail, the manual trade checklist, journal planned trades, exports, and daily HTML reports. The Daily Scanner table should not display reward/risk directly.

There are two separate authentication concerns.

### Local App Access

For version one, do not add user login if the app runs locally on the user's machine.

The app should run at a local address such as:

```text
http://localhost:8000
```

The user's operating system login is enough for local access. App accounts, sessions, roles, password reset, and hosted authentication should only be added if the app later becomes hosted or multi-user.

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
