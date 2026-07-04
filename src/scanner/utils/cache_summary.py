from __future__ import annotations

from scanner.data.cache import CacheOverview


def format_cache_summary(
    stats,
    overview: CacheOverview | None,
) -> str | None:
    if not stats:
        return None

    parts = [
        "Market data cache: "
        f"hits={stats.hits}, "
        f"misses={stats.misses}, "
        f"provider_calls={stats.provider_calls}, "
        f"rows_from_cache={stats.rows_loaded_from_cache}, "
        f"rows_fetched={stats.rows_fetched_from_provider}"
    ]

    if overview is not None:
        parts.append(
            "cache_overview: "
            f"provider={overview.provider or 'all'}, "
            f"cached_tickers={overview.cached_tickers}, "
            f"cached_bars={overview.cached_bars}, "
            f"earliest_bar={_format_value(overview.earliest_bar_date)}, "
            f"latest_bar={_format_value(overview.latest_bar_date)}, "
            f"last_successful_refresh={_format_value(overview.last_successful_refresh)}, "
            f"days_since_refresh={_format_value(overview.days_since_refresh)}"
        )

    return " | ".join(parts)


def _format_value(value) -> str:
    if value is None:
        return "n/a"

    return str(value)
