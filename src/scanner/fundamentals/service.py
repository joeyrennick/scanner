from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd

from scanner.fundamentals.validation import validate_fundamental_analysis


DEFAULT_ASSUMPTIONS = {
    "terminal_growth_rate": 0.025,
    "projection_years": 5,
    "risk_free_rate": 0.0425,
    "equity_risk_premium": 0.055,
    "beta": 1.0,
}

ANALYSIS_SCHEMA_VERSION = 4


class FundamentalAnalysisService:
    def __init__(self, fundamentals_provider, price_provider=None):
        self.fundamentals_provider = fundamentals_provider
        self.price_provider = price_provider or fundamentals_provider

    def analyze(
        self,
        ticker: str,
        assumptions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ticker = ticker.strip().upper()
        raw = self.fundamentals_provider.download_fundamental_data(ticker)
        price_history = self.price_provider.download_price_data(ticker, period="5y")
        normalized = _normalize(raw)
        current_price = _latest_price(price_history)
        _add_market_context(normalized, current_price)
        quality = _quality_analysis(normalized)
        risk = _risk_analysis(normalized, price_history, current_price)
        valuation = _valuation_analysis(
            normalized,
            current_price,
            assumptions or {},
        )
        warnings = _data_warnings(normalized, current_price)

        analysis = {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "ticker": ticker,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": _source_label(
                self.fundamentals_provider,
                self.price_provider,
            ),
            "company": normalized["company"],
            "current_price": current_price,
            "data_as_of": normalized["data_as_of"],
            "financial_history": normalized["financial_history"],
            "ratios": normalized["ratios"],
            "quality": quality,
            "valuation": valuation,
            "risk": risk,
            "warnings": warnings,
            "confidence": _confidence(normalized, warnings),
        }
        analysis["validation"] = validate_fundamental_analysis(analysis)
        return analysis

    def screen_valuation(
        self,
        ticker: str,
        current_price: float | None,
        assumptions: dict[str, Any] | None = None,
        price_history: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        ticker = ticker.strip().upper()
        raw = self.fundamentals_provider.download_fundamental_data(ticker)
        normalized = _normalize(raw)
        _add_market_context(normalized, current_price)
        valuation = _valuation_analysis(
            normalized,
            current_price,
            assumptions or {},
        )
        risk = _risk_analysis(
            normalized,
            price_history if price_history is not None else pd.DataFrame(),
            current_price,
        )
        quality = _quality_analysis(normalized)
        analysis = {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "ticker": ticker,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": _source_label(
                self.fundamentals_provider,
                self.price_provider,
            ),
            "company": normalized["company"],
            "current_price": current_price,
            "data_as_of": normalized["data_as_of"],
            "financial_history": normalized["financial_history"],
            "ratios": normalized["ratios"],
            "quality": quality,
            "valuation": valuation,
            "risk": risk,
            "warnings": _data_warnings(normalized, current_price),
            "confidence": _confidence(
                normalized,
                _data_warnings(normalized, current_price),
            ),
        }
        analysis["validation"] = validate_fundamental_analysis(analysis)
        return analysis

    def add_screen_risk(
        self,
        analysis: dict[str, Any],
        price_history: pd.DataFrame,
    ) -> dict[str, Any]:
        enriched = {
            **analysis,
            "risk": _risk_analysis(
                {"financial_history": analysis.get("financial_history") or []},
                price_history,
                analysis.get("current_price"),
            ),
        }
        enriched["validation"] = validate_fundamental_analysis(enriched)
        return enriched


