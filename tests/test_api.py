from datetime import date
from dataclasses import replace
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

from scanner.api.app import app
from scanner.backtesting.backtest_result import BacktestResult
from scanner.backtesting.trade import Trade
from scanner.services.cache_warmup import CacheWarmupResult, CacheWarmupTickerStatus
from scanner.services.scan_service import ScanResult
from scanner.services.undervalued_scan import UndervaluedScanResult


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


def test_massive_credential_endpoints_store_encrypted_secret(tmp_path, monkeypatch):
    from scanner.api import app as api_app

    db_path = tmp_path / "market_data.sqlite"
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(api_app.settings, market_data_cache_path=str(db_path)),
    )

    initial = client.get("/api/market-data/massive/credential")
    assert initial.status_code == 200
    assert initial.json()["configured"] is False

    saved = client.put(
        "/api/market-data/massive/credential",
        json={"api_key": "secret-value"},
    )
    assert saved.status_code == 200
    assert saved.json()["configured"] is True
    assert saved.json()["source"] == "encrypted_sqlite"

    with sqlite3.connect(db_path) as connection:
        encrypted_value = connection.execute(
            "SELECT encrypted_value FROM secrets WHERE name = ?",
            ("massive_api_key",),
        ).fetchone()[0]

    assert "secret-value" not in encrypted_value

    deleted = client.delete("/api/market-data/massive/credential")
    assert deleted.status_code == 200
    assert deleted.json()["configured"] is False


def test_market_data_history_endpoint_returns_daily_bars(monkeypatch):
    from scanner.api import app as api_app

    class FakeProvider:
        def download_price_data(self, ticker, period="1y"):
            assert ticker == "AAPL"
            assert period == "2y"
            return pd.DataFrame(
                [
                    {
                        "Open": 100.0,
                        "High": 102.0,
                        "Low": 99.0,
                        "Close": 101.0,
                        "Volume": 123456,
                    }
                ],
                index=pd.to_datetime(["2026-01-02"]),
            )

    monkeypatch.setattr(
        api_app,
        "create_market_data_provider",
        lambda **_kwargs: FakeProvider(),
    )

    response = client.get("/api/market-data/history/AAPL?provider=massive&period=1y")

    assert response.status_code == 200
    assert response.json() == {
        "ticker": "AAPL",
        "provider": "massive",
        "period": "1y",
        "interval": "1d",
        "rows": [
            {
                "date": "2026-01-02",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 123456.0,
                "sma_50": None,
                "sma_200": None,
            }
        ],
    }


def test_market_data_history_endpoint_returns_intraday_timestamps(monkeypatch):
    from scanner.api import app as api_app

    factory_calls = []

    class FakeProvider:
        def download_price_data(self, ticker, period="1y", interval="1d"):
            assert ticker == "AAPL"
            assert period == "10d"
            assert interval == "5m"
            return pd.DataFrame(
                [{"Open": 100.0, "High": 101.0, "Low": 99.5, "Close": 100.5}],
                index=pd.to_datetime(["2026-08-28T14:35:00+00:00"]),
            )

    def fake_create_provider(**kwargs):
        factory_calls.append(kwargs)
        return FakeProvider()

    monkeypatch.setattr(api_app, "create_market_data_provider", fake_create_provider)

    response = client.get(
        "/api/market-data/history/AAPL?provider=massive&period=1d&interval=5m"
    )

    assert response.status_code == 200
    assert factory_calls[0]["cache_enabled"] is False
    assert response.json()["interval"] == "5m"
    assert response.json()["rows"][0]["date"] == "2026-08-28T14:35:00+00:00"


def test_market_data_history_calculates_50_and_200_period_moving_averages():
    from scanner.api import app as api_app

    history = pd.DataFrame(
        {"Close": list(range(1, 211))},
        index=pd.date_range("2025-01-01", periods=210, freq="D"),
    )

    result = api_app._add_moving_averages(history)

    assert pd.isna(result.iloc[48]["SMA 50"])
    assert result.iloc[49]["SMA 50"] == 25.5
    assert pd.isna(result.iloc[198]["SMA 200"])
    assert result.iloc[199]["SMA 200"] == 100.5


