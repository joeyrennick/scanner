from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd


DEFAULT_ASSUMPTIONS = {
    "discount_rate": 0.10,
    "terminal_growth_rate": 0.025,
    "projection_years": 5,
}


class FundamentalAnalysisService:
    def __init__(self, provider):
        self.provider = provider

    def analyze(
        self,
        ticker: str,
        assumptions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ticker = ticker.strip().upper()
        raw = self.provider.download_fundamental_data(ticker)
        price_history = self.provider.download_price_data(ticker, period="5y")
        normalized = _normalize(raw)
        current_price = _latest_price(price_history)
        quality = _quality_analysis(normalized)
        risk = _risk_analysis(normalized, price_history, current_price)
        valuation = _valuation_analysis(
            normalized,
            current_price,
            assumptions or {},
        )
        warnings = _data_warnings(normalized, current_price)

        return {
            "schema_version": 1,
            "ticker": ticker,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Massive",
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
        net_income = _number(
            income,
            "net_income_loss_attributable_common_shareholders",
            "consolidated_net_income_loss",
        )
        history.append(
            {
                "period_end": period,
                "fiscal_year": income.get("fiscal_year") or balance.get("fiscal_year"),
                "revenue": revenue,
                "gross_profit": gross_profit,
                "operating_income": operating_income,
                "net_income": net_income,
                "operating_cash_flow": operating_cash,
                "capital_expenditures": capex,
                "free_cash_flow": free_cash_flow,
                "gross_margin": _ratio(gross_profit, revenue),
                "operating_margin": _ratio(operating_income, revenue),
                "cash_and_equivalents": _number(balance, "cash_and_equivalents"),
                "current_assets": _number(balance, "total_current_assets"),
                "current_liabilities": _number(balance, "total_current_liabilities"),
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
                "diluted_eps": _number(income, "diluted_earnings_per_share"),
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
    base_growth = _clamp(revenue_cagr if revenue_cagr is not None else 0.05, 0, 0.15)
    assumptions = {
        **DEFAULT_ASSUMPTIONS,
        "base_growth_rate": base_growth,
        "bear_growth_rate": max(-0.02, base_growth - 0.04),
        "bull_growth_rate": min(0.25, base_growth + 0.04),
        **{key: value for key, value in overrides.items() if value is not None},
    }
    scenarios = []

    for name in ("bear", "base", "bull"):
        growth = _finite(assumptions.get(f"{name}_growth_rate")) or 0
        value = _dcf_per_share(
            free_cash_flow=latest.get("free_cash_flow"),
            growth=growth,
            discount_rate=float(assumptions["discount_rate"]),
            terminal_growth=float(assumptions["terminal_growth_rate"]),
            years=int(assumptions["projection_years"]),
            cash=latest.get("cash_and_equivalents"),
            debt=latest.get("debt"),
            shares=latest.get("diluted_shares"),
        )
        upside = _ratio(value - current_price, current_price) if value is not None and current_price else None
        scenarios.append({"name": name, "growth_rate": growth, "fair_value": value, "upside": upside})

    base = next(item for item in scenarios if item["name"] == "base")
    upside = base["upside"]
    label = "unknown"
    if upside is not None:
        label = "undervalued" if upside >= 0.15 else "overvalued" if upside <= -0.15 else "fairly valued"

    return {
        "label": label,
        "confidence": "medium" if base["fair_value"] is not None else "low",
        "current_price": current_price,
        "margin_of_safety": upside,
        "assumptions": assumptions,
        "scenarios": scenarios,
        "multiples": data["ratios"],
    }


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
        "label": "high" if score >= 60 else "moderate" if score >= 30 else "low",
        "checks": checks,
        "metrics": {
            "annualized_volatility": volatility,
            "maximum_drawdown": drawdown,
            "debt_to_fcf": debt_to_fcf,
        },
    }


def _dcf_per_share(free_cash_flow, growth, discount_rate, terminal_growth, years, cash, debt, shares):
    values = [free_cash_flow, cash, debt, shares]
    if any(value is None for value in values) or free_cash_flow <= 0 or shares <= 0:
        return None
    if discount_rate <= terminal_growth or years <= 0:
        return None
    projected = free_cash_flow
    present_value = 0.0
    for year in range(1, years + 1):
        projected *= 1 + growth
        present_value += projected / ((1 + discount_rate) ** year)
    terminal_value = projected * (1 + terminal_growth) / (discount_rate - terminal_growth)
    equity_value = present_value + terminal_value / ((1 + discount_rate) ** years) + cash - debt
    return max(0.0, equity_value / shares)


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
        warnings.append("Provider ratios are unavailable for this ticker or subscription.")
    return warnings


def _confidence(data: dict[str, Any], warnings: list[str]) -> str:
    if len(data["financial_history"]) >= 5 and not warnings:
        return "high"
    if len(data["financial_history"]) >= 3:
        return "medium"
    return "low"