def _normalize(raw: dict[str, object]) -> dict[str, Any]:
    profile = dict(raw.get("profile") or {})
    incomes = _annual_rows(raw.get("income_statements"))
    balances = _annual_rows(raw.get("balance_sheets"))
    cash_flows = _annual_rows(raw.get("cash_flow_statements"))
    ratios_rows = list(raw.get("ratios") or [])
    ratios = dict(ratios_rows[0]) if ratios_rows else {}
    periods = sorted(
        set(_period(row) for row in incomes + balances + cash_flows if _period(row))
    )[-5:]
    income_by_period = {_period(row): row for row in incomes}
    balance_by_period = {_period(row): row for row in balances}
    cash_by_period = {_period(row): row for row in cash_flows}
    history = []

    for period in periods:
        income = income_by_period.get(period, {})
        balance = balance_by_period.get(period, {})
        cash = cash_by_period.get(period, {})
        operating_cash = _number(
            cash,
            "net_cash_from_operating_activities",
            "cash_from_operating_activities_continuing_operations",
        )
        capex = _number(cash, "purchase_of_property_plant_and_equipment")
        free_cash_flow = (
            operating_cash + capex
            if operating_cash is not None and capex is not None
            else None
        )
        revenue = _number(income, "revenue")
        gross_profit = _number(income, "gross_profit")
        operating_income = _number(income, "operating_income")
        pretax_income = _number(income, "pretax_income")
        income_tax_expense = _number(income, "income_tax_expense")
        interest_expense = _number(income, "interest_expense")
        effective_tax_rate = (
            _clamp(income_tax_expense / pretax_income, 0, 0.50)
            if income_tax_expense is not None
            and pretax_income is not None
            and pretax_income > 0
            else None
        )
        depreciation = _number(cash, "depreciation_and_amortization")
        net_income = _number(
            income,
            "net_income_loss_attributable_common_shareholders",
            "consolidated_net_income_loss",
        )
        cash_and_equivalents = _number(balance, "cash_and_equivalents")
        current_assets = _number(balance, "total_current_assets")
        current_liabilities = _number(balance, "total_current_liabilities")
        current_debt = _number(balance, "debt_current")
        non_cash_working_capital = (
            current_assets
            - cash_and_equivalents
            - current_liabilities
            + (current_debt or 0)
            if current_assets is not None
            and cash_and_equivalents is not None
            and current_liabilities is not None
            else None
        )
        history.append(
            {
                "period_end": period,
                "fiscal_year": income.get("fiscal_year") or balance.get("fiscal_year"),
                "revenue": revenue,
                "gross_profit": gross_profit,
                "operating_income": operating_income,
                "pretax_income": pretax_income,
                "income_tax_expense": income_tax_expense,
                "effective_tax_rate": effective_tax_rate,
                "interest_expense": interest_expense,
                "net_income": net_income,
                "operating_cash_flow": operating_cash,
                "capital_expenditures": capex,
                "depreciation_and_amortization": depreciation,
                "free_cash_flow": free_cash_flow,
                "gross_margin": _ratio(gross_profit, revenue),
                "operating_margin": _ratio(operating_income, revenue),
                "cash_and_equivalents": cash_and_equivalents,
                "current_assets": current_assets,
                "current_liabilities": current_liabilities,
                "non_cash_working_capital": non_cash_working_capital,
                "debt": _sum_numbers(
                    _number(balance, "debt_current"),
                    _number(balance, "long_term_debt_and_capital_lease_obligations"),
                ),
                "equity": _number(
                    balance,
                    "total_equity_attributable_to_parent",
                    "total_equity",
                ),
                "diluted_shares": _number(income, "diluted_shares_outstanding"),
                "diluted_shares_reported": _number(
                    income,
                    "diluted_shares_reported",
                ),
                "diluted_shares_scale_factor": _number(
                    income,
                    "diluted_shares_scale_factor",
                ),
                "diluted_eps": _number(income, "diluted_earnings_per_share"),
            }
        )

    for index, row in enumerate(history):
        previous = history[index - 1] if index > 0 else {}
        current_nwc = row.get("non_cash_working_capital")
        previous_nwc = previous.get("non_cash_working_capital")
        change_nwc = (
            current_nwc - previous_nwc
            if current_nwc is not None and previous_nwc is not None
            else None
        )
        tax_rate = row.get("effective_tax_rate")
        operating_income = row.get("operating_income")
        nopat = (
            operating_income * (1 - tax_rate)
            if operating_income is not None and tax_rate is not None
            else None
        )
        depreciation = row.get("depreciation_and_amortization")
        capex = row.get("capital_expenditures")
        fcff = (
            nopat + depreciation + capex - change_nwc
            if nopat is not None
            and depreciation is not None
            and capex is not None
            and change_nwc is not None
            else None
        )
        row.update(
            {
                "change_in_working_capital": change_nwc,
                "nopat": nopat,
                "fcff": fcff,
                "fcff_margin": _ratio(fcff, row.get("revenue")),
            }
        )

    return {
        "company": {
            "name": profile.get("name") or profile.get("ticker") or "",
            "description": profile.get("description") or "",
            "market_cap": _finite(profile.get("market_cap")),
            "sector": profile.get("sic_description") or "",
            "homepage_url": profile.get("homepage_url") or "",
            "employees": _finite(profile.get("total_employees")),
        },
        "financial_history": history,
        "ratios": {key: _finite(value) for key, value in ratios.items() if _finite(value) is not None},
        "data_as_of": periods[-1] if periods else None,
    }


