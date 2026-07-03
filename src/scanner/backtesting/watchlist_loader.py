import pandas as pd


def load_watchlist_tickers(
    watchlist_path: str,
    strategy_name: str,
    include_all: bool = False,
) -> list[str]:
    watchlist = pd.read_csv(watchlist_path)

    if "Ticker" not in watchlist.columns:
        raise ValueError("Watchlist CSV is missing required column: Ticker")

    if not include_all:
        strategy_column = strategy_name

        if strategy_column not in watchlist.columns:
            raise ValueError(
                f"Watchlist CSV is missing strategy column: {strategy_column}. "
                "Use --watchlist-all to backtest every watchlist ticker."
            )

        watchlist = watchlist[watchlist[strategy_column].astype(str).str.upper() == "YES"]

    tickers = []
    seen = set()

    for ticker in watchlist["Ticker"].dropna():
        normalized = str(ticker).strip().upper()

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        tickers.append(normalized)

    if not tickers:
        raise ValueError("Watchlist CSV does not contain any valid tickers to backtest")

    return tickers
