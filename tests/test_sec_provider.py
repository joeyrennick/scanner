from datetime import date, timedelta

import requests

from scanner.data.providers.sec import SECFundamentalsProvider
from scanner.fundamentals.sec_cache import SECFundamentalsCache


def _duration(value, end, filed, days=364):
    start = date.fromisoformat(end) - timedelta(days=days)
    return {
        "start": start.isoformat(),
        "end": end,
        "val": value,
        "form": "10-K",
        "filed": filed,
        "fp": "FY",
    }


def _instant(value, end, filed):
    return {
        "end": end,
        "val": value,
        "form": "10-K",
        "filed": filed,
        "fp": "FY",
    }


def _concept(unit, observations):
    return {"units": {unit: observations}}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self.payload


def test_sec_provider_normalizes_annual_company_facts(monkeypatch):
    end = "2025-12-31"
    bank_end = "2024-12-31"
    filed = "2026-02-15"
    ticker_payload = {
        "0": {"cik_str": 1234, "ticker": "BRK-B", "title": "Example Holdings"}
    }
    submissions = {
        "name": "Example Holdings Inc.",
        "sicDescription": "Insurance",
    }
    facts = {
        "entityName": "Example Holdings Inc.",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": _concept(
                    "USD",
                    [
                        _duration(25, end, filed, days=90),
                        _duration(100, end, filed),
                    ],
                ),
                "GrossProfit": _concept("USD", [_duration(60, end, filed)]),
                "OperatingIncomeLoss": _concept("USD", [_duration(30, end, filed)]),
                "NetIncomeLoss": _concept("USD", [_duration(20, end, filed)]),
                "WeightedAverageNumberOfDilutedSharesOutstanding": _concept(
                    "shares", [_duration(10, end, filed)]
                ),
                "EarningsPerShareDiluted": _concept(
                    "USD/shares", [_duration(2, end, filed)]
                ),
                "InterestIncomeExpenseNet": _concept(
                    "USD", [_duration(70, bank_end, "2025-02-15")]
                ),
                "NoninterestIncome": _concept(
                    "USD", [_duration(30, bank_end, "2025-02-15")]
                ),
                "WeightedAverageNumberOfSharesOutstandingBasic": _concept(
                    "shares", [_duration(9, bank_end, "2025-02-15")]
                ),
                "EarningsPerShareBasicAndDiluted": _concept(
                    "USD/shares", [_duration(1.5, bank_end, "2025-02-15")]
                ),
                "CashAndCashEquivalentsAtCarryingValue": _concept(
                    "USD", [_instant(40, end, filed)]
                ),
                "AssetsCurrent": _concept("USD", [_instant(80, end, filed)]),
                "LiabilitiesCurrent": _concept("USD", [_instant(50, end, filed)]),
                "ShortTermBorrowings": _concept("USD", [_instant(3, end, filed)]),
                "LongTermDebtCurrent": _concept("USD", [_instant(2, end, filed)]),
                "LongTermDebtNoncurrent": _concept("USD", [_instant(15, end, filed)]),
                "StockholdersEquity": _concept("USD", [_instant(70, end, filed)]),
                "NetCashProvidedByUsedInOperatingActivities": _concept(
                    "USD", [_duration(22, end, filed)]
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": _concept(
                    "USD", [_duration(4, end, filed)]
                ),
            }
        },
    }
    payloads = iter((ticker_payload, facts, submissions))
    captured_headers = []

    def fake_get(_url, headers, timeout):
        captured_headers.append(headers)
        assert timeout == 30
        return FakeResponse(next(payloads))

    monkeypatch.setattr("scanner.data.providers.sec.requests.get", fake_get)

    result = SECFundamentalsProvider(
        user_agent="Example Co admin@example.com"
    ).download_fundamental_data("BRK.B")

    assert result["profile"]["name"] == "Example Holdings Inc."
    assert result["profile"]["sic_description"] == "Insurance"
    assert result["income_statements"][0]["revenue"] == 100
    assert result["income_statements"][0]["diluted_shares_outstanding"] == 9
    assert result["income_statements"][0]["diluted_earnings_per_share"] == 1.5
    assert result["income_statements"][1]["revenue"] == 100
    assert result["balance_sheets"][0]["debt_current"] == 5
    assert result["cash_flow_statements"][0][
        "purchase_of_property_plant_and_equipment"
    ] == -4
    assert all(
        headers["User-Agent"] == "Example Co admin@example.com"
        for headers in captured_headers
    )


