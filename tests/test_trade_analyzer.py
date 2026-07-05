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


def create_bucket_analyzer():
    trades = pd.DataFrame(
        [
            {
                "Ticker": "AAA",
                "Strategy": "Pullback Strategy",
                "Entry Date": "2026-01-05",
                "Exit Date": "2026-01-10",
                "Composite Score": 45,
                "Relative Strength": -2,
                "Relative Volume": 0.7,
                "Return %": 5.0,
            },
            {
                "Ticker": "BBB",
                "Strategy": "Pullback Strategy",
                "Entry Date": "2026-01-12",
                "Exit Date": "2026-01-17",
                "Composite Score": 72,
                "Relative Strength": 12,
                "Relative Volume": 1.2,
                "Return %": -2.0,
            },
            {
                "Ticker": "CCC",
                "Strategy": "Breakout Strategy",
                "Entry Date": "2026-02-03",
                "Exit Date": "2026-02-08",
                "Composite Score": 91,
                "Relative Strength": 24,
                "Relative Volume": 2.4,
                "Return %": 4.0,
            },
            {
                "Ticker": "DDD",
                "Strategy": "Breakout Strategy",
                "Entry Date": "2026-02-10",
                "Exit Date": "2026-02-15",
                "Composite Score": 66,
                "Relative Strength": 7,
                "Relative Volume": 0.95,
                "Return %": 2.0,
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


def test_strategy_summary_groups_trades_by_strategy():
    summary = create_bucket_analyzer().strategy_summary()

    breakout = summary[summary["Strategy"] == "Breakout Strategy"].iloc[0]
    pullback = summary[summary["Strategy"] == "Pullback Strategy"].iloc[0]

    assert breakout["Trades"] == 2
    assert breakout["Average Return"] == 3.0
    assert breakout["Win Rate"] == 100.0
    assert pullback["Trades"] == 2
    assert pullback["Average Return"] == 1.5
    assert pullback["Profit Factor"] == 2.5


def test_analyzer_bucket_summaries_group_metric_ranges():
    analyzer = create_bucket_analyzer()

    composite = analyzer.composite_score_bucket_summary()
    relative_strength = analyzer.relative_strength_bucket_summary()
    relative_volume = analyzer.relative_volume_bucket_summary()

    assert composite["Composite Score Bucket"].tolist() == [
        "<= 50",
        "> 50 to <= 70",
        "> 70 to <= 85",
        "> 85",
    ]
    assert composite["Trades"].tolist() == [1, 1, 1, 1]
    assert relative_strength["Relative Strength Bucket"].tolist() == [
        "<= 0",
        "> 0 to <= 10",
        "> 10 to <= 20",
        "> 20",
    ]
    assert relative_strength["Trades"].tolist() == [1, 1, 1, 1]
    assert relative_volume["Relative Volume Bucket"].tolist() == [
        "<= 0.8",
        "> 0.8 to <= 1",
        "> 1 to <= 1.5",
        "> 2",
    ]
    assert relative_volume["Trades"].tolist() == [1, 1, 1, 1]


def test_bucket_summaries_only_include_available_columns():
    analyzer = create_analyzer()

    assert analyzer.bucket_summaries() == {}


def test_export_bucket_summaries_writes_available_csv_files(tmp_path):
    output_dir = tmp_path / "buckets"

    exports = create_bucket_analyzer().export_bucket_summaries(output_dir)

    assert {path.name for path in exports} == {
        "strategy_summary.csv",
        "composite_score_buckets.csv",
        "relative_strength_buckets.csv",
        "relative_volume_buckets.csv",
    }
    exported = pd.read_csv(output_dir / "composite_score_buckets.csv")
    assert list(exported.columns) == [
        "Composite Score Bucket",
        "Trades",
        "Win Rate",
        "Average Return",
        "Median Return",
        "Best Trade",
        "Worst Trade",
        "Profit Factor",
    ]


def test_plot_return_distribution_writes_png(tmp_path):
    output_path = tmp_path / "return_distribution.png"

    create_analyzer().plot_return_distribution(
        output_path,
        bins=[-math.inf, 0, 3, math.inf],
    )

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"\x89PNG")


def test_generate_html_report_writes_report_and_chart(tmp_path):
    output_path = tmp_path / "trade_report.html"
    chart_path = tmp_path / "trade_report_return_distribution.png"

    create_analyzer().generate_html_report(output_path, min_trades=1, top=2)

    html = output_path.read_text(encoding="utf-8")
    assert "Trade Analysis Report" in html
    assert "Top Tickers by Average Return" in html
    assert "Return Distribution" in html
    assert "trade_report_return_distribution.png" in html
    assert chart_path.exists()
    assert chart_path.read_bytes().startswith(b"\x89PNG")


def test_generate_html_report_includes_available_bucket_summaries(tmp_path):
    output_path = tmp_path / "trade_report.html"

    create_bucket_analyzer().generate_html_report(output_path, min_trades=1, top=2)

    html = output_path.read_text(encoding="utf-8")
    assert "Strategy Summary" in html
    assert "Composite Score Buckets" in html
    assert "Relative Strength Buckets" in html
    assert "Relative Volume Buckets" in html


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
