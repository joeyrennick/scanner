from pathlib import Path

import pandas as pd

from scanner.fundamentals import FundamentalAnalysisService
from scanner.fundamentals.cache import FundamentalAnalysisCache
from scanner.reports.fundamental_analysis_report import FundamentalAnalysisReport


class FakeFundamentalProvider:
    source_name = "SEC EDGAR"

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
    assert result["risk"]["complete"] is True
    assert result["validation"]["status"] in {"validated", "needs_review"}
    assert result["confidence"] == "high"


def test_fundamental_analysis_uses_separate_price_provider_and_derives_ratios():
    class FakePriceProvider:
        name = "test prices"

        def download_price_data(self, ticker, period="5y"):
            assert ticker == "EXM"
            assert period == "5y"
            return pd.DataFrame(
                {"Close": [300.0, 305.0]},
                index=pd.date_range("2026-01-01", periods=2),
            )

    result = FundamentalAnalysisService(
        FakeFundamentalProvider(),
        FakePriceProvider(),
    ).analyze("EXM")

    assert result["schema_version"] == 3
    assert result["source"] == "SEC EDGAR (financials); Test Prices (prices)"
    assert result["current_price"] == 305.0
    assert result["ratios"]["price_to_sales"] == 20_000_000_000 / 14_000_000_000
    assert result["ratios"]["free_cash_flow_yield"] == 0.1


def test_screen_valuation_includes_risk_from_supplied_price_history():
    history = pd.DataFrame(
        {"Close": [100 + index * 0.1 for index in range(260)]},
        index=pd.date_range("2025-01-01", periods=260),
    )

    result = FundamentalAnalysisService(FakeFundamentalProvider()).screen_valuation(
        "EXM",
        current_price=125.9,
        price_history=history,
    )

    assert result["risk"]["label"] == "low"
    assert result["risk"]["score"] == 0


def test_screen_risk_can_be_added_after_valuation_screening():
    service = FundamentalAnalysisService(FakeFundamentalProvider())
    screened = service.screen_valuation("EXM", current_price=125.9)
    history = pd.DataFrame(
        {"Close": [100 + index * 0.1 for index in range(260)]},
        index=pd.date_range("2025-01-01", periods=260),
    )

    enriched = service.add_screen_risk(screened, history)

    assert enriched["risk"]["label"] == "low"
    assert screened["valuation"] == enriched["valuation"]


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
    assert '"validation"' in snapshot


def test_fundamental_analysis_cache_keys_assumptions_and_marks_hits(tmp_path):
    cache = FundamentalAnalysisCache(tmp_path / "cache.sqlite")
    payload = {
        "ticker": "EXM",
        "schema_version": 3,
        "risk": {"label": "low", "score": 25},
        "validation": {
            "status": "validated",
            "label": "Validated candidate",
            "score": 100,
            "reasons": [],
            "model": "dcf",
        },
    }

    cache.set("EXM", {"discount_rate": 0.1}, payload)

    hit = cache.get("EXM", {"discount_rate": 0.1})
    assert hit is not None
    assert hit["cache"]["status"] == "hit"
    assert cache.get("EXM", {"discount_rate": 0.12}) is None
    assert cache.latest_risks(["EXM", "MISSING"]) == {
        "EXM": {"label": "low", "score": 25}
    }
    assert cache.latest_validations(["EXM", "MISSING"]) == {
        "EXM": {
            "status": "validated",
            "label": "Validated candidate",
            "score": 100,
            "reasons": [],
            "model": "dcf",
        }
    }
