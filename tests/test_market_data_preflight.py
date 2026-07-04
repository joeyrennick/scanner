import sys

import pytest

import backtest
import main


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


def test_main_preflight_flag_exits_before_scan(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--preflight-market-data"])
    monkeypatch.setattr(main, "setup_logging", lambda: DummyLogger())
    monkeypatch.setattr(
        main,
        "check_market_data_connectivity",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        main,
        "download_price_data",
        lambda *args, **kwargs: pytest.fail("download_price_data should not be called"),
    )

    with pytest.raises(SystemExit) as excinfo:
        main.main()

    assert excinfo.value.code == 1


def test_backtest_preflight_flag_exits_before_backtest(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["backtest.py", "--ticker", "AAPL", "--preflight-market-data"],
    )
    monkeypatch.setattr(
        backtest,
        "check_market_data_connectivity",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        backtest.StrategyRegistry,
        "get",
        lambda *args, **kwargs: pytest.fail(
            "StrategyRegistry should not be used when preflight fails"
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        backtest.main()

    assert excinfo.value.code == 2
