import { describe, expect, it } from 'vitest';
import {
  candidateFromWatchlistRow,
  mergeWatchlistRows,
  rowMatchesDisplaySettings,
  rowMatchesStrategy,
  sortCandidates,
  stopDistancePercent
} from './watchlist';

describe('watchlist display helpers', () => {
  it('maps existing scanner rows into display candidates', () => {
    const candidate = candidateFromWatchlistRow(
      {
        Ticker: 'AAPL',
        'Company Name': 'Apple Inc.',
        Sector: 'Information Technology',
        'Triggered Strategies': 'Pullback',
        'Composite Score': 82,
        Price: 211.43,
        'Stop 2ATR': 203.43,
        'Relative Strength': 12.345,
        'Relative Volume': 1.25,
        ATR14: 4.1,
        '5D Range': 12
      },
      0,
      '2026-07-02'
    );

    expect(candidate).toMatchObject({
      ticker: 'AAPL',
      companyName: 'Apple Inc.',
      sector: 'Information Technology',
      currentPrice: '$211.43',
      priceSource: 'Cached Close',
      targetExit: '$227.43',
      fiveDayRange: '12',
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

  it('calculates and filters by stop distance and 5D range settings', () => {
    const row = {
      Ticker: 'AAPL',
      Price: 100,
      'Stop 2ATR': 98,
      '5D Range': 11
    };

    expect(stopDistancePercent(row)).toBe(2);
    expect(
      rowMatchesDisplaySettings(row, {
        minStopDistancePercent: 1,
        minFiveDayRange: 10
      })
    ).toBe(true);
    expect(
      rowMatchesDisplaySettings(row, {
        minStopDistancePercent: 3,
        minFiveDayRange: 10
      })
    ).toBe(false);
    expect(
      rowMatchesDisplaySettings(row, {
        minStopDistancePercent: 1,
        minFiveDayRange: 12
      })
    ).toBe(false);
  });

  it('sorts candidates by numeric and text columns', () => {
    const candidates = [
      {
        id: 'MSFT',
        ticker: 'MSFT',
        companyName: 'Microsoft Corporation',
        sector: 'Information Technology',
        strategy: 'Pullback',
        score: '80',
        currentPrice: '$400.00',
        priceAsOf: '2026-07-02',
        priceSource: 'Yahoo',
        relativeStrength: '2.00%',
        relativeVolume: '1.10',
        atr: '$4.00',
        fiveDayRange: '6',
        entryArea: '$400.00',
        stop: '$392.00',
        targetExit: '$416.00',
        holdTime: '5 trading days'
      },
      {
        id: 'AAPL',
        ticker: 'AAPL',
        companyName: 'Apple Inc.',
        sector: 'Information Technology',
        strategy: 'Breakout',
        score: '120',
        currentPrice: '$210.00',
        priceAsOf: '2026-07-01',
        priceSource: 'Yahoo',
        relativeStrength: '5.00%',
        relativeVolume: '1.50',
        atr: '$3.00',
        fiveDayRange: '12',
        entryArea: '$210.00',
        stop: '$204.00',
        targetExit: '$222.00',
        holdTime: '5 trading days'
      }
    ];

    expect(sortCandidates(candidates, { key: 'score', direction: 'desc' }).map((row) => row.ticker)).toEqual([
      'AAPL',
      'MSFT'
    ]);
    expect(sortCandidates(candidates, { key: 'ticker', direction: 'asc' }).map((row) => row.ticker)).toEqual([
      'AAPL',
      'MSFT'
    ]);
  });
});
