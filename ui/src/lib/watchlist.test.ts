import { describe, expect, it } from 'vitest';
import { candidateFromWatchlistRow, rowMatchesStrategy } from './watchlist';

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
});
