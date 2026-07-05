# UI Use Cases And Flows

## Goal

Define the first version of the user interface before implementation.

The UI should help an investor run the scanner, manage cache warmup safely, review candidates, backtest strategies, simulate portfolio behavior, and track manual trades.

## Primary Users

### Individual Investor

Wants a daily workflow:

- update/cache market data safely
- find pullback and breakout candidates
- review candidate risk/reward
- decide whether to manually place trades
- track actual trade results

### Power User

Wants deeper analysis:

- run historical backtests
- compare hold periods
- simulate portfolio constraints
- review reports and exported CSVs
- tune scanner settings

## Navigation Model

Primary navigation:

- Dashboard
- Daily Scanner
- Candidates
- Backtest
- Portfolio
- Journal
- Reports
- Settings

Cache setup is not a persistent primary navigation item. It is a first-time or maintenance flow launched from Dashboard when cache is empty/stale, or from Settings / Cache through Warm Cache and Cache-Only Preview actions.

The app should open to Dashboard.

## Use Case 1: First-Time Setup / Cache Warmup

### Purpose

Help a first-time user build enough local cache to scan without immediately hitting Yahoo rate limits.

### Entry Point

Dashboard warning card:

> Cache is mostly empty. Start setup to warm market data safely.

Primary button:

> Start Cache Warmup

### Flow

1. User launches the cache warmup flow from Dashboard or Settings / Cache.
2. UI shows cache overview:
   - cached tickers
   - cached bars
   - latest cached bar
   - last successful refresh
   - days since refresh
3. User selects:
   - universe
   - optional min/max price
   - mode: Warm Cache or Cache-Only Preview
   - batch size
   - max batches
   - delay between batches
4. User can hover or click the mode info icon to see:
   - Warm Cache fetches missing recent price data in controlled batches and stores it locally.
   - Cache-Only Preview makes no provider calls and only checks existing cached data.
5. UI estimates:
   - symbols to inspect
   - maximum provider batches
   - minimum estimated wait from configured delay
6. User clicks the primary action:
   - Start Warmup in Warm Cache mode
   - Run Preview in Cache-Only Preview mode
7. UI shows progress:
   - current batch
   - total planned batches
   - symbols checked
   - symbols kept
   - symbols skipped
   - provider batches attempted
   - ETA
8. If rate limit happens:
   - UI stops provider calls
   - shows clear warning
   - suggests waiting and resuming later
9. On success:
   - UI updates cache overview
   - user can continue to Daily Scanner

### Success State

Show:

- cache warmup complete for this batch
- cached tickers increased
- days since refresh
- Continue to Scanner button

### Error / Stop State

Show:

- rate limit detected
- provider batches completed before stop
- cached data preserved
- suggested wait time
- Resume Later button
- Run Cache-Only Scan button

## Use Case 2: Daily Scan

### Purpose

Generate today's watchlist for configured strategy candidates.

### Entry Point

Dashboard primary action:

> Run Daily Scan

### Flow

1. User opens Daily Scanner.
2. User selects:
   - universe
   - strategy: all enabled strategies or one/more backend-defined strategies, initially Pullback, Breakout, and Bounce
   - price range
   - history period
   - cache-only mode
3. UI shows current cache status before running.
4. User clicks Run Scan.
5. UI shows:
   - symbols analyzed
   - skipped symbols
   - cache hits/misses
   - provider calls
   - elapsed time
6. UI refreshes latest available provider prices for the final candidate list.
7. UI displays watchlist table.
8. User can:
   - sort by composite score
   - filter by strategy
   - open candidate detail
   - export CSV
   - generate daily HTML report

Daily Scanner page-level actions:

- Export CSV
- Generate Daily Report

These should be visible after a scan completes. Row-level `Add To Journal` actions should add the selected candidate to `Journal > Planned Trades`.

Daily Scanner CSV export behavior:

