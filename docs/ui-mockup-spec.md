# UI Mockup Specification

## Goal

Create screenshot-style mockups for the first version of the swing scanner UI.

The mockups should communicate layout, workflow, information hierarchy, and the investor-facing decision process. They are not final implementation assets.

## Visual Direction

Use an investor workstation style:

- dense but readable
- calm, neutral background
- clear data hierarchy
- compact controls
- sortable tables
- restrained color use
- green/red only for meaningful outcome states
- no marketing hero section
- no decorative illustrations
- no nested card layouts

Suggested palette:

- background: near-white or very light gray
- text: dark neutral
- border: subtle gray
- positive: muted green
- negative: muted red
- warning: amber
- info/accent: restrained blue

Use tables, status bars, segmented controls, tabs, and compact metric panels.

## Shared Layout

All screens should use:

- left navigation rail
- top header with page title and current cache status
- main content area
- compact controls above data
- persistent status area for long-running jobs

Navigation items:

- Dashboard
- Daily Scanner
- Candidates
- Backtest
- Portfolio
- Journal
- Reports
- Settings

Cache setup is not shown as a persistent primary navigation item. The cache warmup/onboarding flow is launched from Dashboard or Settings / Cache.

Top cache status example:

```text
Cache: 2,681 tickers | Latest bar: 2026-07-02 | Refreshed today
```

## Mockup 1: Dashboard

### Purpose

Give the user a starting point and show whether the app is ready to scan.

### Layout

Top row:

- Cache readiness panel
- Today's scan status
- Broker connection status
- Journal summary

Main area:

- Primary action panel: Run Daily Scan
- Setup action panel: Warm Cache
- Recent reports list
- Recent journal activity

### Required Data

Cache panel:

- cached tickers: `2,681`
- cached bars: `110,647`
- latest bar: `2026-07-02`
- days since refresh: `0`

Scan panel:

- last scan: `Today 9:42 AM`
- candidates: `18`
- skipped symbols: `42`

Broker panel:

- status: `Not connected`
- action: `Connect Broker`

Journal panel:

- planned trades: `4`
- open trades: `2`
- closed trades: `37`
- win rate: `58%`

### States

- first-time state: cache mostly empty
- ready state: cache refreshed today
- rate-limited state: warning with resume action

## Mockup 2: Cache Warmup / First-Time Onboarding

### Purpose

Help a first-time user build local cache safely.

### Layout

Header:

- title: Cache Warmup
- status: read-only provider summary

Controls:

- universe selector
- min/max price inputs
- batch size input
- max batches input
- batch delay input
- mode selector: `Warm Cache` or `Cache-Only Preview`
- small info icon next to mode selector
- primary action button that changes by mode:
  - `Start Warmup`
  - `Run Preview`

Progress section:

- progress bar
- current batch / total batches
- symbols checked
- symbols kept
- symbols skipped
- provider batches attempted
- elapsed time
- ETA

Cache overview table:

- provider
- cached tickers
- cached bars
- earliest bar
- latest bar
- last refresh
- days since refresh

### Required Data

Example progress:

```text
Batch 4 of 10
Symbols checked: 200 / 500
Kept: 83
Skipped: 117
Elapsed: 2m 14s
ETA: 3m 22s
```

### States

- not started
- running
- complete
- stopped by rate limit
- cache-only mode

Mode info tooltip text:

```text
Warm Cache fetches missing recent price data in controlled batches and stores it locally.
Cache-Only Preview makes no provider calls. It only checks existing cached data so you can see how much of the universe can be scanned safely right now.
```

Rate-limit warning text:

```text
Yahoo rate limit detected. Cached data was preserved. Wait and resume later.
```

## Mockup 3: Daily Scanner Results

### Purpose

Show today's trade candidates.

### Layout

Controls row:

- universe selector
- strategy segmented control: All / Pullback / Breakout
- min/max price
- history period
- cache-only toggle
- Run Scan button

Summary row:

- analyzed symbols
- candidates
- cache hits
- provider calls
- elapsed time

Results table:

- row selection checkboxes
- ticker
- strategy
- score
- current price
- price as of
- price source
- relative strength
- relative volume
- ATR
- entry area
- stop
- target/exit
- hold time
- action

Do not include a reward/risk column on the Daily Scanner Results table. Reward/risk should be shown in Candidate Detail and controlled by Settings.

### Required Data

Example rows:

- `AAPL`, Pullback, score `82`, current price `211.43`, source `Yahoo`, as of `Today 10:42 AM`
- `NVDA`, Breakout, score `88`, current price `147.20`, source `Yahoo`, as of `Today 10:42 AM`
- `MSFT`, Pullback, score `79`, current price `494.10`, source `Cached Close`, as of `2026-07-02`

Price behavior:

- Show a small status indicator when final candidate prices were refreshed from the provider.
- Show a warning state when any candidate uses `Cached Close` because fresh refresh failed.
- The `Current Price` column header should include a small info icon.
- Tooltip copy: `Scanner indicators can use cached history, but displayed candidate prices are refreshed after the final list is built. If refresh fails, the latest cached close is shown and labeled.`
- Current Price info tooltip copy: `Current Price comes from Yahoo/latest provider data and may be delayed or stale. Confirm the live price in your trading platform, such as TradingView or thinkorswim, before placing a trade.`

Action buttons:

- Open
- Add To Journal

Page-level report/export actions:

- Export CSV, with support for selected rows, filtered rows, or all scan candidates
- Backtest Selected / Backtest Candidates
- Generate Daily Report

These buttons should be visible on the Daily Scanner Results page after a scan completes. `Add To Journal` is a row action and should create a planned trade in `Journal > Planned Trades`; `Generate Daily Report` is a page-level action that creates the dated daily scanner HTML report.

CSV export behavior:

- table should include row selection checkboxes
- show selected count when any rows are selected
- `Export CSV` should make it clear whether it exports selected, filtered, or all candidates
- default export behavior should be filtered candidates when no rows are selected
- provide an explicit option to export all scan candidates
- exported CSV should use adjusted entry/stop/target values when present

Backtest handoff behavior:

- show `Backtest Selected` when one or more rows are selected
- if no rows are selected, show `Backtest Filtered`
- clicking this action should open Backtest Results with source prefilled from the selected or filtered scanner candidates
- do not require CSV export before backtesting scanner candidates

### States

- loading
- populated
- no candidates
- partial cache / provider limit reached

## Mockup 4: Candidate Detail

### Purpose

Help the investor decide whether to take a recommended trade.

### Layout

Header:

- ticker
- company name placeholder
- current price
- price as of
- price source
- strategy signal
- score

Left section:

- price chart placeholder
- moving average overlays
- volume strip
- resizable chart container with visible resize affordance
- draggable horizontal overlays for entry zone, stop, and target/exit
- visible drag handles on each trade level label

Right section:

- trade checklist
- recommendation summary
- risk controls
- edited-state indicators when chart levels have been moved
- Reset to Suggested button in the top-right of the Manual Trade Checklist header

Bottom section:

- historical backtest mini-summary
- similar historical trades table

### Required Fields

Recommendation:

- entry area
- suggested stop
- suggested target/exit
- suggested hold time
- risk per share
- reward/risk
- position size estimate

Reward/risk note:

- show configured default reward/risk multiple
- explain how target/exit was calculated from entry, stop, and configured multiple
- include a link or small action to update the default in Settings

Interactive trade level behavior:

- Entry Zone, Stop, and Target/Exit boxes on the chart should be visually draggable.
- Use small grab handles or drag icons so the behavior is discoverable.
- When a user drags a level, update the matching checklist value in real time.
- Show an `Edited` badge near adjusted values.
- Keep original suggested values available for comparison.
- Include `Reset to Suggested` in the checklist header.
- `Reset to Suggested` should be inside the Manual Trade Checklist box, aligned in the top-right of that panel header, not grouped with the lower action buttons.
- Adjusted values should flow back to Daily Scanner Results, exports, daily HTML report, and planned journal trades.