def test_fundamental_analysis_endpoint_returns_service_result(tmp_path, monkeypatch):
    from scanner.api import app as api_app
    from scanner.data.scanner_results import SQLiteScannerResultStore

    db_path = tmp_path / "cache.sqlite"
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(api_app.settings, market_data_cache_path=str(db_path)),
    )
    store = SQLiteScannerResultStore(db_path)
    run_id = store.save_scan_results(
        pd.DataFrame([{"Ticker": "AAPL", "Triggered Strategies": "Undervalued"}]),
        universe="all",
        market_data_provider="massive",
        history_period="5d",
        output_file=str(tmp_path / "watchlist.csv"),
    )

    class FakeService:
        def __init__(self, fundamentals_provider, price_provider):
            pass

        def analyze(self, ticker, assumptions):
            return {
                "schema_version": 3,
                "ticker": ticker,
                "assumptions": assumptions,
                "risk": {"label": "low", "score": 25},
                "validation": {
                    "status": "validated",
                    "label": "Validated candidate",
                    "score": 100,
                    "reasons": [],
                    "model": "dcf",
                },
            }

    monkeypatch.setattr(api_app, "FundamentalAnalysisService", FakeService)

    response = client.post(
        "/api/fundamentals/AAPL",
        json={"assumptions": {"discount_rate": 0.11}, "run_id": run_id},
    )

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"
    assert response.json()["assumptions"]["discount_rate"] == 0.11
    saved_row = store.get_run(run_id).rows[0]
    assert saved_row["Risk Level"] == "low"
    assert saved_row["Risk Score"] == 25
    assert saved_row["Validation Status"] == "validated"
    assert saved_row["Validation Score"] == 100


def test_fundamental_report_endpoint_creates_downloadable_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    analysis = {
        "schema_version": 3,
        "ticker": "AAPL",
        "company": {"name": "Apple Inc."},
        "quality": {"score": 80, "label": "strong", "checks": []},
        "valuation": {"label": "fairly valued", "scenarios": []},
        "risk": {"score": 25, "label": "low", "checks": []},
        "validation": {
            "status": "validated",
            "label": "Validated candidate",
            "score": 100,
            "checks": [],
            "manual_review_items": [],
        },
        "financial_history": [],
        "warnings": [],
    }

    created = client.post(
        "/api/reports/fundamental-analysis",
        json={"ticker": "AAPL", "analysis": analysis, "page_state": {"tab": "risk"}},
    )

    assert created.status_code == 200
    report = created.json()["report"]
    assert report["type"] == "fundamental_analysis"
    assert report["validation_label"] == "Validated candidate"
    downloaded = client.get(f"/api/reports/{report['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content.startswith(b"%PDF")


def test_strategies_endpoint_returns_metadata():
    response = client.get("/api/strategies")

    assert response.status_code == 200
    strategies = {strategy["key"]: strategy for strategy in response.json()}
    assert "pullback" in strategies
    assert "undervalued" in strategies
    assert strategies["pullback"]["display_name"] == "Pullback Strategy"
    assert strategies["undervalued"]["evaluation_mode"] == "fundamental"
    assert strategies["undervalued"]["backtestable"] is False
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


def test_cache_warmup_job_lifecycle(tmp_path, monkeypatch):
    from scanner.api import app as api_app

    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
    )

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

    monkeypatch.chdir(tmp_path)

    class FakeScanService:
        def __init__(
            self,
            context=None,
            logger=None,
            progress_callback=None,
            cancel_checker=None,
        ):
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
                scanner_run_id=1,
            )

    monkeypatch.setattr(api_app, "ScanService", FakeScanService)
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
    )

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
    assert payload["output_paths"]["scan_log"].startswith("output/logs/scanner_run_")
    assert Path(payload["output_paths"]["scan_log"]).exists()
    assert payload["result"]["scanner_run_id"] == 1
    assert payload["result"]["rows"] == [{"Ticker": "AAPL", "Composite Score": 88}]
    assert payload["result"]["log_path"] == payload["output_paths"]["scan_log"]


