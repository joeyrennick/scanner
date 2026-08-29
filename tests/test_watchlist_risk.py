from types import SimpleNamespace

import pandas as pd

from scanner.data.scanner_results import SQLiteScannerResultStore
from scanner.services.watchlist_risk import WatchlistRiskClassificationService


class FakeContext:
    def __init__(self, price_provider):
        self.settings = SimpleNamespace(
            sec_user_agent="Tests test@example.com",
            market_data_cache_path=":memory:",
            sec_fundamentals_cache_ttl_hours=24,
            sec_max_requests_per_second=8,
        )
        self.price_provider = price_provider

    def get_market_data_provider(self):
        return self.price_provider

    def download_price_data(self, ticker, period="1y"):
        assert period == "5y"
        return self.price_provider.download_price_data(ticker, period)


class FakePriceProvider:
    def download_price_data(self, ticker, period="5y"):
        if ticker == "LOW":
            values = [100 + index * 0.1 for index in range(260)]
        else:
            values = ([100, 40] * 130)
        return pd.DataFrame(
            {"Close": values},
            index=pd.date_range("2025-01-01", periods=len(values)),
        )


class FakeFundamentalsProvider:
    source_name = "SEC EDGAR"

    def prepare(self, ticker):
        assert ticker == "LOW"

    def download_fundamental_data(self, ticker):
        high_risk = ticker == "HIGH"
        years = range(2021, 2026)
        return {
            "profile": {"ticker": ticker, "name": ticker},
            "income_statements": [
                {
                    "timeframe": "annual",
                    "period_end": f"{year}-12-31",
                    "fiscal_year": year,
                    "revenue": 1_000_000,
                    "diluted_shares_outstanding": 100_000,
                }
                for year in years
            ],
            "balance_sheets": [
                {
                    "timeframe": "annual",
                    "period_end": f"{year}-12-31",
                    "fiscal_year": year,
                    "debt_current": 0,
                    "long_term_debt_and_capital_lease_obligations": (
                        10_000_000 if high_risk else 100_000
                    ),
                }
                for year in years
            ],
            "cash_flow_statements": [
                {
                    "timeframe": "annual",
                    "period_end": f"{year}-12-31",
                    "net_cash_from_operating_activities": (
                        -100_000 if high_risk else 1_000_000
                    ),
                    "purchase_of_property_plant_and_equipment": -100_000,
                }
                for year in years
            ],
            "ratios": [],
        }


def test_classifies_and_persists_missing_watchlist_risk(tmp_path):
    store = SQLiteScannerResultStore(tmp_path / "scanner.sqlite")
    run_id = store.save_scan_results(
        pd.DataFrame(
            [
                {"Ticker": "LOW", "Current Price": 125.9, "Risk Level": "low"},
                {"Ticker": "HIGH", "Current Price": 40.0},
            ]
        ),
        universe="all",
        market_data_provider="test",
        history_period="5d",
        output_file=str(tmp_path / "watchlist.csv"),
    )
    progress = []
    price_provider = FakePriceProvider()

    result = WatchlistRiskClassificationService(
        FakeContext(price_provider),
        store,
        fundamentals_provider=FakeFundamentalsProvider(),
        progress_callback=lambda **changes: progress.append(changes),
        max_workers=1,
    ).run(run_id)

    rows = {row["Ticker"]: row for row in store.get_run(run_id).rows}
    assert result.classified_count == 2
    assert rows["LOW"]["Risk Level"] == "low"
    assert rows["LOW"]["Risk Score"] == 0
    assert rows["HIGH"]["Risk Level"] == "high"
    assert rows["HIGH"]["Risk Score"] == 100
    assert rows["LOW"]["Validation Status"] in {
        "validated",
        "needs_review",
        "rejected",
    }
    assert rows["HIGH"]["Validation Status"] == "rejected"
    assert progress[-1]["symbols_checked"] == 2
