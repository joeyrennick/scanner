from datetime import date

from scanner.backtesting.trade import Trade
from scanner.portfolio.portfolio import Portfolio
from scanner.portfolio.portfolio_simulator import PortfolioSimulator
from scanner.portfolio.position import Position


def make_trade(
    ticker: str,
    entry_date: date,
    exit_date: date,
    entry_price: float,
    exit_price: float,
) -> Trade:
    return Trade(
        ticker=ticker,
        strategy_name="Test Strategy",
        entry_date=entry_date,
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
    )


def test_position_calculates_values_and_profit_loss():
    trade = make_trade("AAA", date(2026, 1, 1), date(2026, 1, 5), 100, 110)
    position = Position(trade=trade, shares=10)

    assert position.entry_value == 1000
    assert position.exit_value == 1100
    assert position.profit_loss == 100
    assert position.return_percent == 10


def test_portfolio_opens_and_closes_position_with_cash_balance():
    portfolio = Portfolio(
        initial_cash=10_000,
        max_open_positions=2,
        position_size_percent=0.50,
    )
    trade = make_trade("AAA", date(2026, 1, 1), date(2026, 1, 5), 100, 110)

    position = portfolio.open_position(trade)
    closed_positions = portfolio.close_positions_on(date(2026, 1, 5))

    assert position is not None
    assert position.shares == 50
    assert portfolio.cash == 10_500
    assert closed_positions == [position]
    assert portfolio.open_positions == []
    assert portfolio.closed_positions == [position]


def test_portfolio_limits_maximum_open_positions():
    simulator = PortfolioSimulator(
        initial_cash=10_000,
        max_open_positions=1,
        position_size_percent=0.50,
    )
    trades = [
        make_trade("AAA", date(2026, 1, 1), date(2026, 1, 5), 100, 110),
        make_trade("BBB", date(2026, 1, 1), date(2026, 1, 5), 100, 120),
    ]

    result = simulator.run(trades)

    assert len(result.positions) == 1
    assert result.skipped_trades == 1
    assert result.final_equity == 10_500


def test_portfolio_uses_available_cash_for_position_sizing():
    portfolio = Portfolio(
        initial_cash=1_000,
        max_open_positions=3,
        position_size_percent=0.60,
    )
    first_trade = make_trade("AAA", date(2026, 1, 1), date(2026, 1, 5), 100, 100)
    second_trade = make_trade("BBB", date(2026, 1, 1), date(2026, 1, 5), 100, 100)

    first_position = portfolio.open_position(first_trade)
    second_position = portfolio.open_position(second_trade)

    assert first_position.shares == 6
    assert second_position.shares == 4
    assert portfolio.cash == 0


def test_simulator_tracks_equity_curve_and_performance_metrics():
    simulator = PortfolioSimulator(
        initial_cash=10_000,
        max_open_positions=1,
        position_size_percent=1.0,
    )
    trades = [
        make_trade("AAA", date(2026, 1, 1), date(2026, 1, 2), 100, 90),
        make_trade("BBB", date(2026, 1, 3), date(2027, 1, 3), 90, 108),
    ]

    result = simulator.run(trades)

    assert result.equity_curve["Equity"].tolist() == [10_000, 9_000, 9_000, 10_800]
    assert result.final_cash == 10_800
    assert result.final_equity == 10_800
    assert result.total_return_percent == 8.0
    assert result.max_drawdown_percent == -10.0
    assert round(result.cagr_percent, 2) == 7.96
    assert result.sharpe_ratio > 0