Resizable chart behavior:

- The chart should show a visible resize handle or expand control.
- Resizing should preserve the chart overlays and drag handles.
- The Manual Trade Checklist should remain readable and accessible when the chart is enlarged.
- If using expanded chart mode in a mockup, include a clear return/collapse control.

Actions:

- Add To Journal
- Open Backtest
- Export Candidate

### Important State

When user clicks Add To Journal from Daily Scanner or Candidate Detail, the trade is saved as `Planned`, not `Open`, and appears in `Journal > Planned Trades`.

## Mockup 5: Trade Journal

### Purpose

Show planned trades, open trades, and historical results.

### Layout

Tabs:

- Planned Trades
- Open Trades
- Historical Ledger
- Analytics

`Open Trades` should appear directly to the right of `Planned Trades`. Do not include a separate `Closed` tab because closed trades are historical data and belong in `Historical Ledger`.

Summary row:

- planned trades
- open risk
- closed trades
- win rate
- profit factor
- expectancy
- average winner
- average loser

Planned Trades tab:

- table with planned trades created from Daily Scanner or Candidate Detail
- user-editable planning view
- default sort: most recent created date first
- each row should provide actions to Edit, Open Candidate Detail, and Delete/Cancel
- users can edit planned entry, stop, target, hold time, notes, tags, and planned position size
- Delete/Cancel should remove the row from active Planned Trades after confirmation
- Daily Scanner `Add To Journal` should route new planned recommendations into this tab

Historical ledger:

- read-only table with broker-synced closed trades and matched executions
- default sort: most recent trade first
- closed ledger sort key: exit date descending
- open trade sort key: entry date descending
- planned trade sort key: created date descending
- winning rows shaded green
- losing rows shaded red
- breakeven rows neutral
- column-header filter dropdowns populated from existing values
- visible filter chips above the table
- stats update based on active filters
- no inline editing of actual broker-synced execution fields

Open Trades tab:

- read-only table with broker-synced active open trades
- default sort: most recent entry date first
- show current price, unrealized P/L, days held, active stop, target, and planned-vs-actual entry
- row status should highlight trades near stop or target
- actions should include Open Candidate Detail and Sync Broker Trades
- summary cards should update to open-trade metrics such as open risk, unrealized P/L, average days held, and trades near stop
- no inline editing of actual broker-synced execution fields

### Required Columns

Historical ledger:

- ticker
- strategy
- planned entry
- actual entry
- planned exit
- actual exit
- entry date
- exit date
- days held
- shares
- return %
- dollar P/L
- fees
- notes

### Required Filters

The user should filter by clicking column headers, not by manually typing values.

Show header dropdown affordances on:

- ticker
- strategy
- result
- entry month
- exit month
- broker account
- source

Filter dropdown example:

```text
Ticker
[x] AAPL
[x] NVDA
[ ] MSFT
[ ] SMCI
Apply
```

Show active filter chips:

```text
Ticker: AAPL, NVDA   Strategy: Pullback   Result: Win
```

Summary cards and charts should visibly reflect filtered rows.

### Required Pagination

Show pagination controls below the historical ledger.

Requirements:

- default page size: `50`
- page size selector: `25 / 50 / 100 / All`
- previous and next buttons
- visible range text, for example `Showing 1-50 of 312 filtered trades`
- pagination applies after active sorting and filters
- summary cards and charts are based on the full filtered data set, not the current page
- export action exports the full filtered data set

### Required Actions

- Record Actual Entry
- Record Actual Exit
- Cancel Planned Trade
- Sync Broker Trades
- Export Journal

### Analytics

- win rate
- loss rate
- win/loss count ratio
- average winner
- average loser
- profit factor
- expectancy
- best trade
- worst trade
- longest winning streak
- longest losing streak
- monthly realized P/L