def test_undervalued_scan_job_uses_fundamental_mode(monkeypatch, tmp_path):
    from scanner.api import app as api_app

    monkeypatch.chdir(tmp_path)
    captured = {}

    class FakeUndervaluedScanService:
        def __init__(
            self,
            context=None,
            logger=None,
            progress_callback=None,
            cancel_checker=None,
        ):
            self.progress_callback = progress_callback

        def run(self, config):
            captured["config"] = config
            self.progress_callback(
                current_step="Valuation and fundamental validation complete",
                symbols_total=2,
                symbols_checked=2,
                symbols_kept=1,
                symbols_skipped=0,
                message="Valuation and fundamental validation complete for 1 candidates",
            )
            return UndervaluedScanResult(
                tickers=["CHEAP", "EXPENSIVE"],
                analyzed_count=2,
                dataframe=pd.DataFrame(
                    [
                        {
                            "Ticker": "CHEAP",
                            "Triggered Strategies": "Undervalued",
                            "Fair Value": 20,
                            "Current Price": 10,
                            "Margin of Safety": 100,
                            "Risk Level": "low",
                            "Risk Complete": True,
                            "Validation Status": "validated",
                            "Validation Policy Version": 2,
                        }
                    ]
                ),
                skipped=[],
                elapsed_seconds=0.01,
                scanner_run_id=7,
                excluded_non_common=[("FCNCN", "Preferred Stock")],
            )

    monkeypatch.setattr(
        api_app,
        "UndervaluedScanService",
        FakeUndervaluedScanService,
    )
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
            output_file=str(tmp_path / "watchlist.csv"),
        ),
    )

    response = client.post(
        "/api/scans",
        json={
            "universe": "all",
            "strategy": "undervalued",
            "min_price": 500,
            "max_price": 600,
            "warm_market_data_cache": True,
        },
    )

    assert response.status_code == 200
    payload = wait_for_job(response.json()["job_id"])
    assert payload["status"] == "complete"
    assert payload["result"]["scanner_run_id"] == 7
    assert payload["result"]["excluded_non_common"] == [["FCNCN", "Preferred Stock"]]
    assert payload["result"]["rows"][0]["Ticker"] == "CHEAP"
    assert payload["result"]["fundamental_validations"] == 1
    assert payload["result"]["validation_status_counts"] == {"validated": 1}
    assert captured["config"].universe == "all"
    assert captured["config"].minimum_margin_of_safety == 0.15
    assert not hasattr(captured["config"], "min_price")


def test_backtest_job_lifecycle(monkeypatch):
    from scanner.api import app as api_app

    class FakeBacktestService:
        def __init__(self, config=None, progress_callback=None):
            self.progress_callback = progress_callback

        def run(self, ticker, universe, strategy, tickers=None, result_ticker=None):
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
                ticker=result_ticker or ticker,
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


