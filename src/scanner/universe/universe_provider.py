import pandas as pd
import requests
from io import StringIO


class UniverseProvider:
    SUPPORTED_UNIVERSES = ["sp500", "djia", "nasdaq", "nyse", "all"]

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

    def get_djia_tickers(self) -> list[str]:
        url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))

        for table in tables:
            if "Symbol" in table.columns:
                tickers = table["Symbol"].tolist()
                return self._normalize_tickers(tickers)

        raise ValueError("Could not find DJIA symbols table")

    def get_nasdaq_tickers(self) -> list[str]:
        listed = self._read_nasdaq_trader_file(
            "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
        )
        listed = listed[
            (listed["Test Issue"] == "N")
            & (listed["ETF"] == "N")
            & (listed["Financial Status"] == "N")
        ]
        return self._normalize_tickers(listed["Symbol"].tolist())

    def get_nyse_tickers(self) -> list[str]:
        listed = self._read_nasdaq_trader_file(
            "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
        )
        listed = listed[
            (listed["Exchange"] == "N")
            & (listed["Test Issue"] == "N")
            & (listed["ETF"] == "N")
        ]
        return self._normalize_tickers(listed["ACT Symbol"].tolist())

    def get_universe_tickers(self, universe: str) -> list[str]:
        universe = universe.lower()

        if universe == "sp500":
            return self.get_sp500_tickers()
        if universe == "djia":
            return self.get_djia_tickers()
        if universe == "nasdaq":
            return self.get_nasdaq_tickers()
        if universe == "nyse":
            return self.get_nyse_tickers()
        if universe == "all":
            return self._dedupe_tickers(
                self.get_sp500_tickers()
                + self.get_djia_tickers()
                + self.get_nasdaq_tickers()
                + self.get_nyse_tickers()
            )

        supported = ", ".join(self.SUPPORTED_UNIVERSES)
        raise ValueError(f"Unsupported universe: {universe}. Supported: {supported}")

    def _read_nasdaq_trader_file(self, url: str) -> pd.DataFrame:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        return pd.read_csv(StringIO(response.text), sep="|").iloc[:-1]

    def _normalize_tickers(self, tickers: list[str]) -> list[str]:
        normalized = [
            str(ticker).strip().upper().replace(".", "-")
            for ticker in tickers
            if str(ticker).strip()
        ]
        return self._dedupe_tickers(normalized)

    def _dedupe_tickers(self, tickers: list[str]) -> list[str]:
        deduped = []
        seen = set()

        for ticker in tickers:
            if ticker in seen:
                continue

            seen.add(ticker)
            deduped.append(ticker)

        return deduped
