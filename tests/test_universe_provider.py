import pandas as pd

from scanner.universe.universe_provider import DJIA_FALLBACK_TICKERS, UniverseProvider


def test_get_universe_tickers_combines_supported_universes(monkeypatch):
    provider = UniverseProvider()
    monkeypatch.setattr(provider, "get_sp500_tickers", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(
        provider,
        "get_djia_tickers",
        lambda: (_ for _ in ()).throw(AssertionError("all must not load DJIA")),
    )
    monkeypatch.setattr(provider, "get_nasdaq_tickers", lambda: ["NVDA"])
    monkeypatch.setattr(provider, "get_nyse_tickers", lambda: ["IBM"])

    assert provider.get_universe_tickers("all") == ["AAPL", "MSFT", "NVDA", "IBM"]


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


def test_identifies_common_equity_for_fundamental_valuation():
    provider = UniverseProvider()
    provider._company_names = {
        "FCNCA": "First Citizens BancShares, Inc. Class A Common Stock",
        "FCNCN": "First Citizens BancShares, Inc. Depositary Shares, each representing a 1/40th interest in Preferred Stock",
        "FCNCO": "First Citizens BancShares, Inc. 5.625% Non-Cumulative Perpetual Preferred Stock, Series C",
        "BABA": "Alibaba Group Holding Limited American Depositary Shares",
    }

    assert provider.is_fundamental_common_equity("FCNCA") is True
    assert provider.is_fundamental_common_equity("FCNCN") is False
    assert provider.is_fundamental_common_equity("FCNCO") is False
    assert provider.is_fundamental_common_equity("BABA") is False
    assert provider.is_fundamental_common_equity("UNKNOWN") is True


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


def test_djia_uses_validated_symbol_table(monkeypatch):
    provider = UniverseProvider()
    symbols = list(DJIA_FALLBACK_TICKERS)

    class FakeResponse:
        text = "html"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("scanner.universe.universe_provider.requests.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        "scanner.universe.universe_provider.pd.read_html",
        lambda _html: [pd.DataFrame({"Company": [f"Company {i}" for i in range(30)], "Symbol": symbols})],
    )

    assert provider.get_djia_tickers() == symbols


def test_djia_falls_back_when_external_table_has_no_symbols(monkeypatch, caplog):
    provider = UniverseProvider()

    class FakeResponse:
        text = "html"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("scanner.universe.universe_provider.requests.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        "scanner.universe.universe_provider.pd.read_html",
        lambda _html: [pd.DataFrame({"Company": ["Apple", "Microsoft"]})],
    )

    assert provider.get_djia_tickers() == list(DJIA_FALLBACK_TICKERS)
    assert len(set(DJIA_FALLBACK_TICKERS)) == 30
    assert "GOOGL" in DJIA_FALLBACK_TICKERS
    assert "VZ" not in DJIA_FALLBACK_TICKERS
    assert "using the built-in fallback" in caplog.text