def test_backtest_job_accepts_ticker_list(monkeypatch):
    from scanner.api import app as api_app

    calls = []

    class FakeBacktestService:
        def __init__(self, config=None, progress_callback=None):
            self.progress_callback = progress_callback

        def run(self, ticker, universe, strategy, tickers=None, result_ticker=None):
            calls.append(
                {
                    "ticker": ticker,
                    "universe": universe,
                    "tickers": tickers,
                    "result_ticker": result_ticker,
                }
            )
            if self.progress_callback:
                self.progress_callback(
                    current_step="Backtest complete",
                    symbols_total=len(tickers),
                    symbols_checked=len(tickers),
                    symbols_kept=1,
                    symbols_skipped=0,
                    message="Backtest complete",
                )
            return BacktestResult(
                ticker=result_ticker,
                strategy_name=strategy.name,
                trades=[
                    Trade(
                        ticker=tickers[0],
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
            "tickers": [" aapl ", "MSFT", "AAPL"],
            "strategy": "pullback",
            "history_period": "5d",
            "hold_days": 5,
        },
    )

    assert response.status_code == 200
    payload = wait_for_job(response.json()["job_id"])
    assert payload["status"] == "complete"
    assert calls[0]["ticker"] is None
    assert calls[0]["universe"] is None
    assert calls[0]["tickers"] == ["AAPL", "MSFT"]
    assert calls[0]["result_ticker"] == "2 Candidate Tickers"
    assert payload["result"]["ticker"] == "2 Candidate Tickers"


def test_latest_watchlist_endpoint(tmp_path, monkeypatch):
    from scanner.api import app as api_app
    from scanner.data.scanner_results import SQLiteScannerResultStore

    output_file = tmp_path / "watchlist.csv"
    pd.DataFrame([{"Ticker": "AAPL", "Composite Score": 88}]).to_csv(
        output_file,
        index=False,
    )
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            output_file=str(output_file),
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
    )
    SQLiteScannerResultStore(tmp_path / "market_data.sqlite").save_scan_results(
        pd.DataFrame([{"Ticker": "MSFT", "Composite Score": 92}]),
        universe="sp500",
        market_data_provider="yahoo",
        history_period="6mo",
        output_file=str(output_file),
    )

    response = client.get("/api/watchlist/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == 1
    assert payload["rows"] == [{"Ticker": "MSFT", "Composite Score": 92}]


def test_watchlist_risk_classification_starts_job(monkeypatch):
    from scanner.api import app as api_app

    calls = []

    class FakeRiskService:
        def __init__(self, context, store, **kwargs):
            calls.append((context.settings.market_data_provider, kwargs["max_workers"]))

        def run(self, run_id):
            calls.append(run_id)
            return SimpleNamespace(
                run_id=run_id,
                classified_count=12,
                skipped=[],
                cancelled=False,
            )

    monkeypatch.setattr(api_app, "WatchlistRiskClassificationService", FakeRiskService)

    response = client.post(
        "/api/watchlist/classify-risk",
        json={"run_id": 8, "market_data_provider": "massive"},
    )

    assert response.status_code == 200
    payload = wait_for_job(response.json()["job_id"])
    assert payload["status"] == "complete"
    assert payload["result"]["scanner_run_id"] == 8
    assert payload["result"]["classified_count"] == 12
    assert calls == [("massive", api_app.settings.fundamental_scan_workers), 8]


def test_latest_watchlist_endpoint_backfills_csv_into_sqlite(tmp_path, monkeypatch):
    from scanner.api import app as api_app
    from scanner.data.scanner_results import SQLiteScannerResultStore

    output_file = tmp_path / "watchlist.csv"
    db_path = tmp_path / "market_data.sqlite"
    pd.DataFrame([{"Ticker": "AAPL", "Composite Score": 88}]).to_csv(
        output_file,
        index=False,
    )
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            output_file=str(output_file),
            market_data_cache_path=str(db_path),
        ),
    )

    response = client.get("/api/watchlist/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == 1
    assert payload["rows"] == [{"Ticker": "AAPL", "Composite Score": 88}]
    assert SQLiteScannerResultStore(db_path).latest_run().rows == payload["rows"]


def test_latest_watchlist_endpoint_handles_empty_file(tmp_path, monkeypatch):
    from scanner.api import app as api_app

    output_file = tmp_path / "watchlist.csv"
    output_file.write_text("")
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            output_file=str(output_file),
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
    )

    response = client.get("/api/watchlist/latest")

    assert response.status_code == 200
    assert response.json() == {
        "exists": True,
        "path": str(output_file),
        "run_id": None,
        "created_at": None,
        "rows": [],
    }


