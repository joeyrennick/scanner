import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import quote

import pandas as pd
import requests

from scanner.config.settings import settings
from scanner.data.providers.base import MarketDataProvider
from scanner.security.secret_store import SQLiteSecretStore


MASSIVE_API_KEY_SECRET = "massive_api_key"


class MassiveMarketDataProvider(MarketDataProvider):
    name: str = "massive"
    base_url: str = "https://api.massive.com"

    def __init__(self, api_key: str | None = None, provider_name: str = "massive"):
        self.api_key = (
            api_key
            or os.environ.get("MASSIVE_API_KEY")
            or os.environ.get("POLYGON_API_KEY")
            or SQLiteSecretStore(settings.credential_database_path).get_secret(
                MASSIVE_API_KEY_SECRET
            )
        )
        self.name = provider_name

    def download_price_data(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        if not self.api_key:
            raise RuntimeError(
                "MASSIVE_API_KEY is required when market_data_provider=massive"
            )

        start_date, end_date = _date_range_for_period(period)
        multiplier, timespan = _aggregate_range_for_interval(interval)
        massive_ticker = _to_massive_ticker(ticker)
        url = (
            f"{self.base_url}/v2/aggs/ticker/{quote(massive_ticker)}/range/"
            f"{multiplier}/{timespan}/{start_date.isoformat()}/{end_date.isoformat()}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") == "ERROR":
            message = payload.get("error") or payload.get("message") or "Massive API error"
            raise RuntimeError(message)

        return _history_from_results(payload.get("results") or [])

    def download_price_data_batch(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        if not tickers:
            return {}

        max_workers = max(
            1,
            min(
                len(tickers),
                int(getattr(settings, "massive_batch_workers", 10)),
            ),
        )
        results: dict[str, pd.DataFrame] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.download_price_data,
                    ticker=ticker,
                    period=period,
                ): ticker
                for ticker in tickers
            }

            for future in as_completed(futures):
                ticker = futures[future]
                results[ticker] = future.result()

        return {ticker: results.get(ticker, pd.DataFrame()) for ticker in tickers}

    def download_company_profiles_batch(self, tickers: list[str]) -> dict[str, dict[str, str]]:
        if not self.api_key:
            raise RuntimeError(
                "MASSIVE_API_KEY is required when market_data_provider=massive"
            )

        unique_tickers = list(dict.fromkeys(tickers))
        max_workers = max(1, min(len(unique_tickers), int(settings.massive_batch_workers)))
        profiles: dict[str, dict[str, str]] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._download_company_profile, ticker): ticker
                for ticker in unique_tickers
            }
            for future in as_completed(futures):
                ticker = futures[future]
                profiles[ticker] = future.result()

        return profiles

    def _download_company_profile(self, ticker: str) -> dict[str, str]:
        result = self.download_company_details(ticker)
        return {
            "name": str(result.get("name") or ""),
            "sector": _sector_from_sic(result.get("sic_code")),
        }

    def download_company_details(self, ticker: str) -> dict:
        self._require_api_key()
        massive_ticker = _to_massive_ticker(ticker)
        response = requests.get(
            f"{self.base_url}/v3/reference/tickers/{quote(massive_ticker)}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("results") or {}

    def download_fundamental_data(self, ticker: str) -> dict[str, object]:
        self._require_api_key()
        massive_ticker = _to_massive_ticker(ticker)
        statement_params = {
            "ticker": massive_ticker,
            "timeframe": "annual",
            "order": "desc",
            "sort": "period_end",
            "limit": 10,
        }
        endpoints = {
            "income_statements": "/stocks/financials/v1/income-statements",
            "balance_sheets": "/stocks/financials/v1/balance-sheets",
            "cash_flow_statements": "/stocks/financials/v1/cash-flow-statements",
            "ratios": "/stocks/financials/v1/ratios",
        }
        data: dict[str, object] = {
            "profile": self.download_company_details(massive_ticker),
        }

        for name, endpoint in endpoints.items():
            params = {"ticker": massive_ticker, "limit": 10}
            if name != "ratios":
                params = statement_params.copy()
            data[name] = self._download_results(endpoint, params)

        return data

    def _download_results(self, endpoint: str, params: dict) -> list[dict]:
        response = requests.get(
            f"{self.base_url}{endpoint}",
            params=params,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        if getattr(response, "status_code", None) == 403:
            raise RuntimeError(
                "Massive fundamentals are not enabled for this API key. "
                "Add the Financials & Ratios entitlement or configure an eligible plan."
            )
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") == "ERROR":
            message = payload.get("error") or payload.get("message") or "Massive API error"
            raise RuntimeError(message)

        return payload.get("results") or []

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "MASSIVE_API_KEY is required when market_data_provider=massive"
            )


def _date_range_for_period(period: str) -> tuple[date, date]:
    end_date = pd.Timestamp.today().date()

    if period == "max":
        return date(1970, 1, 1), end_date

    if period == "ytd":
        return date(end_date.year, 1, 1), end_date

    match = re.fullmatch(r"(\d+)(d|w|mo|y)", period)

    if not match:
        return (
            (pd.Timestamp(end_date) - pd.DateOffset(years=1)).date(),
            end_date,
        )

    quantity = int(match.group(1))
    unit = match.group(2)
    offsets = {
        "d": pd.DateOffset(days=quantity),
        "w": pd.DateOffset(weeks=quantity),
        "mo": pd.DateOffset(months=quantity),
        "y": pd.DateOffset(years=quantity),
    }

    return (pd.Timestamp(end_date) - offsets[unit]).date(), end_date


def _aggregate_range_for_interval(interval: str) -> tuple[int, str]:
    ranges = {
        "5m": (5, "minute"),
        "15m": (15, "minute"),
        "1d": (1, "day"),
    }
    aggregate_range = ranges.get(interval)

    if aggregate_range is None:
        supported = ", ".join(ranges)
        raise ValueError(
            f"Unsupported market data interval: {interval}. Supported: {supported}"
        )

    return aggregate_range


def _history_from_results(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    history = pd.DataFrame(results)
    history.index = pd.to_datetime(history["t"], unit="ms", utc=True)
    history = history.sort_index()
    history = history.rename(
        columns={
            "o": "Open",
            "h": "High",
            "l": "Low",
            "c": "Close",
            "v": "Volume",
            "vw": "VWAP",
            "n": "Transactions",
        }
    )

    columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "VWAP",
        "Transactions",
    ]
    history = history[[column for column in columns if column in history.columns]]

    for column in history.columns:
        history[column] = pd.to_numeric(history[column], errors="coerce")

    history["Adj Close"] = history["Close"]
    history["Dividends"] = 0.0
    history["Stock Splits"] = 0.0

    return history


def _to_massive_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace("-", ".")


def _sector_from_sic(value: object) -> str:
    try:
        sic = int(str(value))
    except (TypeError, ValueError):
        return ""

    if 100 <= sic <= 999 or 2000 <= sic <= 2199:
        return "Consumer Staples"
    if 1000 <= sic <= 1299 or 1400 <= sic <= 1499 or 2400 <= sic <= 2699:
        return "Materials"
    if 1300 <= sic <= 1399 or 2900 <= sic <= 2999:
        return "Energy"
    if 2800 <= sic <= 2832:
        return "Materials"
    if 2833 <= sic <= 2836 or 3840 <= sic <= 3851 or 8000 <= sic <= 8099:
        return "Health Care"
    if 3570 <= sic <= 3579 or 3650 <= sic <= 3699 or 7370 <= sic <= 7379:
        return "Information Technology"
    if 4800 <= sic <= 4899:
        return "Communication Services"
    if 4900 <= sic <= 4999:
        return "Utilities"
    if 6500 <= sic <= 6599:
        return "Real Estate"
    if 6000 <= sic <= 6799:
        return "Financials"
    if 1500 <= sic <= 1799 or 3400 <= sic <= 3999 or 4500 <= sic <= 4799:
        return "Industrials"
    if 2200 <= sic <= 2399 or 2700 <= sic <= 2799 or 3100 <= sic <= 3299 or 5000 <= sic <= 5999 or 7000 <= sic <= 7999:
        return "Consumer Discretionary"
    return "Other"
