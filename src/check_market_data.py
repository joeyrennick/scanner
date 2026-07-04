import argparse

from scanner.data.market_data import check_market_data_connectivity


def main():
    parser = argparse.ArgumentParser(
        description="Check live Yahoo/yfinance connectivity with a small market-data download.",
    )
    parser.add_argument(
        "--ticker",
        default="SPY",
        help="Ticker to test against Yahoo Finance.",
    )
    parser.add_argument(
        "--period",
        default="5d",
        help="History period to request, such as 1d, 5d, or 1mo.",
    )

    args = parser.parse_args()

    try:
        result = check_market_data_connectivity(
            ticker=args.ticker,
            period=args.period,
        )
    except Exception as error:
        print(f"Market data check failed: {error}")
        raise SystemExit(1)

    print("Market data check passed")
    print(f"Ticker: {result.ticker}")
    print(f"Period: {result.period}")
    print(f"Rows: {result.rows}")
    print(f"First timestamp: {result.first_timestamp}")
    print(f"Last timestamp: {result.last_timestamp}")
    print(f"Elapsed seconds: {result.elapsed_seconds:.2f}")


if __name__ == "__main__":
    main()
