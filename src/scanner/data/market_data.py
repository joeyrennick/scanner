from dataclasses import dataclass
from functools import lru_cache
import random
import time

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from yfinance._http import new_session


@dataclass(frozen=True)
class MarketDataConnectivityResult:
    ticker: str
    period: str
    rows: int
    elapsed_seconds: float
    first_timestamp: str | None
    last_timestamp: str | None


RETRYABLE_ERROR_PATTERNS = (
    "Too Many Requests",
    "Rate limited",
    "rate limit",
    "429",
)
MAX_DOWNLOAD_ATTEMPTS = 4
BASE_RETRY_DELAY_SECONDS = 1.5


@lru_cache(maxsize=1)
def get_market_data_session():
    return new_session()


def download_price_data(ticker, period="1y") -> pd.DataFrame:
    last_error = None

    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            return yf.download(
                ticker,
                period=period,
                progress=True,
                session=get_market_data_session(),
            )
        except Exception as error:
            if not _should_retry(error) or attempt == MAX_DOWNLOAD_ATTEMPTS:
                raise

            last_error = error
            delay_seconds = BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
            delay_seconds += random.uniform(0, 0.5)
            time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError("Failed to download market data")


def check_market_data_connectivity(
    ticker: str = "SPY",
    period: str = "5d",
) -> MarketDataConnectivityResult:
    started_at = time.perf_counter()
    history = download_price_data(ticker=ticker, period=period)
    elapsed_seconds = time.perf_counter() - started_at

    if history.empty:
        raise RuntimeError(
            f"No rows returned for {ticker} over period {period}; Yahoo connectivity is not healthy"
        )

    first_timestamp = history.index[0].isoformat() if len(history.index) else None
    last_timestamp = history.index[-1].isoformat() if len(history.index) else None

    return MarketDataConnectivityResult(
        ticker=ticker,
        period=period,
        rows=len(history),
        elapsed_seconds=elapsed_seconds,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
    )


def _should_retry(error: Exception) -> bool:
    if isinstance(error, YFRateLimitError):
        return True

    message = str(error)
    return any(pattern in message for pattern in RETRYABLE_ERROR_PATTERNS)
