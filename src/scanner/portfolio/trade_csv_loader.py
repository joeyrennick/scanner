import pandas as pd

from scanner.backtesting.trade import Trade


def load_trades_from_csv(trade_csv_path: str) -> list[Trade]:
    trades = pd.read_csv(trade_csv_path)
    required_columns = [
        "Ticker",
        "Entry Date",
        "Exit Date",
        "Entry Price",
        "Exit Price",
    ]
    missing_columns = [
        column for column in required_columns if column not in trades.columns
    ]

    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Trade CSV is missing required columns: {missing}")

    strategy_column = "Strategy" if "Strategy" in trades.columns else None

    loaded_trades = []
    for _, row in trades.iterrows():
        loaded_trades.append(
            Trade(
                ticker=row["Ticker"],
                strategy_name=row[strategy_column] if strategy_column else "Unknown",
                entry_date=pd.to_datetime(row["Entry Date"]).date(),
                exit_date=pd.to_datetime(row["Exit Date"]).date(),
                entry_price=float(row["Entry Price"]),
                exit_price=float(row["Exit Price"]),
            )
        )

    return loaded_trades
