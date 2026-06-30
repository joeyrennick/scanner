from scanner.config import TICKERS_FILE, OUTPUT_FILE
from scanner.data.market_data import download_price_data
from scanner.indicators.atr import add_atr
from scanner.models.stock_analysis import StockAnalysis
from scanner.indicators.volume import add_volume_indicators
from scanner.indicators.moving_averages import add_moving_averages
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.scoring.score_engine import calculate_score_breakdown
import pandas as pd

def load_tickers(filename):
    with open(filename, "r") as file:
        return [line.strip().upper() for line in file if line.strip()]

def analyze_ticker(ticker, spy_data):
    data = download_price_data(ticker)
    if data.empty:
        return None

    data = add_moving_averages(data)
    data = add_atr(data)
    data = add_volume_indicators(data)
    latest = data.iloc[-1]

    price = latest["Close"].item()
    ma20 = latest["MA20"].item()
    ma50 = latest["MA50"].item()
    ma200 = latest["MA200"].item()
    atr14 = latest["ATR14"].item()
    avg_volume_20 = latest["AvgVolume20"].item()
    relative_volume = latest["RelativeVolume"].item()

    rs = calculate_relative_strength(data, spy_data)
    score_breakdown = calculate_score_breakdown(
            price=price,
            ma20=ma20,
            ma50=ma50,
            ma200=ma200,
            relative_strength=rs,
            relative_volume=relative_volume,
            atr14=atr14,
        )

    return StockAnalysis(
        ticker=ticker,
        price=price,
        ma20=ma20,
        ma50=ma50,
        ma200=ma200,
        relative_strength=rs,
        score_breakdown=score_breakdown,
        atr14=atr14,
        avg_volume_20=avg_volume_20,
        relative_volume=relative_volume
    )

def main():
    tickers = load_tickers(TICKERS_FILE)
    spy = download_price_data("SPY")
    results = []

    for ticker in tickers:
        print(f"Analyzing {ticker}...")
        r = analyze_ticker(ticker, spy)
        if r:
            results.append(r)

    df = pd.DataFrame([result.to_dict() for result in results]).sort_values(by="Score", ascending=False)
    print(df)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
