import os

import pytest

from scanner.utils.worker_tuner import (
    DEFAULT_TICKERS,
    benchmark_worker_counts,
    first_unstable_worker_count,
    parse_worker_counts,
    recommend_worker_count,
    results_dataframe,
)
from scanner.universe.universe_provider import UniverseProvider


def _parse_tickers(value: str) -> list[str]:
    tickers = [item.strip().upper() for item in value.split(",")]
    return [ticker for ticker in tickers if ticker]


def _select_tickers() -> list[str]:
    explicit = os.environ.get("WORKER_TICKERS")
    sample_size = int(os.environ.get("WORKER_SAMPLE_SIZE", "100"))

    if explicit:
        tickers = _parse_tickers(explicit)
    else:
        source = os.environ.get("WORKER_TICKER_SOURCE", "all").lower()

        if source == "default":
            tickers = list(DEFAULT_TICKERS)
        else:
            tickers = UniverseProvider().get_universe_tickers(source)

    if sample_size <= 0:
        raise ValueError("WORKER_SAMPLE_SIZE must be greater than zero")

    return tickers[:sample_size]


def test_live_worker_threshold_benchmark():
    if os.environ.get("RUN_LIVE_WORKER_TUNING") != "1":
        pytest.skip("Set RUN_LIVE_WORKER_TUNING=1 to run the live worker benchmark")

    worker_counts = parse_worker_counts(
        os.environ.get("WORKER_COUNTS", "1,2,4,8,12,16,20,24,32")
    )
    tickers = _select_tickers()
    period = os.environ.get("WORKER_PERIOD", "3mo")
    max_failure_rate = float(os.environ.get("WORKER_MAX_FAILURE_RATE", "0.05"))
    latency_spike_multiple = float(
        os.environ.get("WORKER_LATENCY_SPIKE_MULTIPLE", "2.0")
    )

    results = benchmark_worker_counts(
        worker_counts=worker_counts,
        tickers=tickers,
        period=period,
    )
    results_df = results_dataframe(results)
    recommendation = recommend_worker_count(
        results,
        max_failure_rate=max_failure_rate,
        latency_spike_multiple=latency_spike_multiple,
    )
    threshold = first_unstable_worker_count(
        results,
        max_failure_rate=max_failure_rate,
        latency_spike_multiple=latency_spike_multiple,
    )

    print(results_df.to_string(index=False))
    print()
    print(f"Recommended max_workers: {recommendation}")
    print(f"First unstable worker count: {threshold}")

    assert results_df.empty is False
    assert any(result.successes > 0 for result in results)
