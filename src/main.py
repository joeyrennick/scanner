from scanner.config.settings import settings
from scanner.data.market_data import download_price_data
from scanner.indicators.atr import add_atr
from scanner.services.market_analyzer import MarketAnalyzer
from scanner.models.stock_analysis import StockAnalysis
from scanner.indicators.volume import add_volume_indicators
from scanner.indicators.moving_averages import add_moving_averages
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.scoring.score_engine import calculate_score_breakdown
from scanner.utils.logger import setup_logging
import pandas as pd

def load_tickers(filename):
    with open(filename, "r") as file:
        return [line.strip().upper() for line in file if line.strip()]

def main():
    logger = setup_logging()
    tickers = load_tickers(settings.tickers_file)
    spy = download_price_data(settings.benchmark_ticker)
    results = []
    analyzer = MarketAnalyzer()

    for ticker in tickers:
        logger.info(f"Analyzing {ticker}...")
        r = analyzer.analyze(ticker, spy)
        if r:
            results.append(r)

    df = pd.DataFrame([result.to_dict() for result in results]).sort_values(by="Score", ascending=False)
    print(df)
    df.to_csv(settings.output_file, index=False)
    logger.info(f"Saved results to {settings.output_file}")

if __name__ == "__main__":
    main()
