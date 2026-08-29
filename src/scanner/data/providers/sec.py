from __future__ import annotations

from copy import deepcopy
from datetime import date
import math
import os
from threading import Lock
import time
from typing import Any

import requests

from scanner.fundamentals.sec_cache import SECFundamentalsCache


SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_DEFAULT_USER_AGENT = "Swing Scanner joe.rennick@servicenow.com"
_TICKER_MAP_CACHE: dict[str, dict[str, dict[str, Any]]] = {}
_SEC_REQUEST_LOCK = Lock()
_SEC_LAST_REQUEST_AT = 0.0

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

US_GAAP_TAGS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": (
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "NetIncomeLoss",
        "ProfitLoss",
    ),
    "diluted_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "basic_shares": ("WeightedAverageNumberOfSharesOutstandingBasic",),
    "diluted_eps": (
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
        "EarningsPerShareBasic",
    ),
    "net_interest_income": (
        "InterestIncomeExpenseNet",
        "InterestIncomeExpenseAfterProvisionForLoanLoss",
    ),
    "noninterest_income": ("NoninterestIncome",),
    "cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "total_current_debt": ("ShortTermDebtCurrent", "DebtCurrent"),
    "short_term_borrowings": ("ShortTermBorrowings", "CommercialPaper"),
    "long_term_debt_current": ("LongTermDebtCurrent",),
    "long_term_debt": (
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtAndCapitalLeaseObligationsNoncurrent",
        "LongTermDebtNoncurrent",
    ),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "PartnersCapital",
    ),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capital_expenditures": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
}

IFRS_TAGS = {
    "revenue": ("Revenue",),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("ProfitLossFromOperatingActivities", "OperatingProfitLoss"),
    "net_income": ("ProfitLoss",),
    "diluted_shares": ("WeightedAverageNumberOfSharesOutstandingDiluted",),
    "basic_shares": ("WeightedAverageNumberOfSharesOutstandingBasic",),
    "diluted_eps": ("DilutedEarningsLossPerShare", "BasicEarningsLossPerShare"),
    "net_interest_income": (),
    "noninterest_income": (),
    "cash": ("CashAndCashEquivalents",),
    "current_assets": ("CurrentAssets",),
    "current_liabilities": ("CurrentLiabilities",),
    "total_current_debt": ("BorrowingsCurrent",),
    "short_term_borrowings": ("ShorttermBorrowings",),
    "long_term_debt_current": ("CurrentPortionOfNoncurrentBorrowings",),
    "long_term_debt": ("BorrowingsNoncurrent", "NoncurrentBorrowings"),
    "equity": ("Equity",),
    "operating_cash_flow": ("CashFlowsFromUsedInOperatingActivities",),
    "capital_expenditures": (
        "PurchaseOfPropertyPlantAndEquipment",
        "PaymentsToAcquirePropertyPlantAndEquipment",
    ),
}


