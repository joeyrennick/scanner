from copy import deepcopy
from datetime import date

from scanner.fundamentals.validation import validate_fundamental_analysis


def valid_analysis():
    return {
        "company": {"name": "Example Software, Inc.", "sector": "Software"},
        "current_price": 100.0,
        "data_as_of": "2025-12-31",
        "financial_history": [
            {
                "period_end": f"{year}-12-31",
                "free_cash_flow": 500_000_000,
                "diluted_shares": 100_000_000,
            }
            for year in range(2021, 2026)
        ],
        "ratios": {"free_cash_flow_yield": 0.05, "price_to_earnings": 20.0},
        "quality": {"score": 80, "label": "strong"},
        "risk": {
            "score": 25,
            "label": "low",
            "complete": True,
            "metrics": {"annualized_volatility": 0.2, "maximum_drawdown": -0.25},
        },
        "valuation": {
            "margin_of_safety": 0.25,
            "scenarios": [
                {"name": "bear", "fair_value": 90.0, "upside": -0.10},
                {"name": "base", "fair_value": 125.0, "upside": 0.25},
                {"name": "bull", "fair_value": 150.0, "upside": 0.50},
            ],
        },
    }


def test_validation_accepts_candidate_that_passes_all_automated_gates():
    result = validate_fundamental_analysis(
        valid_analysis(),
        as_of=date(2026, 8, 28),
    )

    assert result["status"] == "validated"
    assert result["label"] == "Validated candidate"
    assert result["score"] == 100
    assert result["policy_version"] == 4
    assert result["manual_filing_review_required"] is True


def test_validation_routes_high_risk_and_sector_specific_models_to_review():
    analysis = valid_analysis()
    analysis["company"] = {"name": "Example BancShares", "sector": "Banks"}
    analysis["risk"] = {
        "score": 75,
        "label": "high",
        "complete": True,
        "metrics": {"annualized_volatility": 0.5, "maximum_drawdown": -0.6},
    }

    result = validate_fundamental_analysis(analysis, as_of=date(2026, 8, 28))

    assert result["status"] == "needs_review"
    assert result["score"] <= 79
    assert result["model"] == "sector_specific"
    assert any(check["name"] == "DCF model suitability" and check["status"] == "review" for check in result["checks"])
    assert any(check["name"] == "Risk-adjusted margin of safety" and check["status"] == "review" for check in result["checks"])


def test_validation_rejects_incomplete_core_dcf_data():
    analysis = deepcopy(valid_analysis())
    analysis["financial_history"][-1]["diluted_shares"] = None

    result = validate_fundamental_analysis(analysis, as_of=date(2026, 8, 28))

    assert result["status"] == "rejected"
    assert result["score"] <= 49
    assert any(check["name"] == "Valid diluted share count" and check["status"] == "fail" for check in result["checks"])


def test_validation_routes_two_or_three_financial_periods_to_review():
    for period_count in (2, 3):
        analysis = deepcopy(valid_analysis())
        analysis["financial_history"] = analysis["financial_history"][-period_count:]

        result = validate_fundamental_analysis(
            analysis,
            as_of=date(2026, 8, 28),
        )

        assert result["status"] == "needs_review"
        assert any(
            check["name"] == "Financial history"
            and check["status"] == "review"
            and check["value"] == period_count
            for check in result["checks"]
        )


def test_validation_rejects_fewer_than_two_financial_periods():
    for period_count in (0, 1):
        analysis = deepcopy(valid_analysis())
        analysis["financial_history"] = analysis["financial_history"][:period_count]

        result = validate_fundamental_analysis(
            analysis,
            as_of=date(2026, 8, 28),
        )

        assert result["status"] == "rejected"
        assert any(
            check["name"] == "Financial history"
            and check["status"] == "fail"
            and check["value"] == period_count
            for check in result["checks"]
        )


def test_validation_flags_implausibly_large_dcf_output_for_review():
    analysis = deepcopy(valid_analysis())
    analysis["valuation"]["margin_of_safety"] = 4.0
    analysis["valuation"]["scenarios"][1]["upside"] = 4.0

    result = validate_fundamental_analysis(analysis, as_of=date(2026, 8, 28))

    assert result["status"] == "needs_review"
    assert any(check["name"] == "DCF output sanity" and check["status"] == "review" for check in result["checks"])


def test_validation_rejects_a_share_count_inconsistent_with_income_and_eps():
    analysis = deepcopy(valid_analysis())
    analysis["financial_history"][-1].update(
        {
            "net_income": 8_563_000_000,
            "diluted_eps": 11.95,
            "diluted_shares": 716.4,
        }
    )

    result = validate_fundamental_analysis(analysis, as_of=date(2026, 8, 28))

    assert result["status"] == "rejected"
    assert any(
        check["name"] == "Share-count consistency"
        and check["status"] == "fail"
        for check in result["checks"]
    )