def _quality_analysis(data: dict[str, Any]) -> dict[str, Any]:
    history = data["financial_history"]
    revenue = [row["revenue"] for row in history]
    fcf = [row["free_cash_flow"] for row in history]
    margins = [row["operating_margin"] for row in history]
    shares = [row["diluted_shares"] for row in history]
    latest = history[-1] if history else {}
    revenue_cagr = _cagr(revenue)
    fcf_positive_years = sum(value is not None and value > 0 for value in fcf)
    margin_stable = _stable(margins, tolerance=0.05)
    current_ratio = _ratio(latest.get("current_assets"), latest.get("current_liabilities"))
    debt_to_fcf = _ratio(latest.get("debt"), latest.get("free_cash_flow"))
    dilution = _growth(shares[0], shares[-1]) if len(shares) >= 2 else None
    checks = [
        _check("Revenue growth", revenue_cagr is not None and revenue_cagr > 0, revenue_cagr, "percent"),
        _check("Positive free cash flow", bool(history) and fcf_positive_years >= max(1, len(history) - 1), fcf_positive_years, "years"),
        _check("Operating margin stability", margin_stable, _range(margins), "range"),
        _check("Current liquidity", current_ratio is not None and current_ratio >= 1, current_ratio, "multiple"),
        _check("Debt supported by cash flow", debt_to_fcf is not None and 0 <= debt_to_fcf <= 4, debt_to_fcf, "multiple"),
        _check("Limited share dilution", dilution is not None and dilution <= 0.05, dilution, "percent"),
    ]
    score = round(100 * sum(check["status"] == "pass" for check in checks) / len(checks))
    return {
        "score": score,
        "label": "strong" if score >= 75 else "acceptable" if score >= 50 else "weak",
        "checks": checks,
        "metrics": {
            "revenue_cagr": revenue_cagr,
            "positive_fcf_years": fcf_positive_years,
            "current_ratio": current_ratio,
            "debt_to_fcf": debt_to_fcf,
            "share_count_change": dilution,
        },
    }


