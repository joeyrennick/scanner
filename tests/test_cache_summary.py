from datetime import datetime

from scanner.data.cache import CacheOverview
from scanner.data.providers.cached import MarketDataCacheStats
from scanner.utils.cache_summary import format_cache_summary


def test_format_cache_summary_includes_refresh_staleness():
    stats = MarketDataCacheStats(
        hits=10,
        misses=2,
        provider_calls=1,
        rows_loaded_from_cache=500,
        rows_fetched_from_provider=100,
    )
    overview = CacheOverview(
        provider="yahoo",
        cached_tickers=25,
        cached_bars=1250,
        earliest_bar_date=datetime(2026, 1, 1).date(),
        latest_bar_date=datetime(2026, 7, 2).date(),
        last_successful_refresh=datetime(2026, 7, 4, 10, 30),
        days_since_refresh=0,
    )

    summary = format_cache_summary(stats, overview)

    assert "hits=10" in summary
    assert "cached_tickers=25" in summary
    assert "latest_bar=2026-07-02" in summary
    assert "last_successful_refresh=2026-07-04 10:30:00" in summary
    assert "days_since_refresh=0" in summary
