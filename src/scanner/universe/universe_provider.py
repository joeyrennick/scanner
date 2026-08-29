import pandas as pd
import requests
from io import StringIO
import logging
import re


logger = logging.getLogger("scanner")

# Validated against S&P Dow Jones Indices' June 29, 2026 constituent change.
# Alphabet (GOOGL) replaced Verizon (VZ). Keep this fallback deliberately
# explicit so an upstream HTML change cannot prevent scanner runs.
DJIA_FALLBACK_TICKERS = (
    "MMM", "GOOGL", "AMZN", "AXP", "AMGN", "AAPL", "BA", "CAT", "CVX", "CSCO",
    "KO", "DIS", "GS", "HD", "HON", "IBM", "JNJ", "JPM", "MCD", "MRK", "MSFT",
    "NKE", "NVDA", "PG", "CRM", "SHW", "TRV", "UNH", "V", "WMT",
)

NON_COMMON_FUNDAMENTAL_SECURITY_PATTERN = re.compile(
    r"\bpreferred\b|\bpreference\b|\bdepositary\s+shares?\b",
    re.IGNORECASE,
)


class UniverseProvider:
    SUPPORTED_UNIVERSES = ["sp500", "djia", "nasdaq", "nyse", "all"]

    def __init__(self):
        self._company_names: dict[str, str] = {}

    def get_sp500_tickers(self) -> list[str]:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))

        sp500 = tables[0]
        self._remember_company_names(sp500, "Symbol", "Security")
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
            table = self._flatten_columns(table)
            symbol_column = next(
                (column for column in ("Symbol", "Ticker") if column in table.columns),
                None,
            )
            if symbol_column:
                name_column = next(
                    (column for column in ("Company", "Company name") if column in table.columns),
                    None,
                )
                if name_column:
                    self._remember_company_names(table, symbol_column, name_column)
                tickers = self._normalize_tickers(table[symbol_column].tolist())
                if len(tickers) == 30:
                    return tickers

        logger.warning(
            "Could not find a validated 30-symbol DJIA table; using the "
            "built-in fallback constituent list"
        )
        return list(DJIA_FALLBACK_TICKERS)

    def get_nasdaq_tickers(self) -> list[str]:
        listed = self._read_nasdaq_trader_file(
            "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
        )
        listed = listed[
            (listed["Test Issue"] == "N")
            & (listed["ETF"] == "N")
            & (listed["Financial Status"] == "N")
        ]
        listed = self._filter_tradeable_common_symbols(listed, "Symbol")
        self._remember_company_names(listed, "Symbol", "Security Name")
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
        listed = self._filter_tradeable_common_symbols(listed, "ACT Symbol")
        self._remember_company_names(listed, "ACT Symbol", "Security Name")
        return self._normalize_tickers(listed["ACT Symbol"].tolist())

    def get_company_name(self, ticker: str) -> str | None:
        return self._company_names.get(self._normalize_ticker(ticker))

    def is_fundamental_common_equity(self, ticker: str) -> bool:
        security_name = self.get_company_name(ticker)
        return security_name is None or not NON_COMMON_FUNDAMENTAL_SECURITY_PATTERN.search(
            security_name
        )

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
            self._normalize_ticker(ticker)
            for ticker in tickers
            if str(ticker).strip()
        ]
        return self._dedupe_tickers(normalized)

    def _flatten_columns(self, table: pd.DataFrame) -> pd.DataFrame:
        flattened = table.copy()
        if isinstance(flattened.columns, pd.MultiIndex):
            flattened.columns = [
                next(
                    (
                        str(part).strip()
                        for part in reversed(column)
                        if str(part).strip() and not str(part).startswith("Unnamed")
                    ),
                    "",
                )
                for column in flattened.columns
            ]
        return flattened

    def _normalize_ticker(self, ticker: object) -> str:
        return str(ticker).strip().upper().replace(".", "-")

    def _remember_company_names(
        self,
        listed: pd.DataFrame,
        symbol_column: str,
        name_column: str,
    ) -> None:
        if symbol_column not in listed.columns or name_column not in listed.columns:
            return

        for symbol, name in zip(listed[symbol_column], listed[name_column]):
            normalized_symbol = self._normalize_ticker(symbol)
            normalized_name = str(name).strip()
            if normalized_symbol and normalized_name and normalized_name.lower() != "nan":
                self._company_names[normalized_symbol] = normalized_name

    def _dedupe_tickers(self, tickers: list[str]) -> list[str]:
        deduped = []
        seen = set()

        for ticker in tickers:
            if ticker in seen:
                continue

            seen.add(ticker)
            deduped.append(ticker)

        return deduped

    def _filter_tradeable_common_symbols(
        self,
        listed: pd.DataFrame,
        symbol_column: str,
    ) -> pd.DataFrame:
        filtered = listed.copy()

        if "Security Name" in filtered.columns:
            security_name = filtered["Security Name"].astype(str).str.lower()
            non_common_pattern = r"\bwarrants?\b|\bunits?\b|\brights?\b"
            filtered = filtered[
                ~security_name.str.contains(non_common_pattern, regex=True)
            ]

        symbol = filtered[symbol_column].astype(str).str.strip().str.upper()
        normalized_symbol = symbol.str.replace(".", "-", regex=False)
        suffix = normalized_symbol.str.split("-").str[-1]
        filtered = filtered[~suffix.isin(["W", "WS", "WT", "U", "R"])]

        return filtered