def _valuation_analysis(
    data: dict[str, Any],
    current_price: float | None,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    history = data["financial_history"]
    latest = history[-1] if history else {}
    revenue_cagr = _cagr([row["revenue"] for row in history])
    base_growth = _clamp(
        revenue_cagr if revenue_cagr is not None else 0.05,
        0,
        0.15,
    )
    legacy_overrides = dict(overrides)
    for scenario in ("bear", "base", "bull"):
        legacy_key = f"{scenario}_growth_rate"
        driver_key = f"{scenario}_revenue_growth_rate"
        if legacy_key in legacy_overrides and driver_key not in legacy_overrides:
            legacy_overrides[driver_key] = legacy_overrides[legacy_key]

    operating_margins = [
        row.get("operating_margin") for row in history[-3:]
    ]
    normalized_margin = _median(operating_margins)
    latest_margin = _finite(latest.get("operating_margin"))
    historical_tax_rate = _median(
        [row.get("effective_tax_rate") for row in history[-3:]]
    )
    tax_rate = _clamp(
        0.21 if historical_tax_rate is None else historical_tax_rate,
        0,
        0.50,
    )
    historical_depreciation_rate = _median(
        [
            _ratio(
                row.get("depreciation_and_amortization"),
                row.get("revenue"),
            )
            for row in history[-3:]
        ]
    )
    depreciation_rate = _clamp(
        0.03
        if historical_depreciation_rate is None
        else historical_depreciation_rate,
        0,
        0.25,
    )
    historical_capex_rate = _median(
        [
            _ratio(
                abs(row["capital_expenditures"])
                if row.get("capital_expenditures") is not None
                else None,
                row.get("revenue"),
            )
            for row in history[-3:]
        ]
    )
    capex_rate = _clamp(
        0.04 if historical_capex_rate is None else historical_capex_rate,
        0,
        0.40,
    )
    historical_working_capital_rate = _median(
        [
            _ratio(
                row.get("non_cash_working_capital"),
                row.get("revenue"),
            )
            for row in history[-3:]
        ]
    )
    working_capital_rate = _clamp(
        0.05
        if historical_working_capital_rate is None
        else historical_working_capital_rate,
        -0.25,
        0.50,
    )
    shares = _finite(latest.get("diluted_shares"))
    debt = _finite(latest.get("debt"))
    cash = _finite(latest.get("cash_and_equivalents"))
    market_cap = (
        current_price * shares
        if current_price is not None and shares is not None
        else _finite(data.get("company", {}).get("market_cap"))
    )
    interest_expense = abs(_finite(latest.get("interest_expense")) or 0)
    derived_cost_of_debt = (
        _clamp(interest_expense / debt, 0.02, 0.15)
        if debt is not None and debt > 0 and interest_expense > 0
        else 0.06
    )
    base_assumptions = {
        **DEFAULT_ASSUMPTIONS,
        "base_revenue_growth_rate": base_growth,
        "bear_revenue_growth_rate": max(-0.02, base_growth - 0.04),
        "bull_revenue_growth_rate": min(0.25, base_growth + 0.04),
        "base_operating_margin": normalized_margin,
        "bear_operating_margin": (
            normalized_margin - 0.02 if normalized_margin is not None else None
        ),
        "bull_operating_margin": (
            normalized_margin + 0.02 if normalized_margin is not None else None
        ),
        "tax_rate": tax_rate,
        "depreciation_rate": depreciation_rate,
        "capex_rate": capex_rate,
        "working_capital_rate": working_capital_rate,
        "cost_of_debt": derived_cost_of_debt,
    }
    assumptions = {
        **base_assumptions,
        **{
            key: value
            for key, value in legacy_overrides.items()
            if value is not None
        },
    }
    overridden_base_growth = _finite(
        legacy_overrides.get("base_revenue_growth_rate")
    )
    if overridden_base_growth is not None:
        if "bear_revenue_growth_rate" not in legacy_overrides:
            assumptions["bear_revenue_growth_rate"] = max(
                -0.02,
                overridden_base_growth - 0.04,
            )
        if "bull_revenue_growth_rate" not in legacy_overrides:
            assumptions["bull_revenue_growth_rate"] = min(
                0.25,
                overridden_base_growth + 0.04,
            )
    overridden_base_margin = _finite(
        legacy_overrides.get("base_operating_margin")
    )
    if overridden_base_margin is not None:
        if "bear_operating_margin" not in legacy_overrides:
            assumptions["bear_operating_margin"] = overridden_base_margin - 0.02
        if "bull_operating_margin" not in legacy_overrides:
            assumptions["bull_operating_margin"] = overridden_base_margin + 0.02
    assumptions["discount_rate"] = _company_wacc(
        assumptions,
        market_cap=market_cap,
        debt=debt,
    )
    base_discount_rate = float(assumptions["discount_rate"])
    base_terminal_growth = float(assumptions["terminal_growth_rate"])
    assumptions.setdefault(
        "bear_discount_rate",
        min(0.20, base_discount_rate + 0.015),
    )
    assumptions.setdefault(
        "bull_discount_rate",
        max(base_terminal_growth + 0.01, base_discount_rate - 0.01),
    )
    assumptions.setdefault(
        "bear_terminal_growth_rate",
        max(0, base_terminal_growth - 0.005),
    )
    assumptions.setdefault(
        "bull_terminal_growth_rate",
        min(0.04, base_terminal_growth + 0.005),
    )

    scenarios = []
    for name in ("bear", "base", "bull"):
        growth = _finite(
            assumptions.get(f"{name}_revenue_growth_rate")
        )
        target_margin = _finite(assumptions.get(f"{name}_operating_margin"))
        scenario_discount_rate = _finite(
            assumptions.get(f"{name}_discount_rate")
        )
        discount_rate = float(
            assumptions["discount_rate"]
            if scenario_discount_rate is None
            else scenario_discount_rate
        )
        scenario_terminal_growth = _finite(
            assumptions.get(f"{name}_terminal_growth_rate")
        )
        terminal_growth = float(
            assumptions["terminal_growth_rate"]
            if scenario_terminal_growth is None
            else scenario_terminal_growth
        )
        forecast = _project_fcff(
            starting_revenue=_finite(latest.get("revenue")),
            starting_operating_margin=latest_margin,
            starting_working_capital=_finite(
                latest.get("non_cash_working_capital")
            ),
            initial_growth=growth,
            target_operating_margin=target_margin,
            terminal_growth=terminal_growth,
            years=int(assumptions["projection_years"]),
            tax_rate=float(assumptions["tax_rate"]),
            depreciation_rate=float(assumptions["depreciation_rate"]),
            capex_rate=float(assumptions["capex_rate"]),
            working_capital_rate=float(assumptions["working_capital_rate"]),
        )
        bridge = _fcff_valuation_bridge(
            forecast,
            discount_rate=discount_rate,
            terminal_growth=terminal_growth,
            cash=cash,
            debt=debt,
            shares=shares,
        )
        for row in forecast:
            row["discount_factor"] = (1 + discount_rate) ** row["year"]
            row["present_value_fcff"] = (
                row["fcff"] / row["discount_factor"]
            )
        value = bridge.get("fair_value_per_share")
        upside = (
            _ratio(value - current_price, current_price)
            if value is not None and current_price
            else None
        )
        scenarios.append(
            {
                "name": name,
                "growth_rate": growth,
                "revenue_growth_rate": growth,
                "operating_margin": target_margin,
                "discount_rate": discount_rate,
                "terminal_growth_rate": terminal_growth,
                "fair_value": value,
                "upside": upside,
                "forecast": forecast,
                "valuation_bridge": bridge,
            }
        )

    base = next(item for item in scenarios if item["name"] == "base")
    upside = base["upside"]
    label = "unknown"
    if upside is not None:
        label = "undervalued" if upside >= 0.15 else "overvalued" if upside <= -0.15 else "fairly valued"

    required_inputs = {
        "revenue": latest.get("revenue") is not None,
        "operating_income": latest.get("operating_income") is not None,
        "income_taxes": any(
            row.get("effective_tax_rate") is not None for row in history
        ),
        "depreciation_and_amortization": any(
            row.get("depreciation_and_amortization") is not None
            for row in history
        ),
        "capital_expenditures": any(
            row.get("capital_expenditures") is not None for row in history
        ),
        "working_capital": any(
            row.get("non_cash_working_capital") is not None for row in history
        ),
        "cash": cash is not None,
        "debt": debt is not None,
        "diluted_shares": shares is not None and shares > 0,
    }
    available_inputs = sum(required_inputs.values())
    confidence = (
        "high"
        if base["fair_value"] is not None
        and available_inputs == len(required_inputs)
        and len(history) >= 4
        else "medium" if base["fair_value"] is not None else "low"
    )
    return {
        "model": "driver_based_fcff",
        "label": label,
        "confidence": confidence,
        "current_price": current_price,
        "margin_of_safety": upside,
        "assumptions": assumptions,
        "scenarios": scenarios,
        "sensitivity": _fcff_sensitivity(
            base,
            current_price=current_price,
            cash=cash,
            debt=debt,
            shares=shares,
        ),
        "input_quality": {
            "fields": required_inputs,
            "available": available_inputs,
            "required": len(required_inputs),
            "missing": [
                name for name, available in required_inputs.items() if not available
            ],
        },
        "multiples": data["ratios"],
    }


def _company_wacc(
    assumptions: dict[str, Any],
    *,
    market_cap: float | None,
    debt: float | None,
) -> float:
    override = _finite(assumptions.get("discount_rate"))
    risk_free_rate = float(assumptions["risk_free_rate"])
    equity_risk_premium = float(assumptions["equity_risk_premium"])
    beta = max(0, float(assumptions["beta"]))
    tax_rate = _clamp(float(assumptions["tax_rate"]), 0, 0.50)
    cost_of_debt = _clamp(float(assumptions["cost_of_debt"]), 0, 0.25)
    cost_of_equity = risk_free_rate + beta * equity_risk_premium
    equity = max(0, market_cap or 0)
    borrowing = max(0, debt or 0)
    capital = equity + borrowing
    assumptions["cost_of_equity"] = cost_of_equity
    if capital <= 0:
        assumptions["equity_weight"] = 1.0
        assumptions["debt_weight"] = 0.0
        if override is not None:
            return override
        return _clamp(cost_of_equity, 0.06, 0.18)
    assumptions["equity_weight"] = equity / capital
    assumptions["debt_weight"] = borrowing / capital
    if override is not None:
        return override
    wacc = (
        equity / capital * cost_of_equity
        + borrowing / capital * cost_of_debt * (1 - tax_rate)
    )
    return _clamp(wacc, 0.06, 0.18)


def _project_fcff(
    *,
    starting_revenue: float | None,
    starting_operating_margin: float | None,
    starting_working_capital: float | None,
    initial_growth: float | None,
    target_operating_margin: float | None,
    terminal_growth: float,
    years: int,
    tax_rate: float,
    depreciation_rate: float,
    capex_rate: float,
    working_capital_rate: float,
) -> list[dict[str, float | int]]:
    if (
        starting_revenue is None
        or starting_revenue <= 0
        or starting_operating_margin is None
        or initial_growth is None
        or target_operating_margin is None
        or years <= 0
    ):
        return []
    revenue = starting_revenue
    working_capital = (
        starting_working_capital
        if starting_working_capital is not None
        else starting_revenue * working_capital_rate
    )
    forecast: list[dict[str, float | int]] = []
    for year in range(1, years + 1):
        growth = _fade(initial_growth, terminal_growth, year, years)
        operating_margin = _fade(
            starting_operating_margin,
            target_operating_margin,
            year,
            years,
        )
        revenue *= 1 + growth
        operating_income = revenue * operating_margin
        nopat = operating_income * (1 - tax_rate)
        depreciation = revenue * depreciation_rate
        capital_expenditures = revenue * capex_rate
        next_working_capital = revenue * working_capital_rate
        change_in_working_capital = next_working_capital - working_capital
        fcff = (
            nopat
            + depreciation
            - capital_expenditures
            - change_in_working_capital
        )
        forecast.append(
            {
                "year": year,
                "revenue_growth_rate": growth,
                "revenue": revenue,
                "operating_margin": operating_margin,
                "operating_income": operating_income,
                "tax_rate": tax_rate,
                "nopat": nopat,
                "depreciation_and_amortization": depreciation,
                "capital_expenditures": capital_expenditures,
                "change_in_working_capital": change_in_working_capital,
                "fcff": fcff,
            }
        )
        working_capital = next_working_capital
    return forecast


def _fcff_valuation_bridge(
    forecast: list[dict[str, Any]],
    *,
    discount_rate: float,
    terminal_growth: float,
    cash: float | None,
    debt: float | None,
    shares: float | None,
) -> dict[str, float | None]:
    if (
        not forecast
        or cash is None
        or debt is None
        or shares is None
        or shares <= 0
        or discount_rate <= terminal_growth
    ):
        return {
            "present_value_forecast": None,
            "terminal_value": None,
            "present_value_terminal": None,
            "enterprise_value": None,
            "cash": cash,
            "debt": debt,
            "equity_value": None,
            "diluted_shares": shares,
            "fair_value_per_share": None,
            "terminal_value_share": None,
        }
    present_value_forecast = sum(
        float(row["fcff"]) / ((1 + discount_rate) ** int(row["year"]))
        for row in forecast
    )
    last_fcff = float(forecast[-1]["fcff"])
    years = int(forecast[-1]["year"])
    terminal_value = (
        last_fcff
        * (1 + terminal_growth)
        / (discount_rate - terminal_growth)
    )
    present_value_terminal = terminal_value / ((1 + discount_rate) ** years)
    enterprise_value = present_value_forecast + present_value_terminal
    equity_value = enterprise_value + cash - debt
    fair_value = max(0, equity_value / shares)
    return {
        "present_value_forecast": present_value_forecast,
        "terminal_value": terminal_value,
        "present_value_terminal": present_value_terminal,
        "enterprise_value": enterprise_value,
        "cash": cash,
        "debt": debt,
        "equity_value": equity_value,
        "diluted_shares": shares,
        "fair_value_per_share": fair_value,
        "terminal_value_share": _ratio(
            present_value_terminal,
            enterprise_value,
        ),
    }


def _fcff_sensitivity(
    base_scenario: dict[str, Any],
    *,
    current_price: float | None,
    cash: float | None,
    debt: float | None,
    shares: float | None,
) -> dict[str, Any]:
    base_discount = float(base_scenario["discount_rate"])
    base_terminal = float(base_scenario["terminal_growth_rate"])
    discount_rates = [
        round(_clamp(base_discount + change, 0.05, 0.20), 4)
        for change in (-0.02, -0.01, 0, 0.01, 0.02)
    ]
    terminal_growth_rates = [
        round(_clamp(base_terminal + change, 0, 0.05), 4)
        for change in (-0.01, -0.005, 0, 0.005, 0.01)
    ]
    values = []
    for terminal_growth in terminal_growth_rates:
        row = []
        for discount_rate in discount_rates:
            bridge = _fcff_valuation_bridge(
                base_scenario.get("forecast") or [],
                discount_rate=discount_rate,
                terminal_growth=terminal_growth,
                cash=cash,
                debt=debt,
                shares=shares,
            )
            fair_value = bridge.get("fair_value_per_share")
            row.append(
                {
                    "fair_value": fair_value,
                    "upside": (
                        _ratio(fair_value - current_price, current_price)
                        if fair_value is not None and current_price
                        else None
                    ),
                }
            )
        values.append(row)
    return {
        "discount_rates": discount_rates,
        "terminal_growth_rates": terminal_growth_rates,
        "values": values,
    }


def _fade(start: float, target: float, year: int, years: int) -> float:
    if years <= 1:
        return target
    weight = (year - 1) / (years - 1)
    return start + (target - start) * weight


def _risk_analysis(data: dict[str, Any], history: pd.DataFrame, current_price) -> dict[str, Any]:
    financials = data["financial_history"]
    latest = financials[-1] if financials else {}
    close = history["Close"].dropna() if not history.empty and "Close" in history else pd.Series(dtype=float)
    returns = close.pct_change().dropna()
    volatility = float(returns.std() * math.sqrt(252)) if len(returns) > 1 else None
    drawdown = None
    if not close.empty:
        drawdown = float((close / close.cummax() - 1).min())
    debt_to_fcf = _ratio(latest.get("debt"), latest.get("free_cash_flow"))
    negative_fcf_years = sum((row.get("free_cash_flow") or 0) < 0 for row in financials)
    high_volatility = volatility is not None and volatility > 0.35
    severe_drawdown = drawdown is not None and drawdown < -0.40
    leverage_risk = debt_to_fcf is None or debt_to_fcf < 0 or debt_to_fcf > 4
    checks = [
        _risk_check("Financial leverage", leverage_risk, debt_to_fcf, "multiple"),
        _risk_check("Free cash flow consistency", negative_fcf_years > 1, negative_fcf_years, "years"),
        _risk_check("Annualized volatility", high_volatility, volatility, "percent"),
        _risk_check("Five-year maximum drawdown", severe_drawdown, drawdown, "percent"),
    ]
    score = round(100 * sum(check["status"] == "risk" for check in checks) / len(checks))
    return {
        "score": score,
        "label": (
            "unknown"
            if volatility is None or drawdown is None
            else "high" if score >= 60 else "moderate" if score >= 30 else "low"
        ),
        "complete": volatility is not None and drawdown is not None,
        "checks": checks,
        "metrics": {
            "annualized_volatility": volatility,
            "maximum_drawdown": drawdown,
            "debt_to_fcf": debt_to_fcf,
        },
    }


def _add_market_context(data: dict[str, Any], current_price: float | None) -> None:
    history = data["financial_history"]
    latest = history[-1] if history else {}
    shares = latest.get("diluted_shares")
    market_cap = data["company"].get("market_cap")
    if market_cap is None and current_price is not None and shares is not None:
        market_cap = current_price * shares
        data["company"]["market_cap"] = market_cap

    derived = {
        "price_to_earnings": _ratio(
            current_price,
            latest.get("diluted_eps"),
        ),
        "price_to_free_cash_flow": _ratio(
            market_cap,
            latest.get("free_cash_flow"),
        ),
        "free_cash_flow_yield": _ratio(
            latest.get("free_cash_flow"),
            market_cap,
        ),
        "price_to_sales": _ratio(market_cap, latest.get("revenue")),
        "debt_to_equity": _ratio(latest.get("debt"), latest.get("equity")),
        "current_ratio": _ratio(
            latest.get("current_assets"),
            latest.get("current_liabilities"),
        ),
    }
    data["ratios"] = {
        **{key: value for key, value in derived.items() if value is not None},
        **data["ratios"],
    }


def _source_label(fundamentals_provider, price_provider) -> str:
    fundamentals_source = getattr(
        fundamentals_provider,
        "source_name",
        fundamentals_provider.__class__.__name__,
    )
    price_source = getattr(price_provider, "name", price_provider.__class__.__name__)
    return f"{fundamentals_source} (financials); {str(price_source).title()} (prices)"


def _annual_rows(value: object) -> list[dict]:
    rows = [dict(row) for row in list(value or []) if isinstance(row, dict)]
    annual = [row for row in rows if row.get("timeframe") in {None, "annual"}]
    return sorted(annual, key=lambda row: _period(row) or "")


def _period(row: dict) -> str | None:
    return row.get("period_end") or row.get("filing_date")


def _number(row: dict, *keys: str) -> float | None:
    for key in keys:
        value = _finite(row.get(key))
        if value is not None:
            return value
    return None


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _sum_numbers(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _ratio(numerator, denominator) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


def _growth(old, new) -> float | None:
    if old in {None, 0} or new is None:
        return None
    return (new - old) / abs(old)


def _cagr(values: list) -> float | None:
    present = [value for value in values if value is not None]
    if len(present) < 2 or present[0] <= 0 or present[-1] <= 0:
        return None
    return (present[-1] / present[0]) ** (1 / (len(present) - 1)) - 1


def _median(values: list) -> float | None:
    present = sorted(value for value in values if value is not None)
    if not present:
        return None
    middle = len(present) // 2
    if len(present) % 2:
        return float(present[middle])
    return float((present[middle - 1] + present[middle]) / 2)


def _range(values: list) -> float | None:
    present = [value for value in values if value is not None]
    return max(present) - min(present) if present else None


def _stable(values: list, tolerance: float) -> bool:
    value_range = _range(values)
    return value_range is not None and value_range <= tolerance


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _latest_price(history: pd.DataFrame) -> float | None:
    if history.empty or "Close" not in history:
        return None
    return _finite(history["Close"].dropna().iloc[-1]) if not history["Close"].dropna().empty else None


def _check(name: str, passed: bool, value, unit: str) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "value": value, "unit": unit}


def _risk_check(name: str, risky: bool, value, unit: str) -> dict[str, Any]:
    return {"name": name, "status": "risk" if risky else "acceptable", "value": value, "unit": unit}


def _data_warnings(data: dict[str, Any], current_price) -> list[str]:
    warnings = []
    years = len(data["financial_history"])
    if years < 5:
        warnings.append(f"Only {years} annual financial periods are available.")
    if current_price is None:
        warnings.append("Current market price is unavailable.")
    if not data["ratios"]:
        warnings.append(
            "Valuation multiples could not be derived from available SEC financials "
            "and price data."
        )
    return warnings


def _confidence(data: dict[str, Any], warnings: list[str]) -> str:
    if len(data["financial_history"]) >= 5 and not warnings:
        return "high"
    if len(data["financial_history"]) >= 3:
        return "medium"
    return "low"
