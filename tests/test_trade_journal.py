from datetime import date

import pytest

from scanner.journal.trade_journal import TradeJournal


def test_trade_journal_adds_and_persists_open_trade(tmp_path):
    journal_path = tmp_path / "trade_journal.csv"
    journal = TradeJournal(journal_path)

    trade_id = journal.add_trade(
        ticker="aapl",
        entry_date=date(2026, 7, 3),
        entry_price=100,
        shares=10,
        strategy="Pullback",
        suggested_stop=95,
        suggested_exit=110,
        notes="Manual entry",
    )

    reloaded = TradeJournal(journal_path)
    trades = reloaded.review_dataframe()

    assert trade_id
    assert trades.iloc[0]["Ticker"] == "AAPL"
    assert trades.iloc[0]["Status"] == "OPEN"
    assert trades.iloc[0]["Entry Value"] == 1000


def test_trade_journal_closes_trade_and_calculates_results(tmp_path):
    journal = TradeJournal(tmp_path / "trade_journal.csv")
    trade_id = journal.add_trade(
        ticker="AAPL",
        entry_date=date(2026, 7, 3),
        entry_price=100,
        shares=10,
    )

    journal.close_trade(
        trade_id=trade_id,
        exit_date=date(2026, 7, 10),
        exit_price=112,
        exit_notes="Hit target",
    )

    trades = journal.review_dataframe()
    summary = journal.summary()

    assert trades.iloc[0]["Status"] == "CLOSED"
    assert trades.iloc[0]["Exit Value"] == 1120
    assert trades.iloc[0]["Profit/Loss"] == 120
    assert trades.iloc[0]["Return %"] == 12
    assert trades.iloc[0]["Holding Days"] == 7
    assert summary["Closed Trades"] == 1
    assert summary["Win Rate"] == 100
    assert summary["Total Profit/Loss"] == 120


def test_trade_journal_closes_trade_after_reload(tmp_path):
    journal_path = tmp_path / "trade_journal.csv"
    journal = TradeJournal(journal_path)
    trade_id = journal.add_trade(
        ticker="AAPL",
        entry_date=date(2026, 7, 3),
        entry_price=100,
        shares=10,
    )
    reloaded = TradeJournal(journal_path)

    reloaded.close_trade(
        trade_id=trade_id,
        exit_date=date(2026, 7, 10),
        exit_price=112,
    )

    trades = TradeJournal(journal_path).review_dataframe()
    assert trades.iloc[0]["Status"] == "CLOSED"
    assert trades.iloc[0]["Profit/Loss"] == 120


def test_trade_journal_summary_handles_open_only_journal(tmp_path):
    journal = TradeJournal(tmp_path / "trade_journal.csv")
    journal.add_trade(
        ticker="AAPL",
        entry_date=date(2026, 7, 3),
        entry_price=100,
        shares=10,
    )

    summary = journal.summary()

    assert summary["Total Trades"] == 1
    assert summary["Open Trades"] == 1
    assert summary["Closed Trades"] == 0
    assert summary["Total Profit/Loss"] == 0


def test_trade_journal_validates_trade_inputs(tmp_path):
    journal = TradeJournal(tmp_path / "trade_journal.csv")

    with pytest.raises(ValueError, match="entry_price"):
        journal.add_trade(
            ticker="AAPL",
            entry_date=date(2026, 7, 3),
            entry_price=0,
            shares=10,
        )

    with pytest.raises(ValueError, match="shares"):
        journal.add_trade(
            ticker="AAPL",
            entry_date=date(2026, 7, 3),
            entry_price=100,
            shares=0,
        )


def test_trade_journal_validates_close_inputs(tmp_path):
    journal = TradeJournal(tmp_path / "trade_journal.csv")
    trade_id = journal.add_trade(
        ticker="AAPL",
        entry_date=date(2026, 7, 3),
        entry_price=100,
        shares=10,
    )

    with pytest.raises(ValueError, match="exit_price"):
        journal.close_trade(
            trade_id=trade_id,
            exit_date=date(2026, 7, 10),
            exit_price=0,
        )

    with pytest.raises(ValueError, match="not found"):
        journal.close_trade(
            trade_id="MISSING",
            exit_date=date(2026, 7, 10),
            exit_price=100,
        )


def test_trade_journal_rejects_closing_trade_twice(tmp_path):
    journal = TradeJournal(tmp_path / "trade_journal.csv")
    trade_id = journal.add_trade(
        ticker="AAPL",
        entry_date=date(2026, 7, 3),
        entry_price=100,
        shares=10,
    )

    journal.close_trade(
        trade_id=trade_id,
        exit_date=date(2026, 7, 10),
        exit_price=112,
    )

    with pytest.raises(ValueError, match="already closed"):
        journal.close_trade(
            trade_id=trade_id,
            exit_date=date(2026, 7, 11),
            exit_price=113,
        )


def test_trade_journal_generates_html_report(tmp_path):
    journal = TradeJournal(tmp_path / "trade_journal.csv")
    trade_id = journal.add_trade(
        ticker="AAPL",
        entry_date=date(2026, 7, 3),
        entry_price=100,
        shares=10,
    )
    journal.close_trade(
        trade_id=trade_id,
        exit_date=date(2026, 7, 10),
        exit_price=112,
    )
    report_path = tmp_path / "trade_journal_report.html"

    journal.generate_html_report(report_path)

    html = report_path.read_text(encoding="utf-8")
    assert "Manual Trade Journal" in html
    assert "Total Profit/Loss" in html
    assert "AAPL" in html
