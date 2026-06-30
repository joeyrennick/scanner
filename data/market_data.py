import yfinance as yf

def download_price_data(ticker, period="1y"):
    return yf.download(ticker, period=period, progress=False)