def test_sec_provider_reports_missing_ticker(monkeypatch):
    monkeypatch.setattr(
        "scanner.data.providers.sec.requests.get",
        lambda *_args, **_kwargs: FakeResponse(
            {"0": {"cik_str": 1234, "ticker": "OTHER", "title": "Other Corp"}}
        ),
    )

    provider = SECFundamentalsProvider()

    try:
        provider.download_fundamental_data("MISSING")
    except RuntimeError as error:
        assert str(error) == "Ticker MISSING was not found in the SEC company ticker list."
    else:
        raise AssertionError("Expected missing SEC ticker to raise RuntimeError")


def test_sec_provider_expands_share_counts_reported_in_thousands_or_millions(
    monkeypatch,
):
    filed = "2026-02-15"
    first_end = "2024-12-31"
    second_end = "2025-12-31"
    ticker_payload = {
        "0": {"cik_str": 63908, "ticker": "MCD", "title": "McDonald's Corp"}
    }
    facts = {
        "entityName": "McDonald's Corp",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": _concept(
                    "USD",
                    [
                        _duration(100_000_000, first_end, filed),
                        _duration(8_563_000_000, second_end, filed),
                    ],
                ),
                "WeightedAverageNumberOfDilutedSharesOutstanding": _concept(
                    "shares",
                    [
                        _duration(100_000, first_end, filed),
                        _duration(716.4, second_end, filed),
                    ],
                ),
                "EarningsPerShareDiluted": _concept(
                    "USD/shares",
                    [
                        _duration(1.0, first_end, filed),
                        _duration(11.95, second_end, filed),
                    ],
                ),
            }
        },
    }
    payloads = iter((ticker_payload, facts))
    monkeypatch.setattr(
        "scanner.data.providers.sec.requests.get",
        lambda *_args, **_kwargs: FakeResponse(next(payloads)),
    )

    result = SECFundamentalsProvider(
        user_agent="Share Scale Test test@example.com",
        include_submissions=False,
    ).download_fundamental_data("MCD")
    rows = {row["period_end"]: row for row in result["income_statements"]}

    assert rows[first_end]["diluted_shares_outstanding"] == 100_000_000
    assert rows[first_end]["diluted_shares_scale_factor"] == 1_000
    assert rows[second_end]["diluted_shares_outstanding"] == 716_400_000
    assert rows[second_end]["diluted_shares_reported"] == 716.4
    assert rows[second_end]["diluted_shares_scale_factor"] == 1_000_000


def test_sec_provider_repairs_cached_share_units_without_refetching(tmp_path):
    cache_path = tmp_path / "cache.sqlite"
    cache = SECFundamentalsCache(cache_path)
    cache.set(
        "MCD",
        {
            "profile": {"ticker": "MCD", "name": "McDonald's Corp"},
            "income_statements": [
                {
                    "period_end": "2025-12-31",
                    "consolidated_net_income_loss": 8_563_000_000,
                    "diluted_shares_outstanding": 716.4,
                    "diluted_earnings_per_share": 11.95,
                }
            ],
            "balance_sheets": [],
            "cash_flow_statements": [],
            "ratios": [],
        },
    )
    provider = SECFundamentalsProvider(
        user_agent="Cached Share Scale Test test@example.com",
        cache_path=str(cache_path),
        include_submissions=False,
    )
    provider._ticker_map = {
        "MCD": {"cik_str": 63908, "ticker": "MCD", "title": "McDonald's Corp"}
    }

    result = provider.download_fundamental_data("MCD")

    assert result["income_statements"][0]["diluted_shares_outstanding"] == 716_400_000
    assert cache.get("MCD")["income_statements"][0][
        "diluted_shares_outstanding"
    ] == 716_400_000
