from scanner.config.settings import settings

def percent_change(data):
    close = data["Close"]
    old = close.iloc[-settings.indicators.relative_strength_lookback_days].item()
    new = close.iloc[-1].item()
    return ((new-old)/old)*100

def calculate_relative_strength(stock_data, benchmark_data):
    return percent_change(stock_data) - percent_change(benchmark_data)
