import math

import pandas as pd

from scanner.analysis.trade_analyzer import TradeAnalyzer


def create_analyzer():
    trades = pd.DataFrame(
        [
            {
                "Ticker": "AAA",
                "Entry Date": "2026-01-05",
                "Exit Date": "2026-01-10",
                "Return %": 5.0,
            },
            {
                "Ticker": "AAA",
                "Entry Date": "2026-01-12",
                "Exit Date": "2026-01-17",
                "Return %": -2.0,
            },
            {
                "Ticker": "BBB",
                "Entry Date": "2026-02-03",
                "Exit Date": "2026-02-08",
                "Return %": 4.0,
            },
            {
                "Ticker": "BBB",
                "Entry Date": "2026-02-10",
                "Exit Date": "2026-02-15",
                "Return %": 2.0,
            },
            {
                "Ticker": "CCC",
                "Entry Date": "2026-02-11",
                "Exit Date": "2026-02-16",
                "Return %": -3.0,
            },
        ]
    )
    return TradeAnalyzer.from_dataframe(trades)


def test_summary_calculates_core_statistics():
    summary = create_analyzer().summary()

    assert summary["Total Trades"] == 5
    assert summary["Win Rate"] == 60.0
    assert summary["Average Return"] == 1.2
    assert summary["Average Winner"] == 11 / 3
    assert summary["Average Loser"] == -2.5
    assert summary["Best Trade"] == 5.0
    assert summary["Worst Trade"] == -3.0
    assert summary["Profit Factor"] == 2.2
    assert summary["Expectancy"] == 1.2


def test_ticker_rankings_sort_by_average_return_and_win_rate():
    analyzer = create_analyzer()

    by_average_return = analyzer.rank_tickers_by_average_return()
    by_win_rate = analyzer.rank_tickers_by_win_rate()

    assert by_average_return.iloc[0]["Ticker"] == "BBB"
    assert by_average_return.iloc[0]["Average Return"] == 3.0
    assert by_win_rate.iloc[0]["Ticker"] == "BBB"
    assert by_win_rate.iloc[0]["Win Rate"] == 100.0


def test_ticker_summary_respects_minimum_trade_count():
    summary = create_analyzer().ticker_summary(min_trades=2)

    assert set(summary["Ticker"]) == {"AAA", "BBB"}


def test_monthly_and_weekday_summaries_group_trades():
    analyzer = create_analyzer()

    monthly = analyzer.monthly_summary()
    weekday = analyzer.weekday_summary()

    january = monthly[monthly["Month"] == "2026-01"].iloc[0]
    assert january["Trades"] == 2
    assert january["Average Return"] == 1.5

    assert set(weekday["Weekday"]) == {"Monday", "Tuesday", "Wednesday"}


def test_streaks_use_exit_date_order():
    analyzer = create_analyzer()

    assert analyzer.longest_winning_streak() == 2
    assert analyzer.longest_losing_streak() == 1


def test_return_distribution_counts_all_trades():
    distribution = create_analyzer().return_distribution(bins=[-math.inf, 0, 3, math.inf])

    assert distribution["Trades"].tolist() == [2, 1, 2]
    assert distribution["Percent"].tolist() == [40.0, 20.0, 40.0]


def test_export_ticker_summary_writes_csv(tmp_path):
    output_path = tmp_path / "ticker_summary.csv"

    create_analyzer().export_ticker_summary(output_path)

    exported = pd.read_csv(output_path)
    assert list(exported.columns) == [
        "Ticker",
        "Trades",
        "Win Rate",
        "Average Return",
        "Median Return",
        "Best Trade",
        "Worst Trade",
        "Profit Factor",
    ]
    assert len(exported) == 3
