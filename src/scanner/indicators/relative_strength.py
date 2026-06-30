from scanner.config import LOOKBACK_DAYS

def percent_change(data):
    close = data["Close"]
    old = close.iloc[-LOOKBACK_DAYS].item()
    new = close.iloc[-1].item()
    return ((new-old)/old)*100

def calculate_relative_strength(stock_data, benchmark_data):
    return percent_change(stock_data) - percent_change(benchmark_data)
