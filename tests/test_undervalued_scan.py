from pathlib import Path

import pandas as pd
import pytest

from scanner.config.settings import ScannerSettings
from scanner.context import ScannerContext
from scanner.services.undervalued_scan import (
    IncompleteCandidateAssessment,
    UndervaluedScanConfig,
    UndervaluedScanService,
    _require_complete_candidate_assessment,
)


class FakeUniverseProvider:
    def get_universe_tickers(self, universe):
        assert universe == "all"
        return ["PENNY", "EXPENSIVE", "NOPRICE", "FCNCN"]

    def get_company_name(self, ticker):
        if ticker == "FCNCN":
            return "First Citizens Depositary Shares representing Preferred Stock"
        return f"{ticker} Common Stock"

    def is_fundamental_common_equity(self, ticker):
        return ticker != "FCNCN"


class FakePriceProvider:
    name = "test prices"

    def __init__(self):
        self.calls = []

    def download_price_data(self, ticker, period="5d"):
        self.calls.append((ticker, period))
        prices = {"PENNY": 1.0, "EXPENSIVE": 1_000.0}
        if ticker not in prices:
            return pd.DataFrame()
        if period == "5y":
            price = prices[ticker]
            values = [price * (0.8 + (0.2 * index / 259)) for index in range(260)]
            return pd.DataFrame(
                {"Close": values},
                index=pd.date_range("2025-01-01", periods=260),
            )
        return pd.DataFrame(
            {"Close": [prices[ticker]]},
            index=pd.to_datetime(["2026-08-28"]),
        )


class FakeSECFundamentalsProvider:
    source_name = "SEC EDGAR"

    def __init__(self):
        self.prepared = []
        self.calls = []

    def prepare(self, ticker):
        self.prepared.append(ticker)

    def download_fundamental_data(self, ticker):
        self.calls.append(ticker)
        years = range(2021, 2026)
        return {
            "profile": {"ticker": ticker, "name": f"{ticker} Corp"},
            "income_statements": [
                {
                    "timeframe": "annual",
                    "period_end": f"{year}-12-31",
                    "fiscal_year": year,
                    "revenue": 10_000_000_000 + (year - 2021) * 1_000_000_000,
                    "consolidated_net_income_loss": 1_500_000_000,
                    "diluted_shares_outstanding": 100_000_000,
                    "diluted_earnings_per_share": 15,
                }
                for year in years
            ],
            "balance_sheets": [
                {
                    "timeframe": "annual",
                    "period_end": f"{year}-12-31",
                    "fiscal_year": year,
                    "cash_and_equivalents": 3_000_000_000,
                    "debt_current": 100_000_000,
                    "long_term_debt_and_capital_lease_obligations": 1_000_000_000,
                    "total_equity": 8_000_000_000,
                }
                for year in years
            ],
            "cash_flow_statements": [
                {
                    "timeframe": "annual",
                    "period_end": f"{year}-12-31",
                    "net_cash_from_operating_activities": 2_500_000_000,
                    "purchase_of_property_plant_and_equipment": -500_000_000,
                }
                for year in years
            ],
            "ratios": [],
        }


def test_undervalued_scan_ignores_price_and_technical_rules(tmp_path):
    price_provider = FakePriceProvider()
    sec_provider = FakeSECFundamentalsProvider()
    context = ScannerContext(
        settings=ScannerSettings(
            market_data_provider="test prices",
            market_data_cache_enabled=False,
            market_data_cache_path=str(tmp_path / "cache.sqlite"),
        ),
        market_data_provider=price_provider,
    )
    progress = []
    service = UndervaluedScanService(
        context=context,
        universe_provider=FakeUniverseProvider(),
        fundamentals_provider=sec_provider,
        progress_callback=lambda **changes: progress.append(changes),
    )
    output_file = tmp_path / "undervalued.csv"

    result = service.run(
        UndervaluedScanConfig(
            universe="all",
            market_data_provider="test prices",
            output_file=str(output_file),
            max_workers=1,
        )
    )

    assert result.tickers == ["PENNY", "EXPENSIVE", "NOPRICE"]
    assert result.excluded_non_common == [
        ("FCNCN", "First Citizens Depositary Shares representing Preferred Stock")
    ]
    assert result.analyzed_count == 2
    assert result.dataframe["Ticker"].tolist() == ["PENNY"]
    assert result.dataframe.iloc[0]["Current Price"] == 1.0
    assert result.dataframe.iloc[0]["Margin of Safety"] >= 15
    assert result.dataframe.iloc[0]["Triggered Strategies"] == "Undervalued"
    assert result.dataframe.iloc[0]["Risk Level"] == "low"
    assert result.dataframe.iloc[0]["Risk Score"] == 0
    assert bool(result.dataframe.iloc[0]["Risk Complete"]) is True
    assert result.dataframe.iloc[0]["Validation Status"] in {
        "validated",
        "needs_review",
    }
    assert result.dataframe.iloc[0]["Validation Policy Version"] == 1
    assert sec_provider.prepared == ["PENNY"]
    assert sec_provider.calls == ["PENNY", "EXPENSIVE"]
    assert price_provider.calls == [
        ("PENNY", "5d"),
        ("PENNY", "5y"),
        ("EXPENSIVE", "5d"),
        ("NOPRICE", "5d"),
    ]
    assert result.skipped == [("NOPRICE", "Current market price is unavailable")]
    assert Path(output_file).exists()
    assert result.scanner_run_id == 1
    assert progress[-1]["current_step"] == (
        "Valuation and fundamental validation complete"
    )
    assert progress[-1]["message"] == (
        "Valuation and fundamental validation complete for 1 candidates"
    )


def test_scanner_refuses_to_save_a_candidate_without_completed_validation():
    analysis = {
        "ticker": "EXM",
        "risk": {"label": "low", "complete": True},
        "validation": {"status": "not_calculated", "checks": []},
    }

    with pytest.raises(
        IncompleteCandidateAssessment,
        match="fundamental validation is incomplete",
    ):
        _require_complete_candidate_assessment(analysis)
