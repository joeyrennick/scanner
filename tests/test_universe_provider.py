import pandas as pd

from scanner.universe.universe_provider import UniverseProvider


def test_get_universe_tickers_combines_supported_universes(monkeypatch):
    provider = UniverseProvider()
    monkeypatch.setattr(provider, "get_sp500_tickers", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(provider, "get_djia_tickers", lambda: ["AAPL", "V"])
    monkeypatch.setattr(provider, "get_nasdaq_tickers", lambda: ["NVDA"])
    monkeypatch.setattr(provider, "get_nyse_tickers", lambda: ["IBM"])

    assert provider.get_universe_tickers("all") == ["AAPL", "MSFT", "V", "NVDA", "IBM"]


def test_get_universe_tickers_routes_named_universe(monkeypatch):
    provider = UniverseProvider()
    monkeypatch.setattr(provider, "get_nasdaq_tickers", lambda: ["NVDA", "AMD"])

    assert provider.get_universe_tickers("nasdaq") == ["NVDA", "AMD"]


def test_get_universe_tickers_rejects_unsupported_universe():
    provider = UniverseProvider()

    try:
        provider.get_universe_tickers("unsupported")
    except ValueError as error:
        assert "Unsupported universe" in str(error)
    else:
        raise AssertionError("Expected unsupported universe to raise ValueError")


def test_normalize_tickers_dedupes_and_converts_dot_symbols():
    provider = UniverseProvider()

    assert provider._normalize_tickers(["brk.b", " AAPL ", "AAPL", ""]) == [
        "BRK-B",
        "AAPL",
    ]


def test_remembers_company_names_by_normalized_ticker():
    provider = UniverseProvider()
    provider._remember_company_names(
        pd.DataFrame(
            {
                "Symbol": ["AAPL", "BRK.B"],
                "Security": ["Apple Inc.", "Berkshire Hathaway Inc."],
            }
        ),
        "Symbol",
        "Security",
    )

    assert provider.get_company_name("aapl") == "Apple Inc."
    assert provider.get_company_name("BRK-B") == "Berkshire Hathaway Inc."
    assert provider.get_company_name("UNKNOWN") is None


def test_filter_tradeable_common_symbols_removes_warrants_units_and_rights():
    provider = UniverseProvider()
    listed = pd.DataFrame(
        {
            "Symbol": ["AAPL", "RZLVW", "SAAQ", "XYZU", "ABCR", "MSFT"],
            "Security Name": [
                "Apple Inc. Common Stock",
                "Rezolve AI Warrants",
                "SAAQ Units",
                "XYZ Units",
                "ABC Rights",
                "Microsoft Corporation Common Stock",
            ],
        }
    )

    filtered = provider._filter_tradeable_common_symbols(listed, "Symbol")

    assert filtered["Symbol"].tolist() == ["AAPL", "MSFT"]
