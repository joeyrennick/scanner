from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import pandas as pd

from scanner.config.settings import settings
from scanner.data.market_data import download_price_data
from scanner.services.market_analyzer import MarketAnalyzer
from scanner.universe.universe_provider import UniverseProvider
from scanner.strategies.strategy_category import StrategyCategory
from scanner.utils.logger import setup_logging


def analyze_one(ticker: str, benchmark_data):
    analyzer = MarketAnalyzer()
    result = analyzer.analyze(ticker, benchmark_data)
    return ticker, result


def main():
    logger = setup_logging()
    start = time.perf_counter()

    tickers = UniverseProvider().get_sp500_tickers()
    benchmark_data = download_price_data(settings.benchmark_ticker)

    results = []
    skipped = []

    logger.info(f"Loaded {len(tickers)} tickers")
    logger.info(f"Starting scan with {settings.max_workers} workers")

    with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
        futures = {
            executor.submit(analyze_one, ticker, benchmark_data): ticker
            for ticker in tickers
        }

        completed = 0

        for future in as_completed(futures):
            completed += 1
            ticker = futures[future]

            try:
                _, result = future.result()
                results.append(result)
                logger.info(f"[{completed}/{len(tickers)}] Finished {ticker}")

            except Exception as e:
                skipped.append((ticker, str(e)))
                logger.warning(f"[{completed}/{len(tickers)}] Skipping {ticker}: {e}")


    trade_candidates = [
        result
        for result in results
        if any(
            strategy.triggered and strategy.category == StrategyCategory.ENTRY
            for strategy in result.strategy_results
        )
    ]

    if trade_candidates:
        df = pd.DataFrame([result.to_dict() for result in trade_candidates])
        df = df.sort_values(by="Composite Score", ascending=False)
    else:
        logger.info("No trade candidates found.")
        df = pd.DataFrame()

    print(df)

    df.to_csv(settings.output_file, index=False)

    elapsed = time.perf_counter() - start

    logger.info("=" * 50)
    logger.info(f"Total tickers: {len(tickers)}")
    logger.info(f"Successfully analyzed: {len(results)}")
    logger.info(f"Trade candidates: {len(trade_candidates)}")
    logger.info(f"Skipped: {len(skipped)}")
    logger.info(f"Scan completed in {elapsed:.2f} seconds")

    if skipped:
        logger.info("Skipped tickers:")
        for ticker, reason in skipped:
            logger.info(f"  - {ticker}: {reason}")


if __name__ == "__main__":
    main()