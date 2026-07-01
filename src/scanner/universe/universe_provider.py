import pandas as pd
import requests
from io import StringIO


class UniverseProvider:

    def get_sp500_tickers(self) -> list[str]:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))

        sp500 = tables[0]
        tickers = sp500["Symbol"].tolist()

        return [ticker.replace(".", "-") for ticker in tickers]