## Mockup 6: Broker Connections

### Purpose

Let the user connect a broker account for read-only trade sync.

### Layout

Connection panel:

- broker selector
- auth method indicator
- connect/test button
- disconnect button

Connected account panel:

- broker
- account label/id
- paper/live mode
- permission scope
- last sync time

Sync preview:

- matched planned trades
- unmatched executions
- unmatched planned trades
- apply selected matches button

### Required States

- not connected
- connecting
- connected
- invalid credentials
- expired token
- insufficient permissions
- paper/live mismatch

Security banner:

```text
Read-only sync only. This app will not place, modify, or cancel trades.
```

## Mockup 7: Backtest Results

### Purpose

Show historical strategy performance.

### Layout

Controls:

- source selector: ticker / universe / watchlist
- strategy
- hold days
- history period
- price range
- Run Backtest button

Source options should include selected or filtered Daily Scanner candidates. Example selected source label: `Selected Daily Scanner Candidates (3)`. The screen should make clear that this direct source does not require CSV export first.

Summary cards:

- trades
- win rate
- average return
- expectancy
- best trade
- worst trade

Charts:

- return distribution
- monthly performance

Tables:

- top tickers by average return
- top tickers by win rate

Do not show a Recent Trades table on Backtest Results. This page should focus on aggregate historical backtest metrics, charts, and ticker rankings. Trade-level detail belongs in the exported trade CSV, generated HTML report, or a separate drill-down view.

Actions:

- Export Trade CSV
- Generate HTML Report
- Simulate Portfolio

## Mockup 8: Portfolio Simulation

### Purpose

Show what strategy trades look like with portfolio rules applied.

### Layout

Controls:

- trade CSV/source selector
- starting cash
- max open positions
- position sizing
- commission
- slippage
- stop-loss
- trailing stop

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

- Export Portfolio Report
- Open Detailed Report

The report/export actions should be visible after simulation results are available.

## Mockup 9: Reports

### Purpose

Let the user reopen previous reports and exports.

### Layout

Filters:

- report type
- date range
- strategy
- ticker

Report table:

- report name
- type
- created date
- source
- file path
- actions

Actions:

- Open
- Download
- Reveal File

## Mockup 10: Settings / Recommendation Defaults

### Purpose

Let the user control the default values used when the app generates suggested entries, stops, targets/exits, hold periods, journal planned trades, exports, and reports.

### Layout

Settings sidebar:

- Recommendation Defaults
- Broker Connections
- Market Data
- Cache
- Appearance

Primary settings:

- default reward/risk multiple, initially `2.0`
- default suggested hold period, initially `5` trading days
- default stop method, initially `2 * ATR`
- ATR period, initially `14`
- entry zone method, initially `Strategy default`
- default risk per trade, initially `1%`

Chart and checklist settings:

- default chart range
- remember resized candidate chart
- show original suggested levels
- show edited-value badges

Export and report defaults:

- default CSV export scope
- include adjusted checklist values in exports and reports
- daily report output folder

Preview panel:

- example ticker
- entry area
- stop
- target/exit
- hold period
- reward/risk calculation

Actions:

- Save Settings
- Reset Defaults
- Discard Changes

Display rules:

- Show a note that settings apply to future recommendations.
- Existing planned trades should not silently change when defaults are edited.
- Include an info tooltip for reward/risk explaining that the target is calculated from entry, stop, and the configured reward multiple.

## Mockup 11: Settings / Cache

### Purpose

Let the user control cache behavior after first-time setup, understand cache freshness, and safely refresh or prune stored market data.

### Layout

Settings sidebar:

- Recommendation Defaults
- Broker Connections
- Market Data
- Cache
- Appearance

Primary panels:

- Cache Health
- Refresh Policy
- Cache Storage
- Maintenance Actions

Cache Health should show:

- cached ticker count
- latest cached bar date
- oldest cached bar date
- cache coverage percent
- days since last refresh
- provider calls avoided today

Refresh Policy controls:

- default history window, initially `6 months`
- cache stale-after threshold, initially `1 trading day`
- refresh only missing bars toggle
- skip provider calls when cache is fresh toggle
- stop on rate limit toggle
- batch size
- delay between provider batches

Cache Storage controls:

- database path
- estimated cache size
- archive older than selector
- retain adjusted OHLCV toggle

Maintenance actions:

- Warm Cache
- Cache-Only Preview
- Refresh Stale Data
- Prune Old Data
- Open Cache Folder

Display rules:

- Show clear wording that Cache-Only Preview makes no provider calls.
- Show estimated wait time before a refresh starts.
- Show warning state if the last refresh ended because of a rate limit.

## Mockup 12: Settings / Market Data

### Purpose

Let the user select market data providers, configure fallback behavior, and manage safe request throttling without touching strategy code.

### Layout

Settings sidebar:

- Recommendation Defaults
- Broker Connections
- Market Data
- Cache
- Appearance

Provider panels:

- Active Provider
- Provider Fallbacks
- Request Safety
- Connection Test

Active Provider controls:

- primary provider dropdown, initially `Yahoo Finance`
- backup provider dropdown, initially `Alpha Vantage`
- provider mode segmented control: `Default`, `Cache First`, `Provider Only`
- API key status for providers that need keys

Provider Fallback controls:

- fallback to cache on provider error toggle
- fallback to backup provider on rate limit toggle
- label cached prices clearly toggle
- fresh price refresh for final scanner candidates toggle

Request Safety controls:

- max workers, initially `40`
- batch size
- delay between batches
- daily request budget
- hourly request budget
- stop immediately on rate-limit toggle

Connection Test panel:

- test symbol input
- Test Provider button
- status table with DNS, HTTPS, provider response, latest bar, latency, and last error

Display rules:

- Present Yahoo Finance as an unofficial provider with no guaranteed rate limit.
- Show a warning when provider-only mode can consume request budget quickly.
- Explain that strategy code reads through the market data layer, not directly from provider APIs.

## Mockup 13: Settings / Appearance

### Purpose

Let the user control local visual preferences that make dense scanner, backtest, and journal views easier to read.

### Layout

Settings sidebar:

- Recommendation Defaults
- Broker Connections
- Market Data
- Cache
- Appearance

Appearance panels:

- Theme
- Tables
- Charts
- Accessibility

Theme controls:

- theme segmented control: `System`, `Light`, `Dark`
- accent color selector
- density selector: `Comfortable`, `Compact`

Table controls:

- default page size, initially `50`
- sticky table headers toggle
- show row striping toggle
- default sort for journal, initially `Most recent first`
- negative values color, initially `Red`
- positive values color, initially `Green`

Chart controls:

- default chart height
- remember resized charts toggle
- show volume by default toggle
- show moving averages by default toggle

Accessibility controls:

- larger table text toggle
- reduce motion toggle
- high contrast mode toggle
- color-blind friendly win/loss colors toggle

Preview panel:

- compact scanner table preview
- small chart preview
- win/loss journal row preview

Display rules:

- Appearance settings should apply locally.
- Changes should update the preview immediately.
- Theme should default to system preference.

## Image Generation Order

Generate mockups in this order:

1. Dashboard
2. Cache Warmup / Onboarding
3. Daily Scanner Results
4. Candidate Detail
5. Trade Journal
6. Broker Connections
7. Backtest Results
8. Portfolio Simulation
9. Reports
10. Settings / Recommendation Defaults
11. Settings / Cache
12. Settings / Market Data
13. Settings / Appearance

## Acceptance Criteria

Each mockup should:

- look like a real application screen
- use realistic data
- show page-specific controls
- show investor-relevant outputs
- avoid marketing layout
- show clear status/error/progress states where relevant
- be readable at desktop resolution
