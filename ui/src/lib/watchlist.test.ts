import { describe, expect, it } from 'vitest';
import { candidateFromWatchlistRow, mergeWatchlistRows, rowMatchesStrategy } from './watchlist';

describe('watchlist display helpers', () => {
  it('maps existing scanner rows into display candidates', () => {
    const candidate = candidateFromWatchlistRow(
      {
        Ticker: 'AAPL',
        'Triggered Strategies': 'Pullback',
        'Composite Score': 82,
        Price: 211.43,
        'Stop 2ATR': 203.43,
        'Relative Strength': 12.345,
        'Relative Volume': 1.25,
        ATR14: 4.1
      },
      0,
      '2026-07-02'
    );

    expect(candidate).toMatchObject({
      ticker: 'AAPL',
      currentPrice: '$211.43',
      priceSource: 'Cached Close',
      targetExit: '$227.43',
      holdTime: '5 trading days'
    });
  });

  it('filters rows by strategy column or triggered strategy text', () => {
    expect(rowMatchesStrategy({ 'Pullback Strategy': 'YES' }, 'pullback')).toBe(true);
    expect(rowMatchesStrategy({ 'Triggered Strategies': 'Breakout' }, 'breakout')).toBe(true);
    expect(rowMatchesStrategy({ 'Pullback Strategy': 'NO' }, 'pullback')).toBe(false);
  });

  it('uses refreshed price and trade level fields when available', () => {
    const candidate = candidateFromWatchlistRow(
      {
        Ticker: 'AAPL',
        Price: 200,
        'Current Price': 212.5,
        'Entry Area': 212.5,
        'Suggested Stop': 204.5,
        'Target/Exit': 228.5,
        'Price Source': 'Yahoo',
        'Price As Of': '2026-07-02',
        'Suggested Hold Time': '5 trading days'
      },
      0
    );

    expect(candidate).toMatchObject({
      currentPrice: '$212.50',
      entryArea: '$212.50',
      stop: '$204.50',
      targetExit: '$228.50',
      priceSource: 'Yahoo',
      priceAsOf: '2026-07-02'
    });
  });

  it('merges refreshed rows by ticker', () => {
    expect(
      mergeWatchlistRows(
        [
          { Ticker: 'AAPL', Price: 200 },
          { Ticker: 'MSFT', Price: 400 }
        ],
        [{ Ticker: 'AAPL', 'Current Price': 212.5 }]
      )
    ).toEqual([
      { Ticker: 'AAPL', Price: 200, 'Current Price': 212.5 },
      { Ticker: 'MSFT', Price: 400 }
    ]);
  });
});
