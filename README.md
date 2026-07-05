# Swing Scanner

Local-first swing trading scanner, backtester, portfolio simulator, and trade
journal tooling.

## Local API Backend

The first FastAPI service layer is available for the future React UI.

Start the development backend:

```bash
PYTHONPATH=src venv/bin/uvicorn scanner.api.app:app --reload
```

Then open:

```text
http://127.0.0.1:8000/api/health
```

Initial API endpoints:

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
- `GET /api/reports/{report_id}/download`
