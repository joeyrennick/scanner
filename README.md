# Swing Scanner

Local-first swing trading scanner, backtester, portfolio simulator, and trade
journal tooling.

## Local API Backend

The first FastAPI service layer is available for the future React UI.

Start the development backend:

```bash
PYTHONPATH=src venv/bin/uvicorn scanner.api.app:app --reload
```

To use Massive/Polygon without local environment variables:

1. Start the backend and UI.
2. Open Settings.
3. Paste the Massive/Polygon API key under Market Data.
4. Save the key.

The key is encrypted in the local SQLite database. The local encryption key is
generated automatically next to the SQLite database and does not need to be
managed manually.

Environment variables are still supported as an override:

```bash
export MASSIVE_API_KEY="your_api_key_here"
export MARKET_DATA_PROVIDER=massive
PYTHONPATH=src venv/bin/uvicorn scanner.api.app:app --reload
```

The app also accepts `POLYGON_API_KEY` as an alias for `MASSIVE_API_KEY`.
Massive is the default market-data provider. Set `MARKET_DATA_PROVIDER=yahoo`
to use Yahoo Finance instead.

Then open:

```text
http://127.0.0.1:8000/api/health
```

Initial API endpoints:

- `GET /api/health`
- `GET /api/settings`
- `GET /api/market-data/massive/credential`
- `PUT /api/market-data/massive/credential`
- `DELETE /api/market-data/massive/credential`
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
- `GET /api/reports/{report_id}/download`
- `POST /api/fundamentals/{ticker}`
- `POST /api/reports/fundamental-analysis`

## Fundamental Analysis

Open `http://127.0.0.1:5173/fundamentals` to analyze a ticker or cycle through
the candidates from a saved scanner run. The page restores the selected run,
ticker, strategy, risk and validation filters, tab, scroll position, and
per-ticker valuation assumptions after refresh or navigation.

Fundamental statements come from the SEC EDGAR Company Facts API, which does not
require an API key. Ratios are derived from those filings and the latest price
from the configured market-data provider. Set `SEC_USER_AGENT` to a declared
identity such as `Your Company admin@example.com` when deploying automated SEC
access. Generated PDF reports and their immutable JSON snapshots are written under
`output/fundamental_reports` and appear on the Reports page.

## Undervalued Strategy

On the Daily Scanner page, select `Undervalued` with the desired universe and
run the scan. This is an explicit SEC fundamentals scan rather than a technical
entry rule. It ignores the Min Price, Max Price, moving-average, volume, and
relative-strength settings. A stock qualifies when its base-case DCF fair value
is at least 15% above its current price using a 10% discount rate, 2.5% terminal
growth, and a five-year projection. Results are ranked by margin of safety.
Preferred stock, preference shares, and depositary shares are excluded before
valuation because issuer-level common-stock DCF inputs do not map correctly to
those securities.
Each result also includes the Fundamentals risk score and its `low`, `moderate`,
or `high` classification, calculated from leverage, free-cash-flow consistency,
annualized volatility, and five-year maximum drawdown. These classifications can
be filtered on the Fundamentals page. Runs created before risk classification was
added appear as `Risk not calculated`; use `Calculate Risk & Validation` on the
Fundamentals page to enrich that saved run in place, or run the Undervalued scan
again. `Undervalued` is a valuation result and does not imply a Low risk level.

The separate automated validation status is `Validated`, `Needs review`, or
`Rejected`. It checks filing coverage and recency, positive free cash flow and
diluted shares, DCF model suitability, business quality, completed risk,
risk-adjusted margin of safety, independent earnings or cash-flow yield support,
and bear-case resilience. Extreme DCF margins above 200% require review. A
`Validated` result is an automated research-screen result, not final investment
approval: the latest 10-K, subsequent 10-Qs, and material 8-Ks still require
human review.

The first `ALL` valuation scan can take substantially longer than a technical
scan because each company needs current price data and an SEC filing. Normalized
SEC statements are cached locally for 24 hours, and SEC requests are limited to
eight per second. Fundamental scans use eight worker threads by default; set
`FUNDAMENTAL_SCAN_WORKERS` to override that value. `All Technical` deliberately
remains the fast technical scan; select `Undervalued` explicitly when this
fundamentals screen is desired.