- users should be able to select one or more candidate rows
- `Export CSV` should support exporting selected candidates only
- if no rows are selected, `Export CSV` should default to the current filtered candidate set, not necessarily every scanned candidate
- users should have an explicit option to export all candidates from the scan
- export confirmation should show the row count, for example `Export 7 selected candidates`
- exported CSV should include adjusted values from Candidate Detail when they exist

Daily Scanner to Backtest handoff:

- users should be able to send selected or filtered scanner candidates directly to Backtest without exporting a CSV first
- when rows are selected, show `Backtest Selected`
- if no rows are selected, allow backtesting the current filtered candidate set
- Backtest should open with source prefilled as `Selected Daily Scanner Candidates (N)` or `Filtered Daily Scanner Candidates (N)`
- CSV export remains optional for external tools and archiving

Price handling:

- Strategy calculations may use cached historical daily bars.
- Final displayed candidate prices should use a fresh provider request for the narrowed candidate list.
- Watchlist, candidate detail, manual trade checklist, exports, and daily HTML report should show:
  - current price
  - price as of
  - price source
- Scanner table `Current Price` header should include an info icon.
- Info tooltip copy: `Current Price comes from Yahoo/latest provider data and may be delayed or stale. Confirm the live price in your trading platform, such as TradingView or thinkorswim, before placing a trade.`
- If fresh price refresh fails, fall back to latest cached close and label the source as `Cached Close`.
- Yahoo data should be presented as latest available provider data, not guaranteed real-time quotes.

### Success State

Watchlist table with:

- ticker
- strategy flags
- composite score
- current price
- price as of
- price source
- relative strength
- ATR
- relative volume
- moving averages
- entry area
- suggested stop
- suggested exit
- suggested hold time

Reward/risk should not appear in the scanner table. It should appear in Candidate Detail, where the UI can show the configured multiple and explain the calculation.

Strategy options should come from backend strategy metadata rather than being hard-coded in the UI. The first configurable strategy set includes Pullback, Breakout, and Bounce.

The Bounce strategy is configurable and should expose MA20/MA50 anchor, maximum distance from anchor, prior-day-high confirmation, and optional relative-volume threshold settings.

### Empty State

Show:

- no candidates matched today
- number of symbols analyzed
- number skipped
- suggestion to broaden filters

## Use Case 3: Review Candidate Detail

### Purpose

Help the investor decide whether a candidate is worth manually trading.

### Entry Point

Click a ticker from the watchlist.

### Flow

1. User opens candidate detail.
2. UI shows summary metrics.
3. UI shows manual trade checklist.
4. User can drag entry zone, stop, and target/exit levels on the price chart.
5. Manual trade checklist values update as the user drags.
6. User can revert adjusted levels back to the original suggested values.
7. UI shows historical strategy performance for the ticker.
8. User can add candidate to journal as planned trade.

### Screen Content

Header:

- ticker
- current price
- price as of
- price source
- strategy signal
- composite score

Checklist:

- entry area
- suggested stop
- risk per share
- position size estimate
- suggested exit
- suggested hold time
- reward/risk
- notes

Reward/risk should use the user's configured default reward/risk multiple from Settings unless the user overrides it for this candidate.

Charts:

- price chart with moving averages
- resizable stock chart area
- draggable entry zone
- draggable target/exit level
- draggable stop level
- ATR/volume view
- historical backtest result for ticker

Interactive trade levels:

- Entry zone, stop, and target/exit should appear as draggable horizontal chart overlays.
- Dragging a level updates the matching checklist value immediately.
- Dragging entry should recalculate risk per share, suggested target/exit, reward/risk, and position size estimate unless the target has been manually overridden.
- Dragging stop should recalculate risk per share, reward/risk, and position size estimate.
- Dragging target/exit should recalculate reward/risk.
- If a value is changed manually, show an edited state next to the field.
- The original app-suggested values must be retained separately from user-adjusted values.
- Provide `Reset to Suggested` in the top-right of the Manual Trade Checklist panel header to restore entry area, stop, target/exit, reward/risk, risk per share, and position size estimate to their original suggested values.
- Adjusted entry area, stop, target/exit, hold time, and calculated checklist values should be reflected back in the Daily Scanner Results row for that candidate.
- Exports, daily HTML report, and planned journal trades should use the adjusted values when they exist, while preserving a reference to the original suggested values.

