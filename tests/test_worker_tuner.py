import pytest

from scanner.utils.worker_tuner import (
    WorkerBenchmarkResult,
    first_unstable_worker_count,
    parse_worker_counts,
    recommend_worker_count,
    results_dataframe,
)


def test_parse_worker_counts():
    assert parse_worker_counts("1, 2,4") == [1, 2, 4]


def test_parse_worker_counts_rejects_non_positive_values():
    with pytest.raises(ValueError, match="greater than zero"):
        parse_worker_counts("1,0,2")


def test_recommend_worker_count_stops_before_failure_breakdown():
    results = [
        WorkerBenchmarkResult(1, attempts=10, successes=10, failures=0, elapsed_seconds=10),
        WorkerBenchmarkResult(2, attempts=10, successes=10, failures=0, elapsed_seconds=8),
        WorkerBenchmarkResult(4, attempts=10, successes=8, failures=2, elapsed_seconds=7),
    ]

    recommendation = recommend_worker_count(results, max_failure_rate=0.05)

    assert recommendation == 2


def test_recommend_worker_count_stops_before_latency_breakdown():
    results = [
        WorkerBenchmarkResult(1, attempts=10, successes=10, failures=0, elapsed_seconds=10),
        WorkerBenchmarkResult(2, attempts=10, successes=10, failures=0, elapsed_seconds=12),
        WorkerBenchmarkResult(4, attempts=10, successes=10, failures=0, elapsed_seconds=25),
    ]

    recommendation = recommend_worker_count(results, latency_spike_multiple=2.0)

    assert recommendation == 2


def test_first_unstable_worker_count_returns_first_failure_or_latency_breakdown():
    results = [
        WorkerBenchmarkResult(1, attempts=10, successes=10, failures=0, elapsed_seconds=10),
        WorkerBenchmarkResult(2, attempts=10, successes=10, failures=0, elapsed_seconds=12),
        WorkerBenchmarkResult(4, attempts=10, successes=8, failures=2, elapsed_seconds=7),
    ]

    threshold = first_unstable_worker_count(results, max_failure_rate=0.05)

    assert threshold == 4


def test_results_dataframe_contains_benchmark_columns():
    dataframe = results_dataframe(
        [
            WorkerBenchmarkResult(
                1,
                attempts=10,
                successes=9,
                failures=1,
                elapsed_seconds=5,
            )
        ]
    )

    assert dataframe.iloc[0]["Workers"] == 1
    assert dataframe.iloc[0]["Failure Rate"] == 0.1
    assert dataframe.iloc[0]["Throughput / Second"] == 1.8
