import { describe, expect, it } from 'vitest';
import {
  candidateFromWatchlistRow,
  defaultScannerResultFilters,
  mergeWatchlistRows,
  normalizeScannerResultFilters,
  rowMatchesDisplaySettings,
  rowMatchesScannerResultFilters,
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
    expect(candidate).toMatchObject({
      validationLabel: 'Not calculated',
      qualityLabel: 'Not calculated',
      dcfLabel: 'Not calculated',
      riskLabel: 'Not calculated'
    });
  });

  it('maps the Fundamentals summary classifications into scanner candidates', () => {
    const candidate = candidateFromWatchlistRow(
      {
        Ticker: 'SFNC',
        'Validation Status': 'needs_review',
        'Validation Score': 79,
        'Quality Label': 'weak',
        'Quality Score': 33,
        'Valuation Label': 'undervalued',
        'Margin of Safety': 42.15,
        'Risk Level': 'low',
        'Risk Score': 25
      },
      0
    );

    expect(candidate).toMatchObject({
      validationLabel: 'Needs Review',
      validationScore: '79',
      qualityLabel: 'Weak',
      qualityScore: '33',
      dcfLabel: 'Undervalued by DCF',
      marginOfSafety: '42.15%',
      riskLabel: 'Low',
      riskScore: '25'
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

  it('normalizes persisted scanner result filters and rejects obsolete values', () => {
    expect(
      normalizeScannerResultFilters({
        validation: 'needs_review',
        quality: 'weak',
        dcf: 'undervalued',
        risk: 'low',
        minPrice: 25,
        maxPrice: 150.5
      })
    ).toEqual({
      validation: 'needs_review',
      quality: 'weak',
      dcf: 'undervalued',
      risk: 'low',
      minPrice: 25,
      maxPrice: 150.5
    });

    expect(
      normalizeScannerResultFilters({
        validation: 'obsolete',
        quality: 12,
        dcf: null,
        risk: 'medium',
        minPrice: -1,
        maxPrice: '100'
      })
    ).toEqual(defaultScannerResultFilters);
    expect(
      rowMatchesScannerResultFilters(
        {
          'Validation Status': 'rejected',
          'Quality Label': 'weak',
          'Valuation Label': 'overvalued',
          'Risk Level': 'high'
        },
        defaultScannerResultFilters
      )
    ).toBe(true);
  });

  it('filters inclusively by current price with a saved-price fallback', () => {
    const filters = {
      ...defaultScannerResultFilters,
      minPrice: 25,
      maxPrice: 100
    };

    expect(
      rowMatchesScannerResultFilters(
        { Price: 10, 'Current Price': 25 },
        filters
      )
    ).toBe(true);
    expect(rowMatchesScannerResultFilters({ Price: 100 }, filters)).toBe(true);
    expect(rowMatchesScannerResultFilters({ Price: 24.99 }, filters)).toBe(false);
    expect(
      rowMatchesScannerResultFilters(
        { Price: 50, 'Current Price': 100.01 },
        filters
      )
    ).toBe(false);
    expect(rowMatchesScannerResultFilters({}, filters)).toBe(false);
    expect(
      rowMatchesScannerResultFilters(
        {},
        { ...defaultScannerResultFilters, minPrice: null, maxPrice: null }
      )
    ).toBe(true);
  });

  it('recognizes every scanner result classification and missing values', () => {
    const cases = [
      ['validation', 'Validation Status', ['validated', 'needs_review', 'rejected']],
      ['quality', 'Quality Label', ['strong', 'acceptable', 'weak']],
      ['dcf', 'Valuation Label', ['undervalued', 'fairly_valued', 'overvalued']],
      ['risk', 'Risk Level', ['low', 'moderate', 'high']]
    ] as const;

    for (const [filterName, columnName, values] of cases) {
      for (const value of values) {
        expect(
          rowMatchesScannerResultFilters(
            { [columnName]: value },
            { ...defaultScannerResultFilters, [filterName]: value }
          )
        ).toBe(true);
      }
      expect(
        rowMatchesScannerResultFilters(
          {},
          { ...defaultScannerResultFilters, [filterName]: 'not_calculated' }
        )
      ).toBe(true);
    }
  });

  it('combines result filters with AND semantics and preserves them while sorting', () => {
    const rows = [
      {
        Ticker: 'SFNC',
        'Composite Score': 75,
        'Validation Status': 'needs_review',
        'Quality Label': 'weak',
        'Valuation Label': 'undervalued',
        'Risk Level': 'low'
      },
      {
        Ticker: 'MATCH',
        'Composite Score': 90,
        'Validation Status': 'needs_review',
        'Quality Label': 'weak',
        'Valuation Label': 'undervalued',
        'Risk Level': 'low'
      },
      {
        Ticker: 'WRONGRISK',
        'Composite Score': 99,
        'Validation Status': 'needs_review',
        'Quality Label': 'weak',
        'Valuation Label': 'undervalued',
        'Risk Level': 'high'
      }
    ];
    const filters = {
      ...defaultScannerResultFilters,
      validation: 'needs_review',
      quality: 'weak',
      dcf: 'undervalued',
      risk: 'low'
    } as const;
    const candidates = rows
      .filter((row) => rowMatchesScannerResultFilters(row, filters))
      .map((row, index) => candidateFromWatchlistRow(row, index));

    expect(sortCandidates(candidates, { key: 'score', direction: 'asc' }).map((row) => row.ticker)).toEqual([
      'SFNC',
      'MATCH'
    ]);
    expect(sortCandidates(candidates, { key: 'score', direction: 'desc' }).map((row) => row.ticker)).toEqual([
      'MATCH',
      'SFNC'
    ]);
    expect(filters).toEqual({
      validation: 'needs_review',
      quality: 'weak',
      dcf: 'undervalued',
      risk: 'low',
      minPrice: null,
      maxPrice: null
    });
  });
});