Resizable chart behavior:

- The price chart panel should support resizing, especially expanding width and height for detailed review.
- The resize affordance should be visible, for example a corner handle, expand button, or split-pane drag handle.
- Resizing should preserve the draggable entry, stop, and target overlays.
- Resizing should not overlap the Manual Trade Checklist; the layout should either adjust columns or allow a focused expanded chart mode.
- Expanded chart mode should keep the checklist accessible or provide a clear return control.
- The app should remember the user's last chart size locally when practical.

Actions:

- Add To Journal
- Export Candidate
- Open Report

## Use Case 4: Historical Backtest

### Purpose

Evaluate configured strategy behavior over a ticker, watchlist, selected scanner candidates, or universe.

### Flow

1. User opens Backtest.
2. User selects source:
   - ticker
   - universe
   - watchlist CSV
3. User selects:
   - strategy from backend metadata, initially Pullback, Breakout, Bounce, and any future registered strategies
   - hold days
   - history period
   - minimum history days, default `252`
   - overlap mode: allow overlapping trades by default, with an option to block overlap
   - optional price filter
4. User runs backtest.
5. UI displays summary and trade table.
6. User can export trades or generate HTML analysis report.

### Screen Content

Summary cards:

- total trades
- win rate
- average return
- expectancy
- best trade
- worst trade
- configuration context: hold days, history period, minimum history days, and overlap mode

Tables/charts:

- trades table
- top tickers by return
- top tickers by win rate
- analyzer buckets:
  - strategy summary
  - composite score buckets when the trade source includes `Composite Score`
  - relative strength buckets when the trade source includes `Relative Strength`
  - relative volume buckets when the trade source includes `Relative Volume`
- monthly results
- weekday results
- return distribution

Actions:

- Export Trade CSV
- Export Analyzer Bucket CSVs
- Generate HTML Report
- Simulate Portfolio

Backtest source behavior:

- Backtest can be launched directly from selected or filtered Daily Scanner candidates
- Backtest Results should show the source clearly, for example `Selected Daily Scanner Candidates (3)`
- the user should not need to export a CSV before running this backtest
- Backtest Results should show the `BacktestConfig` used for the run so users can interpret results correctly
- When a portfolio simulation is launched from a backtest result, the simulation should retain and display the source backtest config
- Analyzer bucket sections should be shown only when the backtest result has the required source columns. Older trade CSVs may only show strategy-level buckets.

## Use Case 5: Portfolio Simulation

### Purpose

Show what the trade results look like when realistic portfolio constraints are applied.

### Flow

1. User opens Portfolio.
2. User selects trade CSV or latest backtest result.
3. User configures:
   - starting cash
   - max open positions
   - position sizing
   - commission
   - slippage
   - stop-loss
   - trailing stop
4. User runs simulation.
5. UI displays portfolio-level results.

When the source is a backtest result, the page should show the backtest configuration that produced the trade list:

- strategy
- hold days
- history period
- minimum history days
- overlap mode

### Screen Content

Summary cards:

- total return
- CAGR
- max drawdown
- Sharpe ratio
- ending equity

Charts:

- equity curve
- drawdown curve

Tables:

- positions
- rejected trades
- monthly equity

Actions:

- Export Report
- Open Detailed Portfolio Report

These report actions should be visible after portfolio simulation results are available.

## Use Case 6: Manual Trade Journal

### Purpose

Track recommended trades, planned trades, and what the user actually bought and sold.

The scanner can suggest an entry area, stop, target/exit, hold time, reward/risk, and position size estimate. The user should be able to add that recommendation to the journal as a planned trade without claiming it was actually filled.

