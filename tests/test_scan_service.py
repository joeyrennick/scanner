import pandas as pd

from scanner.config.settings import ScannerSettings
from scanner.context import ScannerContext
from scanner.data.cache import SQLiteMarketDataCache
from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.data.providers.cached import CachedMarketDataProvider
from scanner.models.stock_analysis import StockAnalysis
from scanner.models.strategy_result import StrategyResult
from scanner.scoring.score_engine import ScoreBreakdown
from scanner.services.scan_service import ScanConfig, ScanService
from scanner.strategies.strategy_category import StrategyCategory


class FakeLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)


class FakeUniverseProvider:
    def get_universe_tickers(self, universe):
        return ["AAPL", "MSFT"]

    def get_company_name(self, ticker):
        return {"AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation"}.get(ticker)


class FakeProvider:
    name = "fake_scan"

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        return pd.DataFrame(
            {"Close": [100.0, 101.0]},
            index=pd.to_datetime(["2026-07-02", "2026-07-03"]),
        )

    def download_company_profiles_batch(self, tickers):
        return {
            ticker: {"name": "Apple Inc." if ticker == "AAPL" else "", "sector": "Information Technology"}
            for ticker in tickers
        }


class RateLimitedBatchProvider:
    name = "fake_rate_limited_scan"

    def __init__(self):
        self.batch_calls = []

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        raise AssertionError("scan should not fall through to single-ticker fetches")

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        self.batch_calls.append((tuple(tickers), period))
        raise RuntimeError("YFRateLimitError: Too Many Requests")


def create_analysis(ticker: str, triggered: bool) -> StockAnalysis:
    return StockAnalysis(
        ticker=ticker,
        price=100,
        ma20=99,
        ma50=98,
        ma200=90,
        relative_strength=10,
        atr14=2,
        avg_volume_20=1_000_000,
        relative_volume=1.2,
        score_breakdown=ScoreBreakdown(
            trend_score=50,
            relative_strength_score=15,
            volume_score=5,
            volatility_score=10,
        ),
        strategy_results=[
            StrategyResult(
                name="Pullback Strategy",
                category=StrategyCategory.ENTRY,
                triggered=triggered,
                score=20 if triggered else 0,
                reason="test",
                checks={"Test Check": triggered},
            )
        ],
    )


def test_scan_service_returns_structured_result_and_writes_watchlist(
    tmp_path,
    monkeypatch,
):
    logger = FakeLogger()
    context = ScannerContext(
        settings=ScannerSettings(
            benchmark_ticker="SPY",
            max_workers=1,
            market_data_cache_enabled=False,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
        logger=logger,
        market_data_provider=FakeProvider(),
    )
    service = ScanService(
        context=context,
        logger=logger,
        universe_provider=FakeUniverseProvider(),
    )

    def fake_analyze_one(self, ticker, benchmark_data, period):
        return create_analysis(ticker=ticker, triggered=ticker == "AAPL")

    monkeypatch.setattr(ScanService, "_analyze_one", fake_analyze_one)

    output_file = tmp_path / "watchlist.csv"
    result = service.run(
        ScanConfig(
            universe="sp500",
            history_period="5d",
            output_file=str(output_file),
        )
    )

    assert result.tickers == ["AAPL", "MSFT"]
    assert [analysis.ticker for analysis in result.analyses] == ["AAPL", "MSFT"]
    assert [candidate.ticker for candidate in result.trade_candidates] == ["AAPL"]
    assert result.skipped == []
    assert result.dataframe["Ticker"].tolist() == ["AAPL"]
    assert result.dataframe["Company Name"].tolist() == ["Apple Inc."]
    assert result.dataframe["Sector"].tolist() == ["Information Technology"]
    assert result.scanner_run_id == 1
    assert output_file.exists()
    assert pd.read_csv(output_file)["Ticker"].tolist() == ["AAPL"]
    latest_run = SQLiteScannerResultStore(tmp_path / "market_data.sqlite").latest_run()
    assert latest_run is not None
    assert latest_run.rows[0]["Ticker"] == "AAPL"
    assert latest_run.rows[0]["Company Name"] == "Apple Inc."
    assert "Loaded 2 tickers" in logger.infos
    assert "Trade candidates: 1" in logger.infos


def test_scan_service_stops_after_cache_warmup_rate_limit(
    tmp_path,
    monkeypatch,
):
    from scanner.data import market_data

    monkeypatch.setattr(market_data, "MAX_DOWNLOAD_ATTEMPTS", 1)
    logger = FakeLogger()
    provider = RateLimitedBatchProvider()
    cached_provider = CachedMarketDataProvider(
        provider=provider,
        cache=SQLiteMarketDataCache(tmp_path / "market_data.sqlite"),
    )
    context = ScannerContext(
        settings=ScannerSettings(
            benchmark_ticker="SPY",
            max_workers=1,
            market_data_cache_enabled=True,
            market_data_cache_path=str(tmp_path / "market_data.sqlite"),
        ),
        logger=logger,
        market_data_provider=cached_provider,
    )
    service = ScanService(
        context=context,
        logger=logger,
        universe_provider=FakeUniverseProvider(),
    )

    def fail_analyze_one(self, ticker, benchmark_data, period):
        raise AssertionError("analysis should not run without warmed cache")

    monkeypatch.setattr(ScanService, "_analyze_one", fail_analyze_one)

    output_file = tmp_path / "watchlist.csv"
    result = service.run(
        ScanConfig(
            universe="sp500",
            history_period="5d",
            output_file=str(output_file),
            cache_warmup_batch_size=1,
            cache_warmup_batch_delay_seconds=0,
        )
    )

    assert provider.batch_calls == [(("SPY",), "5d")]
    assert result.cache_warmup_result is not None
    assert result.cache_warmup_result.stopped_for_rate_limit is True
    assert result.analyses == []
    assert result.trade_candidates == []
    assert output_file.exists()
