from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import time

import pandas as pd

from scanner.data.market_data import download_price_data


DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "AVGO",
    "TSLA",
    "BRK-B",
    "JPM",
    "LLY",
    "V",
    "UNH",
    "XOM",
    "MA",
    "COST",
    "HD",
    "PG",
    "NFLX",
    "JNJ",
    "ABBV",
    "BAC",
    "KO",
    "PLTR",
    "AMD",
    "CRM",
    "ORCL",
    "CSCO",
    "WMT",
    "IBM",
    "GE",
    "MRK",
    "CVX",
    "MCD",
    "GS",
    "DIS",
    "NKE",
    "CAT",
    "AXP",
    "VZ",
]


@dataclass
class WorkerBenchmarkResult:
    workers: int
    attempts: int
    successes: int
    failures: int
    elapsed_seconds: float

    @property
    def failure_rate(self) -> float:
        if self.attempts == 0:
            return 0.0

        return self.failures / self.attempts

    @property
    def throughput_per_second(self) -> float:
        if self.elapsed_seconds == 0:
            return 0.0

        return self.successes / self.elapsed_seconds

    @property
    def average_seconds_per_attempt(self) -> float:
        if self.attempts == 0:
            return 0.0

        return self.elapsed_seconds / self.attempts

    def to_dict(self) -> dict:
        return {
            "Workers": self.workers,
            "Attempts": self.attempts,
            "Successes": self.successes,
            "Failures": self.failures,
            "Failure Rate": self.failure_rate,
            "Elapsed Seconds": self.elapsed_seconds,
            "Throughput / Second": self.throughput_per_second,
            "Avg Seconds / Attempt": self.average_seconds_per_attempt,
        }


def parse_worker_counts(value: str) -> list[int]:
    counts = []

    for item in value.split(","):
        count = int(item.strip())

        if count <= 0:
            raise ValueError("Worker counts must be greater than zero")

        counts.append(count)

    return counts


def benchmark_worker_count(
    workers: int,
    tickers: list[str],
    period: str = "3mo",
) -> WorkerBenchmarkResult:
    started_at = time.perf_counter()
    successes = 0
    failures = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_one, ticker, period): ticker
            for ticker in tickers
        }

        for future in as_completed(futures):
            if future.result():
                successes += 1
            else:
                failures += 1

    elapsed = time.perf_counter() - started_at
    return WorkerBenchmarkResult(
        workers=workers,
        attempts=len(tickers),
        successes=successes,
        failures=failures,
        elapsed_seconds=elapsed,
    )


def benchmark_worker_counts(
    worker_counts: list[int],
    tickers: list[str],
    period: str = "3mo",
) -> list[WorkerBenchmarkResult]:
    return [
        benchmark_worker_count(
            workers=workers,
            tickers=tickers,
            period=period,
        )
        for workers in worker_counts
    ]


def recommend_worker_count(
    results: list[WorkerBenchmarkResult],
    max_failure_rate: float = 0.05,
    latency_spike_multiple: float = 2.0,
) -> int | None:
    if not results:
        return None

    stable_results = []
    baseline_latency = results[0].average_seconds_per_attempt

    for result in results:
        failure_breakdown = result.failure_rate > max_failure_rate
        latency_breakdown = (
            baseline_latency > 0
            and result.average_seconds_per_attempt
            > baseline_latency * latency_spike_multiple
        )

        if failure_breakdown or latency_breakdown:
            break

        stable_results.append(result)

    if not stable_results:
        return None

    return stable_results[-1].workers


def first_unstable_worker_count(
    results: list[WorkerBenchmarkResult],
    max_failure_rate: float = 0.05,
    latency_spike_multiple: float = 2.0,
) -> int | None:
    if not results:
        return None

    baseline_latency = results[0].average_seconds_per_attempt

    for result in results:
        failure_breakdown = result.failure_rate > max_failure_rate
        latency_breakdown = (
            baseline_latency > 0
            and result.average_seconds_per_attempt
            > baseline_latency * latency_spike_multiple
        )

        if failure_breakdown or latency_breakdown:
            return result.workers

    return None


def results_dataframe(results: list[WorkerBenchmarkResult]) -> pd.DataFrame:
    return pd.DataFrame([result.to_dict() for result in results])


def _download_one(ticker: str, period: str) -> bool:
    try:
        history = download_price_data(ticker=ticker, period=period)
        return not history.empty
    except Exception:
        return False
