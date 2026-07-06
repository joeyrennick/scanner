import pandas as pd

from scanner.data.scanner_results import SQLiteScannerResultStore


def test_scanner_result_store_saves_and_loads_latest_run(tmp_path):
    store = SQLiteScannerResultStore(tmp_path / "market_data.sqlite")

    run_id = store.save_scan_results(
        pd.DataFrame(
            [
                {
                    "Ticker": "AAPL",
                    "Triggered Strategies": "Pullback",
                    "Composite Score": 88,
                    "Price": 200.0,
                }
            ]
        ),
        universe="sp500",
        market_data_provider="yahoo",
        history_period="6mo",
        output_file="output/watchlist.csv",
    )

    latest = store.latest_run()

    assert latest is not None
    assert latest.id == run_id
    assert latest.universe == "sp500"
    assert latest.rows == [
        {
            "Ticker": "AAPL",
            "Triggered Strategies": "Pullback",
            "Composite Score": 88,
            "Price": 200.0,
        }
    ]


def test_scanner_result_store_updates_enriched_rows_by_ticker(tmp_path):
    store = SQLiteScannerResultStore(tmp_path / "market_data.sqlite")
    run_id = store.save_scan_results(
        pd.DataFrame(
            [
                {"Ticker": "AAPL", "Price": 200.0, "Composite Score": 88},
                {"Ticker": "MSFT", "Price": 400.0, "Composite Score": 80},
            ]
        ),
        universe="sp500",
        market_data_provider="yahoo",
        history_period="6mo",
        output_file="output/watchlist.csv",
    )

    merged_rows = store.update_rows_by_ticker(
        run_id=run_id,
        rows=[
            {
                "Ticker": "AAPL",
                "Current Price": 212.5,
                "Price As Of": "2026-07-02",
                "5D Range": 5,
            }
        ],
    )

    assert merged_rows[0]["Price"] == 200.0
    assert merged_rows[0]["Current Price"] == 212.5
    assert merged_rows[0]["5D Range"] == 5
    assert merged_rows[1]["Ticker"] == "MSFT"
    assert store.latest_run().rows == merged_rows


def test_scanner_result_store_updates_and_resets_trade_levels(tmp_path):
    store = SQLiteScannerResultStore(tmp_path / "market_data.sqlite")
    run_id = store.save_scan_results(
        pd.DataFrame(
            [
                {
                    "Ticker": "AAPL",
                    "Price": 200.0,
                    "Entry Area": 200.0,
                    "Suggested Stop": 190.0,
                    "Target/Exit": 220.0,
                }
            ]
        ),
        universe="sp500",
        market_data_provider="yahoo",
        history_period="6mo",
        output_file="output/watchlist.csv",
    )

    updated = store.update_trade_levels(
        run_id=run_id,
        ticker="AAPL",
        entry_area=201.0,
        suggested_stop=191.0,
        target_exit=225.0,
    )

    assert updated["Entry Area"] == 201.0
    assert updated["Suggested Stop"] == 191.0
    assert updated["Target/Exit"] == 225.0
    assert updated["Trade Levels Edited"] == "YES"
    assert updated["Original Entry Area"] == 200.0

    reset = store.update_trade_levels(run_id=run_id, ticker="AAPL", reset=True)

    assert reset["Entry Area"] == 200.0
    assert reset["Suggested Stop"] == 190.0
    assert reset["Target/Exit"] == 220.0
    assert reset["Trade Levels Edited"] == "NO"