def test_refresh_watchlist_prices_recalculates_trade_levels(monkeypatch, tmp_path):
    from scanner.api import app as api_app
    from scanner.data.scanner_results import SQLiteScannerResultStore

    db_path = tmp_path / "market_data.sqlite"
    store = SQLiteScannerResultStore(db_path)
    run_id = store.save_scan_results(
        pd.DataFrame(
            [
                {
                    "Ticker": "AAPL",
                    "Price": 200.0,
                    "ATR14": 4.0,
                    "Stop 2ATR": 192.0,
                }
            ]
        ),
        universe="sp500",
        market_data_provider="yahoo",
        history_period="6mo",
        output_file="output/watchlist.csv",
    )

    class FakeProvider:
        def download_price_data_batch(self, tickers, period="1y"):
            assert tickers == ["AAPL"]
            assert period == "5d"
            return {
                "AAPL": pd.DataFrame(
                    {
                        "High": [214.0, 215.0],
                        "Low": [205.0, 206.0],
                        "Close": [210.0, 212.5],
                    },
                    index=pd.to_datetime(["2026-07-01", "2026-07-02"]),
                )
            }

    monkeypatch.setattr(
        api_app,
        "create_market_data_provider",
        lambda name, cache_enabled: FakeProvider(),
    )
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            market_data_cache_path=str(db_path),
        ),
    )

    response = client.post(
        "/api/watchlist/refresh-prices",
        json={
            "run_id": run_id,
            "rows": [
                {
                    "Ticker": "AAPL",
                    "Price": 200.0,
                    "ATR14": 4.0,
                    "Stop 2ATR": 192.0,
                }
            ],
            "market_data_provider": "yahoo",
            "period": "5d",
            "reward_risk_multiple": 2.0,
            "suggested_hold_days": 5,
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["refreshed_count"] == 1
    assert payload["fallback_count"] == 0
    assert payload["rows"][0] == {
        "Ticker": "AAPL",
        "Price": 212.5,
        "ATR14": 4.0,
        "Stop 2ATR": 204.5,
        "Current Price": 212.5,
        "Price As Of": "2026-07-02",
        "Price Source": "Yahoo",
        "Entry Area": 212.5,
        "Suggested Hold Time": "5 trading days",
        "5D Range": 5,
        "Suggested Stop": 204.5,
        "Risk / Share": 8.0,
        "Stop Distance %": 3.76,
        "Target/Exit": 228.5,
        "Suggested Exit": 228.5,
    }
    assert (
        SQLiteScannerResultStore(db_path)
        .latest_run()
        .rows[0]["5D Range"]
        == 5
    )


def test_refresh_watchlist_prices_falls_back_to_cached_close(monkeypatch, tmp_path):
    from scanner.api import app as api_app

    class FakeProvider:
        def download_price_data_batch(self, tickers, period="1y"):
            return {"AAPL": pd.DataFrame()}

    monkeypatch.setattr(
        api_app,
        "create_market_data_provider",
        lambda name, cache_enabled: FakeProvider(),
    )
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(
            api_app.settings,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
    )

    response = client.post(
        "/api/watchlist/refresh-prices",
        json={
            "rows": [{"Ticker": "AAPL", "Price": 200.0, "ATR14": 4.0}],
            "market_data_provider": "yahoo",
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["refreshed_count"] == 0
    assert payload["fallback_count"] == 1
    assert payload["rows"][0]["Current Price"] == 200.0
    assert payload["rows"][0]["Price Source"] == "Cached Close"
    assert payload["rows"][0]["Stop Distance %"] == 4.0


def test_update_candidate_trade_levels_persists_to_sqlite(monkeypatch, tmp_path):
    from scanner.api import app as api_app
    from scanner.data.scanner_results import SQLiteScannerResultStore

    db_path = tmp_path / "market_data.sqlite"
    store = SQLiteScannerResultStore(db_path)
    run_id = store.save_scan_results(
        pd.DataFrame(
            [
                {
                    "Ticker": "AAPL",
                    "Price": 200.0,
                    "Entry Area": 200.0,
                    "Suggested Stop": 190.0,
                    "Target/Exit": 220.0,
                }
            ]
        ),
        universe="sp500",
        market_data_provider="yahoo",
        history_period="6mo",
        output_file="output/watchlist.csv",
    )
    monkeypatch.setattr(
        api_app,
        "settings",
        replace(api_app.settings, market_data_cache_path=str(db_path)),
    )

    response = client.post(
        "/api/watchlist/candidates/AAPL/trade-levels",
        json={
            "run_id": run_id,
            "entry_area": 201.25,
            "suggested_stop": 191.5,
            "target_exit": 222.75,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["row"]["Entry Area"] == 201.25
    assert payload["row"]["Suggested Stop"] == 191.5
    assert payload["row"]["Target/Exit"] == 222.75
    assert payload["row"]["Trade Levels Edited"] == "YES"
    assert SQLiteScannerResultStore(db_path).latest_run().rows[0]["Entry Area"] == 201.25


def test_reports_endpoint_lists_output_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_dir = Path("output")
    output_dir.mkdir()
    (output_dir / "daily_scanner_report_2026-07-05.html").write_text(
        "<html></html>"
    )
    (output_dir / "scanner.log").write_text("scan log")

    response = client.get("/api/reports")

    assert response.status_code == 200
    report_types = {report["type"] for report in response.json()}
    assert "daily_scanner" in report_types
    assert "log" in report_types


def test_generate_daily_scanner_report_from_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/reports/daily-scanner",
        json={
            "report_date": "2026-07-05",
            "rows": [
                {
                    "Ticker": "AAPL",
                    "Triggered Strategies": "Pullback Strategy",
                    "Composite Score": 90,
                    "Price": 100,
                    "Stop 2ATR": 95,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    report_path = Path(payload["report"]["path"])
    assert report_path.exists()
    assert payload["report"]["type"] == "daily_scanner"
    assert Path(payload["archived_watchlist"]).exists()
    assert "Daily Scanner Report" in report_path.read_text(encoding="utf-8")


def test_generate_daily_scanner_report_rejects_empty_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/reports/daily-scanner",
        json={"report_date": "2026-07-05", "rows": []},
    )

    assert response.status_code == 422
