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
