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
            or SQLiteSecretStore(settings.market_data_cache_path).get_secret(
                MASSIVE_API_KEY_SECRET
            )
        )
        self.name = provider_name

    def download_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        if not self.api_key:
            raise RuntimeError(
                "MASSIVE_API_KEY is required when market_data_provider=massive"
            )

        start_date, end_date = _date_range_for_period(period)
        massive_ticker = _to_massive_ticker(ticker)
        url = (
            f"{self.base_url}/v2/aggs/ticker/{quote(massive_ticker)}/range/"
            f"1/day/{start_date.isoformat()}/{end_date.isoformat()}"
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


def _date_range_for_period(period: str) -> tuple[date, date]:
    end_date = pd.Timestamp.today().date()

    if period == "max":
        return date(1970, 1, 1), end_date

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


def _history_from_results(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    history = pd.DataFrame(results)
    history.index = pd.to_datetime(history["t"], unit="ms")
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
