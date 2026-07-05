import pandas as pd

from scanner.config.settings import ScannerSettings
from scanner.context import ScannerContext
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


class FakeProvider:
    name = "fake_scan"

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        return pd.DataFrame(
            {"Close": [100.0, 101.0]},
            index=pd.to_datetime(["2026-07-02", "2026-07-03"]),
        )


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
    assert output_file.exists()
    assert pd.read_csv(output_file)["Ticker"].tolist() == ["AAPL"]
    assert "Loaded 2 tickers" in logger.infos
    assert "Trade candidates: 1" in logger.infos