### Flow

1. User reviews a recommended candidate from Daily Scanner or Candidate Detail.
2. User clicks Add To Journal.
3. UI creates a planned trade using scanner recommendations:
   - ticker
   - strategy
   - recommended entry area
   - recommended stop
   - recommended exit/target
   - suggested hold time
   - reward/risk
   - position size estimate
   - notes
4. Planned trade appears in `Journal > Planned Trades` with status `Planned`.
5. User places the actual trade in their brokerage/trading platform.
6. User runs broker sync.
7. App matches broker fills/positions to planned trades where possible.
8. Matched active broker positions appear in `Open Trades`.
9. Matched closed broker trades appear in `Historical Ledger`.
10. UI calculates realized results and compares actual execution to the original recommendation.

Daily Scanner journal behavior:

- Daily Scanner `Add To Journal` should always create a planned trade, not an open or closed trade.
- The created item should appear in the `Planned Trades` tab.
- If the same ticker/strategy/date recommendation is already planned, the UI should prevent accidental duplicates or ask the user to confirm adding another planned trade.

### Screen Content

Planned trades:

- ticker
- strategy
- recommended entry area
- recommended stop
- recommended target/exit
- suggested hold time
- reward/risk
- planned position size
- status
- notes
- actions to edit, record actual entry, open candidate detail, and delete/cancel the planned trade

Planned Trades tab:

- this is the user-editable journal planning view
- default sort is most recent created date first
- users can edit planned entry, stop, target, hold time, notes, tags, and planned position size
- users can delete/cancel planned trade items directly from this view
- deleting/canceling a planned trade should require confirmation
- delete/cancel should remove the item from active planned trades without affecting historical closed trades
- if auditability is desired later, canceled planned trades can be retained with status `Canceled`, but they should not remain in the active planned list by default

Open trades:

- ticker
- strategy
- recommended entry
- entry date
- entry price
- actual shares
- stop
- target
- suggested hold time
- days held
- current price
- unrealized profit/loss
- distance to stop
- distance to target
- notes

The Journal tab order should be:

- Planned Trades
- Open Trades
- Historical Ledger
- Analytics

Do not include a separate `Closed` tab. Closed trades are historical records and should appear in `Historical Ledger`.

The `Open Trades` tab should appear directly to the right of `Planned Trades`. It shows all active positions and replaces any generic `Open` tab label.

Open Trades tab:

- all active open trades
- read-only view populated from broker-synced open positions and executions
- default sort is most recent entry date first
- current price
- unrealized return percent
- unrealized dollar profit/loss
- active stop
- active target
- distance to stop
- distance to target
- days held vs suggested hold time
- actions to open candidate detail and sync broker trades
- no inline editing of broker-synced actual execution fields
- any correction to actual fills should happen through broker sync/linking, not by editing this table directly

Closed trades:

- exit date
- exit price
- return percent
- result
- recommendation vs actual entry difference
- recommendation vs actual exit difference

Historical trade ledger:

- read-only view populated from broker-synced closed trades and matched executions
- all closed trades in one sortable/filterable table
- default sort is most recent trade first
- for closed trades, most recent means latest exit date
- for open trades, most recent means latest entry date
- for planned trades, most recent means latest created date
- each trade row colored by result:
  - green for winning trades
  - red for losing trades
  - neutral for scratch/breakeven trades
- ticker
- strategy
- planned vs actual entry
- planned vs actual exit
- entry date
- exit date
- days held
- shares
- return percent
- dollar profit/loss
- fees/slippage
- notes
- linked scanner recommendation, if available
- no inline editing of actual broker-synced execution fields
- corrections should happen through broker sync review, matching/linking, or broker-side correction where applicable

Filtering behavior:

- users filter by clicking a column header
- each column filter shows existing values from that column
- users select one or more values from the dropdown
- users should not need to manually type filter text for standard filters
- selected filters appear as removable chips above the table
- table summary stats recalculate from the filtered rows
- clear-all-filters action resets the ledger and stats

Column filters should support:

- ticker
- strategy
- result
- status
- entry month
- exit month
- broker account
- source
- tags

Pagination behavior:

- default page size should be `50`
- user can choose page size: `25`, `50`, `100`, or `All`
- pagination applies after filters and sorting
- summary stats and charts should use the full filtered data set, not only the visible page
- table footer should show visible range and filtered total, for example `Showing 1-50 of 312 filtered trades`
- export should export the full filtered data set, not just the current page
- selected page size should persist locally for the user

Actions:

- Add recommended trade from candidate detail
- Edit planned trade
- Sync broker trades
- Link unmatched broker execution to planned trade
- Cancel planned trade
- Delete/cancel planned trade from Planned Trades
- Export journal

Summary:

- planned trades
- open risk
- realized return
- win rate
- loss rate
- actual win/loss ratio
- average winner
- average loser
- profit factor
- expectancy
- total closed trades
- total winning trades
- total losing trades
- average win/loss

Historical analysis:

- percentage of successful trades
- win/loss count ratio
- average return by strategy
- average return by ticker
- best trade
- worst trade
- longest winning streak
- longest losing streak
- monthly journal performance
- cumulative realized P/L

Filtered analytics:

- all summary and historical analysis metrics should update based on the active ledger filters
- show both filtered count and total count, for example `18 of 37 closed trades`
- charts should reflect the filtered data set unless the user disables filter-linked analytics

### Broker Sync

If the user places paper or real trades through TradingView, the app should not depend on a TradingView user API for actual fills. TradingView's broker API is designed for broker partners, not individual users retrieving their own TradingView paper-trading data.

The app should instead support broker connectors that can import actual orders, positions, executions, and closed trades from the broker account used inside TradingView or another brokerage workflow.

Fidelity must be supported as a first-class workflow. If direct Fidelity sync is not available through an authorized account-data sharing integration, the app should support Fidelity activity/history file imports and apply the same journal matching and review flow used by direct broker connectors.

Flow:

1. User creates a planned trade from a scanner recommendation.
2. User places the trade manually in TradingView through their connected broker.
3. User clicks Sync Broker Trades in the Journal.
4. App queries the configured broker API.
5. App matches broker executions to planned journal trades by:
   - ticker
   - side
   - date/time window
   - approximate expected entry area
6. App updates actual entry fills, actual exit fills, shares, fees, and status.
7. User reviews unmatched executions and can manually link them.

Connector model:

- `BrokerConnector`
- `FidelityImportConnector`
- `InteractiveBrokersConnector`
- `list_open_positions()`
- `list_orders()`
- `list_executions(start_date, end_date)`
- `list_closed_trades(start_date, end_date)` if broker supports it

Initial broker sync screen:

- broker selector
- connection status
- sync date range
- read-only mode indicator
- matched trades
- unmatched broker executions
- unmatched planned journal trades

Security requirements:

- use read-only credentials where the broker supports them
- do not ask users to enter Fidelity website credentials into this app
- use broker-hosted or approved-provider-hosted authentication when automated broker sync is available
- the user should enter brokerage username/password only on the broker or approved provider page
- the app should receive only an authorization result, token, or connection reference
- do not screen-scrape brokerage websites
- never place trades from this app in version one
- keep credentials local
- clearly show what account is connected
- require user confirmation before applying matched fills to the journal

### Trade Statuses

- `Planned`: created from a scanner recommendation or manually entered idea; no actual entry fill yet.
- `Open`: actual entry fill recorded; position is active.
- `Closed`: actual exit fill recorded; realized return is calculated.
- `Canceled`: planned trade was not taken.

### Recommendation vs Actual Fields

Keep recommended and actual execution fields separate.

Recommended fields:

- recommended entry low/high
- recommended stop
- recommended exit/target
- suggested hold time
- estimated position size
- estimated reward/risk

Actual fields:

- actual entry date/time
- actual entry price
- actual shares
- actual exit date/time
- actual exit price
- actual fees/slippage if entered
- actual return percent

This lets the user review both decision quality and execution quality.

## Use Case 7: Reports

### Purpose

Let users reopen previous scanner, backtest, portfolio, and journal reports.

### Flow

1. User opens Reports.
2. UI indexes generated report files from configured output folders.
3. User filters by type/date.
4. User opens, downloads, reveals, or copies the path for a report file.
5. If a file is missing, UI shows a clear file-not-found state without rerunning analysis.

### Report Types

- daily scanner report
- backtest report
- trade analysis report
- portfolio report
- journal report
- CSV export

### Report Actions

- `Open`: open generated HTML reports in the browser and CSVs in the default app where supported.
- `Download`: stream the file through the local API.
- `Reveal File`: open Finder/Explorer to the file location where supported.
- `Copy Path`: fallback action when reveal is unavailable.

### Retention

- Version one should not auto-delete generated reports.
- Reports page should show file size and modified date so users can manually manage files.
- Retention automation can be added later if users need cleanup options.

## Use Case 8: Broker Connection Setup

### Purpose

Allow users to connect a broker account so the app can sync actual fills, positions, and closed trades into the journal.

This is separate from app login. For a local-only app, version one does not need user accounts or app authentication. The app should bind to `127.0.0.1` by default and rely on the user's operating system login for local access. Broker authentication is still required for broker sync or file import workflows where applicable.

### Entry Point

Settings navigation:

> Broker Connections

Settings navigation:

> Recommendation Defaults

Journal action:

> Sync Broker Trades

If no broker is connected, the Journal should route the user to Broker Connections.

### Flow

1. User opens Settings / Broker Connections.
2. User selects broker.
3. UI shows required auth method:
   - file import for Fidelity
   - API key / secret
   - OAuth login
   - refresh token
   - paper/live account selector
4. User connects account.
5. App validates credentials.
6. UI displays:
   - broker name
   - account label/id
   - paper or live mode
   - permission mode
   - last sync time
7. User confirms read-only sync mode.
8. User returns to Journal and clicks Sync Broker Trades.

## Use Case 11: Configure Recommendation Defaults

### Purpose

Allow the user to control defaults used when the app calculates suggested exits and manual trade checklist values.

### Entry Point

Settings navigation:

> Recommendation Defaults

### Flow

1. User opens Settings.
2. User selects Recommendation Defaults.
3. UI shows configurable defaults:
   - default reward/risk multiple
   - default suggested hold period
   - default stop method
   - strategy-specific rule defaults
   - default chart range and chart resize behavior
   - export/report defaults
4. User updates the reward/risk multiple.
5. App saves the setting locally.
6. Candidate Detail, manual trade checklist, planned journal trades, exports, and daily HTML reports use the configured default.

### Required Fields

- default reward/risk multiple, initially `2.0`
- default suggested hold period, initially `5` trading days
- default stop method, initially `2 * ATR`
- ATR period, initially `14`
- entry zone method, initially `Strategy default`
- default risk per trade, initially `1%`
- default chart range
- remember resized candidate chart setting
- default CSV export scope
- include adjusted checklist values in exports and reports

Strategy rule settings:

- strategy settings should be generated from backend strategy config metadata where possible
- Pullback should expose maximum distance from MA20, minimum relative volume, and minimum relative strength
- Breakout should expose maximum distance from 52-week high, minimum relative volume, and minimum relative strength
- Bounce should expose anchor MA (`MA20` or `MA50`), maximum distance from anchor, prior-day-high confirmation, optional relative-volume threshold, and minimum relative strength
- changes apply to future scans, backtests, and recommendations
- existing planned trades should keep the original strategy settings used when they were created

### Display Rules

