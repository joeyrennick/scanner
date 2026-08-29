from __future__ import annotations

from datetime import date, datetime
import math
import re
from typing import Any


VALIDATION_POLICY_VERSION = 1
MINIMUM_DCF_MARGIN = 0.15
LOW_RISK_MARGIN = 0.20
MODERATE_RISK_MARGIN = 0.30
MAXIMUM_AUTOMATIC_MARGIN = 2.0
MINIMUM_QUALITY_SCORE = 50
MINIMUM_FINANCIAL_PERIODS = 4
MAXIMUM_FINANCIAL_PERIOD_AGE_DAYS = 500

SECTOR_SPECIFIC_MODEL_PATTERN = re.compile(
    r"\b(bank|bancorp|bancshares|financial|insurance|assurance|reit|"
    r"real estate investment trust|savings institution|credit union|"
    r"brokerage|security broker|investment banking)\b",
    re.IGNORECASE,
)


def validate_fundamental_analysis(
    analysis: dict[str, Any],
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    as_of = as_of or date.today()
    history = list(analysis.get("financial_history") or [])
    latest = history[-1] if history else {}
    company = analysis.get("company") or {}
    quality = analysis.get("quality") or {}
    risk = analysis.get("risk") or {}
    valuation = analysis.get("valuation") or {}
    ratios = analysis.get("ratios") or {}
    scenarios = {
        str(scenario.get("name") or "").lower(): scenario
        for scenario in valuation.get("scenarios") or []
    }
    margin = _number(valuation.get("margin_of_safety"))
    fair_value = _number((scenarios.get("base") or {}).get("fair_value"))
    current_price = _number(analysis.get("current_price"))
    shares = _number(latest.get("diluted_shares"))
    free_cash_flow = _number(latest.get("free_cash_flow"))
    filing_age = _filing_age_days(analysis.get("data_as_of"), as_of)
    checks: list[dict[str, Any]] = []

    _append_check(
        checks,
        "Financial history",
        len(history) >= MINIMUM_FINANCIAL_PERIODS,
        "fail",
        len(history),
        f"At least {MINIMUM_FINANCIAL_PERIODS} annual periods are required.",
    )
    _append_check(
        checks,
        "Financial period recency",
        filing_age is not None
        and filing_age <= MAXIMUM_FINANCIAL_PERIOD_AGE_DAYS,
        "fail",
        filing_age,
        "Latest financial period must be no more than "
        f"{MAXIMUM_FINANCIAL_PERIOD_AGE_DAYS} days old.",
    )
    _append_check(
        checks,
        "Positive free cash flow",
        free_cash_flow is not None and free_cash_flow > 0,
        "fail",
        free_cash_flow,
        "A common-stock DCF requires positive current free cash flow.",
    )
    _append_check(
        checks,
        "Valid diluted share count",
        shares is not None and shares > 0,
        "fail",
        shares,
        "A positive diluted share count is required for per-share fair value.",
    )
    _append_check(
        checks,
        "Base DCF available",
        fair_value is not None
        and fair_value > 0
        and current_price is not None
        and current_price > 0,
        "fail",
        fair_value,
        "Base fair value and current price must both be positive.",
    )
    _append_check(
        checks,
        "DCF candidate threshold",
        margin is not None and margin >= MINIMUM_DCF_MARGIN,
        "fail",
        margin,
        "Base DCF margin of safety must be at least 15%.",
    )

    company_identity = " ".join(str(company.get(key) or "") for key in ("name", "sector"))
    sector_specific = bool(SECTOR_SPECIFIC_MODEL_PATTERN.search(company_identity))
    _append_check(
        checks,
        "DCF model suitability",
        not sector_specific,
        "review",
        "sector-specific" if sector_specific else "standard operating company",
        "Banks, insurers, financial firms, and REITs require sector-specific "
        "valuation methods.",
    )

    quality_score = _number(quality.get("score"))
    _append_check(
        checks,
        "Business quality",
        quality_score is not None and quality_score >= MINIMUM_QUALITY_SCORE,
        "review",
        quality_score,
        f"Business quality must be at least {MINIMUM_QUALITY_SCORE}/100.",
    )

    risk_label = str(risk.get("label") or "unknown").lower()
    risk_complete = bool(risk.get("complete")) or all(
        _number((risk.get("metrics") or {}).get(key)) is not None
        for key in ("annualized_volatility", "maximum_drawdown")
    )
    _append_check(
        checks,
        "Risk analysis complete",
        risk_complete and risk_label in {"low", "moderate", "high"},
        "review",
        risk_label,
        "A completed market and financial risk analysis is required.",
    )

    required_margin = {"low": LOW_RISK_MARGIN, "moderate": MODERATE_RISK_MARGIN}.get(risk_label)
    risk_adjusted_pass = (
        required_margin is not None
        and margin is not None
        and margin >= required_margin
    )
    _append_check(
        checks,
        "Risk-adjusted margin of safety",
        risk_adjusted_pass,
        "review",
        margin,
        "Low-risk candidates require 20% margin; moderate-risk candidates "
        "require 30%; high-risk candidates require manual review.",
    )
    _append_check(
        checks,
        "DCF output sanity",
        margin is not None and margin <= MAXIMUM_AUTOMATIC_MARGIN,
        "review",
        margin,
        "Margins above 200% require manual unit, share-count, and assumption review.",
    )

    fcf_yield = _number(ratios.get("free_cash_flow_yield"))
    pe = _number(ratios.get("price_to_earnings"))
    earnings_yield = 1 / pe if pe is not None and pe > 0 else None
    independent_pass = (
        (fcf_yield is not None and fcf_yield >= 0.04)
        or (earnings_yield is not None and earnings_yield >= 0.04)
    )
    _append_check(
        checks,
        "Independent valuation support",
        independent_pass,
        "review",
        {
            "free_cash_flow_yield": fcf_yield,
            "earnings_yield": earnings_yield,
        },
        "At least one of free-cash-flow yield or earnings yield must be 4% or higher.",
    )

    bear_upside = _number((scenarios.get("bear") or {}).get("upside"))
    _append_check(
        checks,
        "Bear-case resilience",
        bear_upside is not None and bear_upside >= -0.20,
        "review",
        bear_upside,
        "Bear-case fair value should be no more than 20% below the current price.",
    )

    hard_failures = [check for check in checks if check["status"] == "fail"]
    reviews = [check for check in checks if check["status"] == "review"]
    if hard_failures:
        status, label = "rejected", "Rejected"
    elif reviews:
        status, label = "needs_review", "Needs review"
    else:
        status, label = "validated", "Validated candidate"

    passed = sum(check["status"] == "pass" for check in checks)
    raw_score = round(100 * passed / len(checks)) if checks else 0
    score = raw_score
    if status == "rejected":
        score = min(score, 49)
    elif status == "needs_review":
        score = min(score, 79)
    return {
        "policy_version": VALIDATION_POLICY_VERSION,
        "status": status,
        "label": label,
        "score": score,
        "checks": checks,
        "reasons": [check["explanation"] for check in hard_failures + reviews],
        "model": "sector_specific" if sector_specific else "dcf",
        "manual_filing_review_required": True,
        "manual_review_items": [
            "Read the latest 10-K Item 1A risk factors and Item 7 MD&A.",
            "Review subsequent 10-Q and 8-K filings for material changes.",
            "Confirm accounting units, diluted shares, and non-recurring cash flows.",
        ],
    }


def _append_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    failure_status: str,
    value: Any,
    explanation: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "pass" if passed else failure_status,
            "value": value,
            "explanation": explanation,
        }
    )


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _filing_age_days(value: Any, as_of: date) -> int | None:
    if not value:
        return None
    try:
        period = datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None
    return (as_of - period).days
