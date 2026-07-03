from datetime import date

import pandas as pd
import pytest

from scanner.reports.daily_scanner_report import DailyScannerReport


def write_watchlist(tmp_path):
    watchlist_path = tmp_path / "watchlist.csv"
    pd.DataFrame(
        [
            {
                "Ticker": "AAA",
                "Triggered Strategies": "Pullback",
                "Composite Score": 120,
                "Technical Score": 100,
                "Strategy Score": 20,
                "Price": 50.0,
                "Stop 2ATR": 45.0,
                "ATR14": 2.5,
                "Relative Strength": 15,
                "Relative Volume": 1.2,
                "Pullback: Failed Checks": "None",
            },
            {
                "Ticker": "BBB",
                "Triggered Strategies": "Breakout",
                "Composite Score": 90,
                "Technical Score": 65,
                "Strategy Score": 25,
                "Price": 75.0,
                "Stop 2ATR": 68.0,
                "ATR14": 3.5,
                "Relative Strength": 10,
                "Relative Volume": 1.5,
                "Breakout: Failed Checks": "None",
            },
        ]
    ).to_csv(watchlist_path, index=False)
    return watchlist_path


def test_daily_scanner_report_summary_counts_candidates_and_strategies(tmp_path):
    report = DailyScannerReport(
        watchlist_path=write_watchlist(tmp_path),
        report_date=date(2026, 7, 3),
    )

    summary = report.summary()

    assert summary["Report Date"] == "2026-07-03"
    assert summary["Candidates"] == 2
    assert summary["Average Composite Score"] == 105
    assert summary["Pullback Candidates"] == 1
    assert summary["Breakout Candidates"] == 1


def test_daily_scanner_report_writes_html_and_archives_watchlist(tmp_path):
    report = DailyScannerReport(
        watchlist_path=write_watchlist(tmp_path),
        report_date=date(2026, 7, 3),
    )
    report_path = tmp_path / "daily_scanner_report.html"
    output_dir = tmp_path / "daily_reports"

    report.generate_html_report(report_path)
    archive_path = report.archive_watchlist(output_dir)

    html = report_path.read_text(encoding="utf-8")
    assert "Daily Scanner Report" in html
    assert "Watchlist Candidates" in html
    assert "Pullback: Failed Checks" in html
    assert archive_path.name == "watchlist_2026-07-03.csv"
    assert archive_path.exists()


def test_daily_scanner_report_includes_manual_trade_checklist(tmp_path):
    report = DailyScannerReport(
        watchlist_path=write_watchlist(tmp_path),
        report_date=date(2026, 7, 3),
        account_size=100_000,
        risk_per_trade_percent=1,
        suggested_hold_days=7,
        reward_risk_multiple=2,
    )
    report_path = tmp_path / "daily_scanner_report.html"

    checklist = report.manual_trade_checklist()
    report.generate_html_report(report_path)

    html = report_path.read_text(encoding="utf-8")
    first_row = checklist[checklist["Ticker"] == "AAA"].iloc[0]
    assert first_row["Entry Area"] == 50.0
    assert first_row["Suggested Stop"] == 45.0
    assert first_row["Risk / Share"] == 5.0
    assert first_row["Suggested Exit"] == 60.0
    assert first_row["Reward/Risk"] == 2
    assert first_row["Suggested Hold Time"] == "7 trading days"
    assert first_row["Risk Budget"] == 1000
    assert first_row["Position Size Estimate"] == 200
    assert first_row["Estimated Position Value"] == 10_000
    assert "Manual Trade Checklist" in html
    assert "Suggested Exit" in html
    assert "Suggested Hold Time" in html
    assert "Notes" in html


def test_daily_scanner_report_includes_portfolio_context(tmp_path):
    equity_curve_path = tmp_path / "equity_curve.csv"
    portfolio_report_path = tmp_path / "portfolio_report.html"
    portfolio_report_path.write_text("<html></html>", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "Date": "2026-01-01",
                "Cash": 5000,
                "Open Value": 5000,
                "Equity": 10_000,
                "Open Positions": 1,
            },
            {
                "Date": "2026-07-03",
                "Cash": 12_000,
                "Open Value": 0,
                "Equity": 12_000,
                "Open Positions": 0,
            },
        ]
    ).to_csv(equity_curve_path, index=False)
    report = DailyScannerReport(
        watchlist_path=write_watchlist(tmp_path),
        report_date=date(2026, 7, 3),
        portfolio_equity_curve_path=equity_curve_path,
        portfolio_report_path=portfolio_report_path,
    )
    report_dir = tmp_path / "daily_reports"
    report_path = report_dir / "daily_scanner_report.html"

    report.generate_html_report(report_path)

    html = report_path.read_text(encoding="utf-8")
    assert "Portfolio/Risk Context" in html
    assert "Total Return" in html
    assert "20.00" in html
    assert 'href="../portfolio_report.html"' in html


def test_daily_scanner_report_rejects_invalid_equity_curve(tmp_path):
    equity_curve_path = tmp_path / "equity_curve.csv"
    pd.DataFrame([{"Date": "2026-01-01", "Cash": 10_000}]).to_csv(
        equity_curve_path,
        index=False,
    )
    report = DailyScannerReport(
        watchlist_path=write_watchlist(tmp_path),
        report_date=date(2026, 7, 3),
        portfolio_equity_curve_path=equity_curve_path,
    )

    with pytest.raises(ValueError, match="Equity"):
        report.generate_html_report(tmp_path / "daily_scanner_report.html")


def test_daily_scanner_report_rejects_invalid_trade_checklist_inputs(tmp_path):
    with pytest.raises(ValueError, match="account_size"):
        DailyScannerReport(
            watchlist_path=write_watchlist(tmp_path),
            report_date=date(2026, 7, 3),
            account_size=0,
            risk_per_trade_percent=1,
        )

    with pytest.raises(ValueError, match="risk_per_trade_percent"):
        DailyScannerReport(
            watchlist_path=write_watchlist(tmp_path),
            report_date=date(2026, 7, 3),
            account_size=100_000,
            risk_per_trade_percent=0,
        )

    with pytest.raises(ValueError, match="suggested_hold_days"):
        DailyScannerReport(
            watchlist_path=write_watchlist(tmp_path),
            report_date=date(2026, 7, 3),
            suggested_hold_days=0,
        )

    with pytest.raises(ValueError, match="reward_risk_multiple"):
        DailyScannerReport(
            watchlist_path=write_watchlist(tmp_path),
            report_date=date(2026, 7, 3),
            reward_risk_multiple=0,
        )


def test_daily_scanner_report_requires_ticker_column(tmp_path):
    watchlist_path = tmp_path / "watchlist.csv"
    pd.DataFrame([{"Symbol": "AAA"}]).to_csv(watchlist_path, index=False)

    with pytest.raises(ValueError, match="Ticker"):
        DailyScannerReport(
            watchlist_path=watchlist_path,
            report_date=date(2026, 7, 3),
        )
