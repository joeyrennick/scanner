from pathlib import Path

import pandas as pd

from scanner.fundamentals import FundamentalAnalysisService
from scanner.fundamentals.cache import FundamentalAnalysisCache
from scanner.reports.fundamental_analysis_report import FundamentalAnalysisReport


class FakeFundamentalProvider:
    def download_fundamental_data(self, ticker):
        years = range(2021, 2026)
        return {
            "profile": {
                "ticker": ticker,
                "name": "Example Corp",
                "market_cap": 20_000_000_000,
                "sic_description": "Software",
            },
            "income_statements": [
                {
                    "timeframe": "annual",
                    "period_end": f"{year}-12-31",
                    "fiscal_year": year,
                    "revenue": 10_000_000_000 + (year - 2021) * 1_000_000_000,
                    "gross_profit": 6_000_000_000 + (year - 2021) * 600_000_000,
                    "operating_income": 2_000_000_000 + (year - 2021) * 200_000_000,
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
                    "total_current_assets": 5_000_000_000,
                    "total_current_liabilities": 2_000_000_000,
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
            "ratios": [{"price_to_earnings": 18.0}],
        }

    def download_price_data(self, ticker, period="5y"):
        return pd.DataFrame(
            {"Close": [100 + index * 0.1 for index in range(260)]},
            index=pd.date_range("2025-01-01", periods=260),
        )


def test_fundamental_analysis_calculates_explainable_sections():
    result = FundamentalAnalysisService(FakeFundamentalProvider()).analyze("EXM")

    assert result["ticker"] == "EXM"
    assert len(result["financial_history"]) == 5
    assert result["quality"]["label"] == "strong"
    assert result["valuation"]["scenarios"][1]["fair_value"] is not None
    assert result["risk"]["label"] == "low"
    assert result["confidence"] == "high"


def test_fundamental_report_creates_pdf_and_immutable_snapshot(tmp_path):
    analysis = FundamentalAnalysisService(FakeFundamentalProvider()).analyze("EXM")
    pdf_path = tmp_path / "report.pdf"
    snapshot_path = tmp_path / "report.json"

    FundamentalAnalysisReport(analysis, {"tab": "valuation"}).generate(
        pdf_path,
        snapshot_path,
    )

    assert pdf_path.read_bytes().startswith(b"%PDF")
    snapshot = snapshot_path.read_text()
    assert '"ticker": "EXM"' in snapshot
    assert '"tab": "valuation"' in snapshot


def test_fundamental_analysis_cache_keys_assumptions_and_marks_hits(tmp_path):
    cache = FundamentalAnalysisCache(tmp_path / "cache.sqlite")
    payload = {"ticker": "EXM", "schema_version": 1}

    cache.set("EXM", {"discount_rate": 0.1}, payload)

    hit = cache.get("EXM", {"discount_rate": 0.1})
    assert hit is not None
    assert hit["cache"]["status"] == "hit"
    assert cache.get("EXM", {"discount_rate": 0.12}) is None