class SECFundamentalsProvider:
    """Download and normalize public-company fundamentals from SEC EDGAR."""

    source_name = "SEC EDGAR"

    def __init__(
        self,
        user_agent: str | None = None,
        timeout: int = 30,
        *,
        cache_path: str | None = None,
        cache_ttl_hours: int = 24,
        include_submissions: bool = True,
        max_requests_per_second: float = 8,
    ):
        self.user_agent = (
            user_agent or os.environ.get("SEC_USER_AGENT") or SEC_DEFAULT_USER_AGENT
        ).strip()
        self.timeout = timeout
        self.cache = (
            SECFundamentalsCache(cache_path, ttl_hours=cache_ttl_hours)
            if cache_path
            else None
        )
        self.include_submissions = include_submissions
        self.minimum_request_interval = (
            1 / max_requests_per_second if max_requests_per_second > 0 else 0
        )
        self._ticker_map: dict[str, dict[str, Any]] | None = None

    def download_fundamental_data(self, ticker: str) -> dict[str, object]:
        normalized_ticker = ticker.strip().upper()
        company = self._resolve_company(normalized_ticker)
        cik = f"{int(company['cik_str']):010d}"
        cached = self.cache.get(normalized_ticker) if self.cache else None
        if cached is None:
            company_facts = self._get_json(SEC_COMPANY_FACTS_URL.format(cik=cik))
            data = self._normalize_company_facts(
                normalized_ticker,
                cik,
                company,
                company_facts,
            )
            _normalize_diluted_share_units(data)
            if self.cache:
                self.cache.set(normalized_ticker, data)
        else:
            data = deepcopy(cached)
            if _normalize_diluted_share_units(data) and self.cache:
                self.cache.set(normalized_ticker, data)

        if self.include_submissions:
            submissions = self._get_json(SEC_SUBMISSIONS_URL.format(cik=cik))
            profile = dict(data.get("profile") or {})
            profile.update(
                {
                    "name": submissions.get("name") or profile.get("name") or "",
                    "description": submissions.get("description") or "",
                    "sic_description": submissions.get("sicDescription") or "",
                    "homepage_url": submissions.get("website") or "",
                }
            )
            data["profile"] = profile
        return data

    def prepare(self, ticker: str) -> None:
        """Load the shared SEC ticker-to-CIK map before concurrent requests."""
        self._resolve_company(ticker.strip().upper())

    def _normalize_company_facts(
        self,
        normalized_ticker: str,
        cik: str,
        company: dict[str, Any],
        company_facts: dict[str, Any],
    ) -> dict[str, object]:

        facts = company_facts.get("facts") or {}
        if "us-gaap" in facts:
            taxonomy = "us-gaap"
            tags = US_GAAP_TAGS
        elif "ifrs-full" in facts:
            taxonomy = "ifrs-full"
            tags = IFRS_TAGS
        else:
            raise RuntimeError(
                f"SEC EDGAR has no standardized US-GAAP or IFRS company facts for "
                f"{normalized_ticker}."
            )

        taxonomy_facts = facts[taxonomy]
        income = self._income_rows(taxonomy_facts, tags)
        balances = self._balance_rows(taxonomy_facts, tags)
        cash_flows = self._cash_flow_rows(taxonomy_facts, tags)

        if not income and not balances and not cash_flows:
            raise RuntimeError(
                f"SEC EDGAR returned no annual financial statements for {normalized_ticker}."
            )

        return {
            "profile": {
                "ticker": normalized_ticker,
                "name": company_facts.get("entityName")
                or company.get("title")
                or normalized_ticker,
                "description": "",
                "sic_description": "",
                "homepage_url": "",
                "cik": cik,
            },
            "income_statements": income,
            "balance_sheets": balances,
            "cash_flow_statements": cash_flows,
            "ratios": [],
        }

    def _resolve_company(self, ticker: str) -> dict[str, Any]:
        if self._ticker_map is None:
            self._ticker_map = _TICKER_MAP_CACHE.get(self.user_agent)
            if self._ticker_map is None:
                payload = self._get_json(SEC_COMPANY_TICKERS_URL)
                ticker_map: dict[str, dict[str, Any]] = {}
                for value in payload.values():
                    if not isinstance(value, dict) or not value.get("ticker"):
                        continue
                    sec_ticker = str(value["ticker"]).upper()
                    ticker_map[sec_ticker] = value
                    ticker_map[sec_ticker.replace("-", ".")] = value
                if not ticker_map:
                    raise RuntimeError("SEC EDGAR returned an empty company ticker list.")
                _TICKER_MAP_CACHE[self.user_agent] = ticker_map
                self._ticker_map = ticker_map

        aliases = (ticker, ticker.replace(".", "-"), ticker.replace("-", "."))
        for alias in aliases:
            company = self._ticker_map.get(alias)
            if company is not None:
                return company
        raise RuntimeError(
            f"Ticker {ticker} was not found in the SEC company ticker list."
        )

    def _get_json(self, url: str) -> dict[str, Any]:
        try:
            _wait_for_sec_request_slot(self.minimum_request_interval)
            response = requests.get(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            if response.status_code == 403:
                raise RuntimeError(
                    "SEC EDGAR rejected the automated request. Set SEC_USER_AGENT "
                    "to a declared organization and contact email."
                )
            if response.status_code == 429:
                raise RuntimeError(
                    "SEC EDGAR rate-limited the request. Wait briefly and try again."
                )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise RuntimeError(f"SEC EDGAR request failed: {error}") from error
        except ValueError as error:
            raise RuntimeError("SEC EDGAR returned an invalid JSON response.") from error

        if not isinstance(payload, dict):
            raise RuntimeError("SEC EDGAR returned an unexpected response format.")
        return payload

    def _income_rows(self, facts: dict[str, Any], tags: dict[str, tuple[str, ...]]):
        revenue = _concept_series(
            facts, tags["revenue"], ("USD",), duration=True
        )
        banking_revenue = _sum_series(
            _concept_series(
                facts, tags["net_interest_income"], ("USD",), duration=True
            ),
            _concept_series(
                facts, tags["noninterest_income"], ("USD",), duration=True
            ),
        )
        for period, value in banking_revenue.items():
            revenue.setdefault(period, value)

        diluted_shares = _concept_series(
            facts, tags["diluted_shares"], ("shares",), duration=True
        )
        basic_shares = _concept_series(
            facts, tags["basic_shares"], ("shares",), duration=True
        )
        for period, value in basic_shares.items():
            diluted_shares.setdefault(period, value)

        fields = {
            "revenue": revenue,
            "gross_profit": _concept_series(
                facts, tags["gross_profit"], ("USD",), duration=True
            ),
            "operating_income": _concept_series(
                facts, tags["operating_income"], ("USD",), duration=True
            ),
            "consolidated_net_income_loss": _concept_series(
                facts, tags["net_income"], ("USD",), duration=True
            ),
            "diluted_shares_outstanding": diluted_shares,
            "diluted_earnings_per_share": _concept_series(
                facts,
                tags["diluted_eps"],
                ("USD/shares", "USD / shares"),
                duration=True,
            ),
        }
        return _rows_from_series(fields)

    def _balance_rows(self, facts: dict[str, Any], tags: dict[str, tuple[str, ...]]):
        total_current_debt = _concept_series(
            facts, tags["total_current_debt"], ("USD",), duration=False
        )
        current_debt_components = _sum_series(
            _concept_series(
                facts, tags["short_term_borrowings"], ("USD",), duration=False
            ),
            _concept_series(
                facts, tags["long_term_debt_current"], ("USD",), duration=False
            ),
        )
        for period, value in current_debt_components.items():
            total_current_debt.setdefault(period, value)

        fields = {
            "cash_and_equivalents": _concept_series(
                facts, tags["cash"], ("USD",), duration=False
            ),
            "total_current_assets": _concept_series(
                facts, tags["current_assets"], ("USD",), duration=False
            ),
            "total_current_liabilities": _concept_series(
                facts, tags["current_liabilities"], ("USD",), duration=False
            ),
            "debt_current": total_current_debt,
            "long_term_debt_and_capital_lease_obligations": _concept_series(
                facts, tags["long_term_debt"], ("USD",), duration=False
            ),
            "total_equity": _concept_series(
                facts, tags["equity"], ("USD",), duration=False
            ),
        }
        return _rows_from_series(fields)

    def _cash_flow_rows(self, facts: dict[str, Any], tags: dict[str, tuple[str, ...]]):
        capex = _concept_series(
            facts, tags["capital_expenditures"], ("USD",), duration=True
        )
        capex = {period: -abs(value) for period, value in capex.items()}
        fields = {
            "net_cash_from_operating_activities": _concept_series(
                facts, tags["operating_cash_flow"], ("USD",), duration=True
            ),
            "purchase_of_property_plant_and_equipment": capex,
        }
        return _rows_from_series(fields)


def _concept_series(
    facts: dict[str, Any],
    tags: tuple[str, ...],
    preferred_units: tuple[str, ...],
    *,
    duration: bool,
) -> dict[str, float]:
    combined: dict[str, float] = {}
    for tag in tags:
        concept = facts.get(tag)
        if not isinstance(concept, dict):
            continue
        observations = _observations(concept, preferred_units)
        candidates: dict[str, tuple[str, float]] = {}
        for observation in observations:
            if observation.get("form") not in ANNUAL_FORMS:
                continue
            period_end = observation.get("end")
            value = observation.get("val")
            if not period_end or not isinstance(value, (int, float)):
                continue
            if duration and not _is_annual_duration(observation):
                continue
            rank = str(observation.get("filed") or "")
            current = candidates.get(period_end)
            if current is None or rank >= current[0]:
                candidates[period_end] = (rank, float(value))
        for period_end, (_rank, value) in candidates.items():
            combined.setdefault(period_end, value)
    return combined


def _observations(
    concept: dict[str, Any], preferred_units: tuple[str, ...]
) -> list[dict[str, Any]]:
    units = concept.get("units") or {}
    for unit in preferred_units:
        observations = units.get(unit)
        if isinstance(observations, list):
            return [item for item in observations if isinstance(item, dict)]
    return []


def _is_annual_duration(observation: dict[str, Any]) -> bool:
    start = observation.get("start")
    end = observation.get("end")
    if not start or not end:
        return False
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return False
    return 300 <= days <= 430


def _sum_series(*series: dict[str, float]) -> dict[str, float]:
    periods = set().union(*(values.keys() for values in series))
    return {
        period: sum(values[period] for values in series if period in values)
        for period in periods
    }


def _rows_from_series(fields: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    periods = sorted(set().union(*(values.keys() for values in fields.values())))
    rows = []
    for period in periods:
        row: dict[str, Any] = {
            "timeframe": "annual",
            "period_end": period,
            "fiscal_year": int(period[:4]),
        }
        row.update(
            {
                field: values[period]
                for field, values in fields.items()
                if period in values
            }
        )
        rows.append(row)
    return rows


def _normalize_diluted_share_units(data: dict[str, object]) -> bool:
    """Expand SEC share facts reported in thousands or millions into shares."""
    changed = False
    for row in data.get("income_statements") or []:
        if not isinstance(row, dict):
            continue
        if row.get("diluted_shares_scale_factor") is not None:
            continue
        shares = _finite_number(row.get("diluted_shares_outstanding"))
        net_income = _finite_number(row.get("consolidated_net_income_loss"))
        diluted_eps = _finite_number(row.get("diluted_earnings_per_share"))
        scale = _share_scale_factor(shares, net_income, diluted_eps)
        if shares is None or scale == 1:
            continue
        row["diluted_shares_reported"] = shares
        row["diluted_shares_scale_factor"] = scale
        row["diluted_shares_outstanding"] = shares * scale
        changed = True
    return changed


def _share_scale_factor(
    shares: float | None,
    net_income: float | None,
    diluted_eps: float | None,
) -> int:
    if (
        shares is None
        or shares <= 0
        or net_income is None
        or net_income == 0
        or diluted_eps is None
        or diluted_eps == 0
        or net_income * diluted_eps <= 0
    ):
        return 1

    implied_shares = abs(net_income / diluted_eps)
    scales = (1, 1_000, 1_000_000, 1_000_000_000)
    best_scale = min(
        scales,
        key=lambda candidate: abs(
            math.log10((shares * candidate) / implied_shares)
        ),
    )
    consistency_ratio = shares * best_scale / implied_shares
    return best_scale if 0.5 <= consistency_ratio <= 2 else 1


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _wait_for_sec_request_slot(minimum_interval: float) -> None:
    global _SEC_LAST_REQUEST_AT

    if minimum_interval <= 0:
        return
    with _SEC_REQUEST_LOCK:
        elapsed = time.monotonic() - _SEC_LAST_REQUEST_AT
        if elapsed < minimum_interval:
            time.sleep(minimum_interval - elapsed)
        _SEC_LAST_REQUEST_AT = time.monotonic()