- Daily Scanner table should not show reward/risk.
- Candidate Detail should show reward/risk with an explanation of the calculation.
- If the user changes the default reward/risk multiple, future recommendations should use the new default.
- Existing planned trades should not silently change when recommendation defaults are edited.

## Use Case 12: Configure App Settings

### Purpose

Allow the user to manage cache behavior, market data providers, and local display preferences without editing config files.

### Entry Points

Settings navigation:

> Cache

> Market Data

> Appearance

### Cache Settings Flow

1. User opens Settings / Cache.
2. UI shows cache health:
   - cached ticker count
   - latest cached bar date
   - days since last refresh
   - cache coverage
   - provider calls avoided today
3. User adjusts refresh policy:
   - history window
   - stale-after threshold
   - batch size
   - delay between provider batches
4. User can run Warm Cache, Cache-Only Preview, Refresh Stale Data, or Prune Old Data.
5. UI warns clearly if the last refresh stopped because of a provider rate limit.

### Market Data Settings Flow

1. User opens Settings / Market Data.
2. UI shows active provider and fallback configuration.
3. User can select:
   - primary provider
   - backup provider
   - cache-first/provider-only mode
   - provider request safety limits
4. User can test provider connectivity with a sample symbol.
5. UI shows DNS, HTTPS, provider response, latest bar, latency, and last error.

### Appearance Settings Flow

1. User opens Settings / Appearance.
2. UI shows theme, table, chart, and accessibility preferences.
3. User changes density, page size, chart defaults, or win/loss colors.
4. Preview updates immediately.
5. Settings are saved locally.

### Display Rules

- Cache settings should distinguish clearly between provider calls and cache-only reads.
- Market Data settings should explain that Yahoo Finance is unofficial and has no guaranteed rate limit.
- Appearance settings should apply locally and should not affect scanner calculations.

### Security Requirements

- prefer read-only credentials where broker supports them
- do not place, modify, or cancel trades from this app in version one
- keep credentials local
- store broker API secrets in OS keychain/keyring where practical
- use encrypted local config only as a fallback
- do not store Fidelity website credentials for file import mode
- do not collect brokerage website passwords in the app
- clearly display connected account and paper/live status
- require confirmation before applying matched broker fills to the journal

### Broker Sync Output

Show:

- matched planned trades
- unmatched broker executions
- unmatched planned journal trades
- open broker positions
- closed broker trades, if broker supports them
- sync warnings

### Error States

- invalid credentials
- expired token
- insufficient permissions
- broker unavailable
- paper/live account mismatch
- no executions found for selected date range

## Initial Mockup List

Create screenshot-style mockups for:

1. Dashboard
2. Cache Warmup / Onboarding
3. Daily Scanner Results
4. Candidate Detail
5. Backtest Results
6. Portfolio Simulation
7. Trade Journal
8. Broker Connections
9. Reports

## Visual Direction

The UI should feel like an investor workstation:

- dense but readable
- restrained color palette
- clear status indicators
- tables optimized for scanning
- charts used where they clarify decisions
- no marketing-style hero layout
- no decorative cards inside cards

## Resolved Decisions

- Dashboard should emphasize daily scanner readiness while still showing cache health prominently.
- Backtest and Portfolio should be separate pages. Backtest measures strategy history; Portfolio Simulation applies account cash, position sizing, stops, slippage, commissions, and portfolio constraints.
- Candidate Detail should include a full stock chart in version one because draggable entry, stop, and target levels are part of the manual trade checklist workflow.
- Generated HTML reports should be linked from the UI as local files in version one. The Reports page should index, open, download, and reveal generated reports without rerunning analysis.
- Cache warmup should be a launched workflow from Dashboard or Settings / Cache, not a permanent primary navigation item.
- Broker credentials should be stored locally and should prefer OS keychain/keyring storage where practical.
- App login should remain omitted while the application is local-only.
- Broker sync should be read-only in version one. The app should not place, modify, or cancel trades.
