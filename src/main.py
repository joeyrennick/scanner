from scanner.config.settings import settings
from scanner.data.market_data import download_price_data
from scanner.services.market_analyzer import MarketAnalyzer
from scanner.universe.universe_provider import UniverseProvider
from scanner.utils.logger import setup_logging
import pandas as pd


def main():
    logger = setup_logging()

    tickers = UniverseProvider().get_sp500_tickers()
    spy = download_price_data(settings.benchmark_ticker)

    results = []
    skipped = []

    analyzer = MarketAnalyzer()

    for ticker in tickers:
        logger.info(f"Analyzing {ticker}...")

        try:
            result = analyzer.analyze(ticker, spy)
            results.append(result)

        except Exception as e:
            logger.warning(f"Skipping {ticker}: {e}")
            skipped.append((ticker, str(e)))

    df = pd.DataFrame([result.to_dict() for result in results])
    df = df.sort_values(by="Score", ascending=False)

    print(df)

    df.to_csv(settings.output_file, index=False)

    logger.info("=" * 50)
    logger.info(f"Total tickers: {len(tickers)}")
    logger.info(f"Successfully analyzed: {len(results)}")
    logger.info(f"Skipped: {len(skipped)}")

    if skipped:
        logger.info("Skipped tickers:")
        for ticker, reason in skipped:
            logger.info(f"  - {ticker}: {reason}")


if __name__ == "__main__":
    main()