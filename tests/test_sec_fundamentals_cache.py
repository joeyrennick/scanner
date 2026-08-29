from scanner.fundamentals.sec_cache import SECFundamentalsCache


def test_sec_fundamentals_cache_round_trips_normalized_payload(tmp_path):
    cache = SECFundamentalsCache(tmp_path / "cache.sqlite", ttl_hours=24)
    payload = {
        "profile": {"ticker": "AAPL", "name": "Apple Inc."},
        "income_statements": [{"period_end": "2025-09-27", "revenue": 10}],
    }

    cache.set("aapl", payload)

    assert cache.get("AAPL") == payload
