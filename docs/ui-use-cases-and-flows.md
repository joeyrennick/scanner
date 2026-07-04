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
- Cache Setup
- Daily Scanner
- Candidates
- Backtest
- Portfolio
- Journal
- Reports
- Settings

The app should open to Dashboard.

## Use Case 1: First-Time Setup / Cache Warmup

### Purpose

Help a first-time user build enough local cache to scan without immediately hitting Yahoo rate limits.

### Entry Point

Dashboard warning card:

> Cache is mostly empty. Start setup to warm market data safely.

Primary button:

> Start Cache Setup

### Flow

1. User opens Cache Setup.
2. UI shows cache overview:
   - cached tickers
   - cached bars
   - latest cached bar
   - last successful refresh
   - days since refresh
3. User selects:
   - universe
   - optional min/max price
   - batch size
   - max batches
   - delay between batches
4. UI estimates:
   - symbols to inspect
   - maximum provider batches
   - minimum estimated wait from configured delay
5. User clicks Start.
6. UI shows progress:
   - current batch
   - total planned batches
   - symbols checked
   - symbols kept
   - symbols skipped
   - provider batches attempted
   - ETA
7. If rate limit happens:
   - UI stops provider calls
   - shows clear warning
   - suggests waiting and resuming later
8. On success:
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

Generate today's watchlist for pullback and breakout strategy candidates.

### Entry Point

Dashboard primary action:

> Run Daily Scan

### Flow

1. User opens Daily Scanner.
2. User selects:
   - universe
   - strategy: pullback, breakout, or both
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
6. UI displays watchlist table.
7. User can:
   - sort by composite score
   - filter by strategy
   - open candidate detail
   - export CSV
   - generate daily HTML report

### Success State

Watchlist table with:

- ticker
- strategy flags
- composite score
- price
- relative strength
- ATR
- relative volume
- moving averages
- entry area
- suggested stop
- suggested exit
- reward/risk
- suggested hold time

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
4. UI shows historical strategy performance for the ticker.
5. User can add candidate to journal as planned trade.

### Screen Content

Header:

- ticker
- current price
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

Charts:

- price chart with moving averages
- ATR/volume view
- historical backtest result for ticker

Actions:

- Add To Journal
- Export Candidate
- Open Report

## Use Case 4: Historical Backtest

### Purpose

Evaluate pullback/breakout strategy behavior over a ticker, watchlist, or universe.

### Flow

1. User opens Backtest.
2. User selects source:
   - ticker
   - universe
   - watchlist CSV
3. User selects:
   - strategy
   - hold days
   - history period
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

Tables/charts:

- trades table
- top tickers by return
- top tickers by win rate
- monthly results
- weekday results
- return distribution

Actions:

- Export Trade CSV
- Generate HTML Report
- Simulate Portfolio

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
4. Planned trade appears in Journal with status `Planned`.
5. After the user places an order, they update the planned trade with actual entry fill details.
6. Trade status changes to `Open`.
7. After the user exits, they update actual exit fill details.
8. Trade status changes to `Closed`.
9. UI calculates realized results and compares actual execution to the original recommendation.

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
- notes

Closed trades:

- exit date
- exit price
- return percent
- result
- recommendation vs actual entry difference
- recommendation vs actual exit difference

Actions:

- Add recommended trade from candidate detail
- Edit planned trade
- Record actual entry fill
- Record actual exit fill
- Cancel planned trade
- Export journal

Summary:

- planned trades
- open risk
- realized return
- win rate
- average win/loss

### Broker Sync

If the user places paper or real trades through TradingView, the app should not depend on a TradingView user API for actual fills. TradingView's broker API is designed for broker partners, not individual users retrieving their own TradingView paper-trading data.

The app should instead support broker connectors that can import actual orders, positions, executions, and closed trades from the broker account used inside TradingView.

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
2. UI lists reports from output folders.
3. User filters by type/date.
4. User opens report or downloads file.

### Report Types

- daily scanner report
- trade analysis report
- portfolio report
- journal report

## Use Case 8: Broker Connection Setup

### Purpose

Allow users to connect a broker account so the app can sync actual fills, positions, and closed trades into the journal.

This is separate from app login. For a local-only app, version one does not need user accounts or app authentication. Broker authentication is still required for broker sync.

### Entry Point

Settings navigation:

> Broker Connections

Journal action:

> Sync Broker Trades

If no broker is connected, the Journal should route the user to Broker Connections.

### Flow

1. User opens Settings / Broker Connections.
2. User selects broker.
3. UI shows required auth method:
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

### Security Requirements

- prefer read-only credentials where broker supports them
- do not place, modify, or cancel trades from this app in version one
- keep credentials local
- consider OS keychain/keyring storage
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
2. Cache Setup
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

## Open Questions

- Should Dashboard emphasize daily scanner status or cache status first?
- Should Backtest and Portfolio be separate pages or one analysis workflow?
- Should Candidate Detail include a full chart in version one?
- Should first version support generated HTML reports inside the UI, or link to files?
- Should cache warmup be its own page or a modal launched from Dashboard?
- Which broker connector should be implemented first?
- Should broker credentials use OS keychain/keyring storage in version one?
- Should app login remain omitted while the app is local-only?
