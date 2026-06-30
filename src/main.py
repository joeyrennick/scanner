from scanner.config import TICKERS_FILE, OUTPUT_FILE
from scanner.data.market_data import download_price_data
from scanner.indicators.moving_averages import add_moving_averages
from scanner.indicators.relative_strength import calculate_relative_strength
from scanner.scoring.score_engine import calculate_score
import pandas as pd

def load_tickers(filename):
    with open(filename, "r") as file:
        return [line.strip().upper() for line in file if line.strip()]

def analyze_ticker(ticker, spy_data):
    data = download_price_data(ticker)
    if data.empty:
        return None

    data = add_moving_averages(data)
    latest = data.iloc[-1]

    price = latest["Close"].item()
    ma20 = latest["MA20"].item()
    ma50 = latest["MA50"].item()
    ma200 = latest["MA200"].item()

    rs = calculate_relative_strength(data, spy_data)
    score = calculate_score(price, ma20, ma50, ma200, rs)

    return {
        "Ticker": ticker,
        "Price": round(price,2),
        "20MA": round(ma20,2),
        "50MA": round(ma50,2),
        "200MA": round(ma200,2),
        "Relative Strength": round(rs,2),
        "Score": score
    }

def main():
    tickers = load_tickers(TICKERS_FILE)
    spy = download_price_data("SPY")
    results = []

    for ticker in tickers:
        print(f"Analyzing {ticker}...")
        r = analyze_ticker(ticker, spy)
        if r:
            results.append(r)

    df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
    print(df)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
