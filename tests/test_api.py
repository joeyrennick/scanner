from datetime import date
from dataclasses import replace
from pathlib import Path
import time

import pandas as pd
from fastapi.testclient import TestClient

from scanner.api.app import app
from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.trade import Trade
from scanner.services.cache_warmup import CacheWarmupResult, CacheWarmupTickerStatus
from scanner.services.scan_service import ScanResult


client = TestClient(app)


def wait_for_job(job_id: str):
    for _attempt in range(50):
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()

        if payload["status"] in {"complete", "failed", "stopped"}:
            return payload

        time.sleep(0.02)

    raise AssertionError(f"job did not finish: {job_id}")


def test_health_endpoint():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_endpoint_includes_cache_retention():
    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["market_data_cache_retention_years"] == 5


def test_strategies_endpoint_returns_metadata():
    response = client.get("/api/strategies")

    assert response.status_code == 200
    strategies = {strategy["key"]: strategy for strategy in response.json()}
    assert "pullback" in strategies
    assert strategies["pullback"]["display_name"] == "Pullback Strategy"
    assert "max_distance_from_ma20" in strategies["pullback"]["default_config"]


def test_cache_overview_endpoint(tmp_path, monkeypatch):
    from scanner.api import app as api_app

    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
    )
    response = client.get("/api/cache/overview")

    assert response.status_code == 200
    assert response.json()["cached_tickers"] == 0


def test_cache_warmup_job_lifecycle(monkeypatch):
    from scanner.api import app as api_app

    class FakeCacheWarmupService:
        def __init__(self, context=None, logger=None, progress_callback=None):
            self.progress_callback = progress_callback

        def run(self, config):
            if self.progress_callback:
                self.progress_callback(
                    current_step="Cache-only preview complete",
                    symbols_total=1,
                    symbols_checked=1,
                    symbols_kept=1,
                    symbols_skipped=0,
                    provider_batches_attempted=0,
                    provider_symbols_attempted=0,
                    message="Cache-only preview complete",
                )
            return CacheWarmupResult(
                statuses=[
                    CacheWarmupTickerStatus(
                        ticker="AAPL",
                        status="cached",
                        rows=10,
                    )
                ],
                period=config.period,
                batch_size=config.batch_size,
                provider_batches_allowed=config.max_provider_batches,
                provider_batches_planned=0,
                provider_batches_attempted=0,
                provider_symbols_planned=0,
                provider_symbols_attempted=0,
                provider_calls_before=0,
                provider_calls_after=0,
                stopped_for_rate_limit=False,
                cache_only_preview=config.cache_only_preview,
                elapsed_seconds=0.01,
            )

    monkeypatch.setattr(api_app, "CacheWarmupService", FakeCacheWarmupService)

    response = client.post(
        "/api/cache/warmup",
        json={
            "tickers": ["AAPL"],
            "history_period": "5d",
            "cache_only_preview": True,
        },
    )

    assert response.status_code == 200
    payload = wait_for_job(response.json()["job_id"])
    assert payload["status"] == "complete"
    assert payload["progress"]["current_step"] == "Cache-only preview complete"
    assert payload["progress"]["elapsed_seconds"] is not None
    assert payload["symbols_checked"] == 1
    assert payload["result"]["available"] == 1
    assert payload["result"]["provider_calls_attempted"] == 0


def test_scan_job_lifecycle(monkeypatch, tmp_path):
    from scanner.api import app as api_app

    class FakeScanService:
        def __init__(self, context=None, logger=None, progress_callback=None):
            self.progress_callback = progress_callback

        def run(self, config):
            if self.progress_callback:
                self.progress_callback(
                    current_step="Scan complete",
                    symbols_total=1,
                    symbols_checked=1,
                    symbols_kept=1,
                    symbols_skipped=0,
                    output_paths={"watchlist_csv": str(tmp_path / "watchlist.csv")},
                    message="Scan complete",
                )
            dataframe = pd.DataFrame(
                [
                    {
                        "Ticker": "AAPL",
                        "Composite Score": 88,
                    }
                ]
            )
            return ScanResult(
                tickers=["AAPL"],
                analyses=[],
                trade_candidates=[],
                skipped=[],
                dataframe=dataframe,
                output_file=str(tmp_path / "watchlist.csv"),
                elapsed_seconds=0.01,
                cache_summary="cache ok",
            )

    monkeypatch.setattr(api_app, "ScanService", FakeScanService)

    response = client.post(
        "/api/scans",
        json={
            "universe": "sp500",
            "history_period": "5d",
            "warm_market_data_cache": False,
        },
    )

    assert response.status_code == 200
    payload = wait_for_job(response.json()["job_id"])
    assert payload["status"] == "complete"
    assert payload["progress"]["current_step"] == "Scan complete"
    assert payload["output_paths"]["watchlist_csv"] == str(tmp_path / "watchlist.csv")
    assert payload["result"]["rows"] == [{"Ticker": "AAPL", "Composite Score": 88}]


def test_backtest_job_lifecycle(monkeypatch):
    from scanner.api import app as api_app

    class FakeBacktestService:
        def __init__(self, config=None, progress_callback=None):
            self.progress_callback = progress_callback

        def run(self, ticker, universe, strategy):
            if self.progress_callback:
                self.progress_callback(
                    current_step="Backtest complete",
                    symbols_total=1,
                    symbols_checked=1,
                    symbols_kept=1,
                    symbols_skipped=0,
                    message="Backtest complete",
                )
            return BacktestResult(
                ticker=ticker,
                strategy_name=strategy.name,
                trades=[
                    Trade(
                        ticker=ticker,
                        strategy_name=strategy.name,
                        entry_date=date(2026, 1, 1),
                        exit_date=date(2026, 1, 6),
                        entry_price=100,
                        exit_price=110,
                    )
                ],
            )

    monkeypatch.setattr(api_app, "BacktestService", FakeBacktestService)

    response = client.post(
        "/api/backtests",
        json={
            "ticker": "AAPL",
            "strategy": "pullback",
            "history_period": "5d",
            "hold_days": 5,
        },
    )

    assert response.status_code == 200
    payload = wait_for_job(response.json()["job_id"])
    assert payload["status"] == "complete"
    assert payload["progress"]["current_step"] == "Backtest complete"
    assert payload["symbols_checked"] == 1
    assert payload["result"]["statistics"]["total_trades"] == 1
    assert payload["result"]["trades"][0]["Return %"] == 10.0


def test_latest_watchlist_endpoint(tmp_path, monkeypatch):
    from scanner.api import app as api_app

    output_file = tmp_path / "watchlist.csv"
    pd.DataFrame([{"Ticker": "AAPL", "Composite Score": 88}]).to_csv(
        output_file,
        index=False,
    )
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(api_app.settings, output_file=str(output_file)),
    )

    response = client.get("/api/watchlist/latest")

    assert response.status_code == 200
    assert response.json()["rows"] == [{"Ticker": "AAPL", "Composite Score": 88}]


def test_reports_endpoint_lists_output_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_dir = Path("output")
    output_dir.mkdir()
    (output_dir / "daily_scanner_report_2026-07-05.html").write_text(
        "<html></html>"
    )

    response = client.get("/api/reports")

    assert response.status_code == 200
    assert response.json()[0]["type"] == "daily_scanner"
