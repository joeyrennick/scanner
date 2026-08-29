import { beforeEach, describe, expect, it } from 'vitest';
import {
  candidateRiskCounts,
  candidateRows,
  candidateSelectionForStrategy,
  candidateStrategyForRows,
  candidateTickerForStrategy,
  candidateValidationCounts,
  loadFundamentalState
} from './FundamentalAnalysisPage';

const displaySettings = { minStopDistancePercent: 1, minFiveDayRange: 10 };

describe('fundamental analysis state', () => {
  beforeEach(() => localStorage.clear());

  it('restores saved component state and lets the URL select navigation state', () => {
    localStorage.setItem(
      'swing-scanner.fundamentals.v1',
      JSON.stringify({
        version: 1,
        ticker: 'MSFT',
        tickerDraft: 'MSFT',
        runId: 8,
        strategy: 'pullback',
        risk: 'low',
        validation: 'needs_review',
        classificationJobId: 'classification-123',
        tab: 'quality',
        scrollY: 240,
        assumptionsByTicker: { MSFT: { discount_rate: 0.11 } }
      })
    );

    const state = loadFundamentalState(new URLSearchParams('ticker=AAPL&tab=validation&validation=validated'));

    expect(state.ticker).toBe('AAPL');
    expect(state.tab).toBe('validation');
    expect(state.risk).toBe('low');
    expect(state.validation).toBe('validated');
    expect(state.classificationJobId).toBe('classification-123');
    expect(state.runId).toBeNull();
    expect(state.scrollY).toBe(240);
    expect(state.assumptionsByTicker.MSFT.discount_rate).toBe(0.11);
  });

  it('ignores malformed saved state', () => {
    localStorage.setItem('swing-scanner.fundamentals.v1', '{broken');

    const state = loadFundamentalState(new URLSearchParams());

    expect(state.ticker).toBe('');
    expect(localStorage.getItem('swing-scanner.fundamentals.v1')).toBeNull();
  });

  it('filters candidate navigation by triggered strategy', () => {
    const rows = [
      { Ticker: 'AAPL', 'Triggered Strategies': 'Pullback Strategy' },
      { Ticker: 'MSFT', 'Triggered Strategies': 'Breakout Strategy' }
    ];

    expect(candidateRows(rows, 'pullback', displaySettings).map((row) => row.Ticker)).toEqual(['AAPL']);
    expect(candidateRows(rows, 'all', displaySettings)).toHaveLength(2);
  });

  it('preserves an explicitly linked historical scanner run', () => {
    const state = loadFundamentalState(new URLSearchParams('ticker=AAPL&run_id=6'));

    expect(state.runId).toBe(6);
  });

  it('uses the same display thresholds as the Candidates page', () => {
    const rows = [
      { Ticker: 'AAPL', 'Triggered Strategies': 'Pullback', 'Current Price': 100, 'Suggested Stop': 98, '5D Range': 12 },
      { Ticker: 'MSFT', 'Triggered Strategies': 'Pullback', 'Current Price': 100, 'Suggested Stop': 99.5, '5D Range': 12 },
      { Ticker: 'NVDA', 'Triggered Strategies': 'Pullback', 'Current Price': 100, 'Suggested Stop': 98, '5D Range': 8 }
    ];

    expect(candidateRows(rows, 'all', displaySettings).map((row) => row.Ticker)).toEqual(['AAPL']);
  });

  it('filters candidates by saved risk classification', () => {
    const rows = [
      { Ticker: 'LOW', 'Triggered Strategies': 'Undervalued', 'Risk Level': 'low' },
      { Ticker: 'MED', 'Triggered Strategies': 'Undervalued', 'Risk Level': 'moderate' },
      { Ticker: 'HIGH', 'Triggered Strategies': 'Undervalued', 'Risk Level': 'HIGH' },
      { Ticker: 'OLD', 'Triggered Strategies': 'Undervalued' }
    ];

    expect(candidateRows(rows, 'undervalued', displaySettings, 'low').map((row) => row.Ticker)).toEqual(['LOW']);
    expect(candidateRows(rows, 'undervalued', displaySettings, 'moderate').map((row) => row.Ticker)).toEqual(['MED']);
    expect(candidateRows(rows, 'undervalued', displaySettings, 'high').map((row) => row.Ticker)).toEqual(['HIGH']);
    expect(candidateRows(rows, 'undervalued', displaySettings, 'unknown').map((row) => row.Ticker)).toEqual(['OLD']);
    expect(candidateRiskCounts(rows, 'undervalued', displaySettings)).toEqual({
      low: 1,
      moderate: 1,
      high: 1,
      unknown: 1
    });
  });

  it('lets the URL restore a risk filter', () => {
    const state = loadFundamentalState(new URLSearchParams('risk=high'));

    expect(state.risk).toBe('high');
  });

  it('filters and counts candidates by automated validation status', () => {
    const rows = [
      { Ticker: 'PASS', 'Triggered Strategies': 'Undervalued', 'Validation Status': 'validated' },
      { Ticker: 'REVIEW', 'Triggered Strategies': 'Undervalued', 'Validation Status': 'needs_review' },
      { Ticker: 'FAIL', 'Triggered Strategies': 'Undervalued', 'Validation Status': 'REJECTED' },
      { Ticker: 'OLD', 'Triggered Strategies': 'Undervalued' }
    ];

    expect(candidateRows(rows, 'undervalued', displaySettings, 'all', 'validated').map((row) => row.Ticker)).toEqual(['PASS']);
    expect(candidateRows(rows, 'undervalued', displaySettings, 'all', 'needs_review').map((row) => row.Ticker)).toEqual(['REVIEW']);
    expect(candidateRows(rows, 'undervalued', displaySettings, 'all', 'rejected').map((row) => row.Ticker)).toEqual(['FAIL']);
    expect(candidateRows(rows, 'undervalued', displaySettings, 'all', 'not_calculated').map((row) => row.Ticker)).toEqual(['OLD']);
    expect(candidateValidationCounts(rows, 'undervalued', displaySettings)).toEqual({
      validated: 1,
      needs_review: 1,
      rejected: 1,
      not_calculated: 1
    });
  });

  it('selects a matching candidate when the strategy filter changes', () => {
    const rows = [
      { Ticker: 'ATLO', 'Triggered Strategies': 'Pullback, Bounce' },
      { Ticker: 'SCHW', 'Triggered Strategies': 'Bounce' },
      { Ticker: 'TSLA', 'Triggered Strategies': 'Breakout' }
    ];
    const pullbacks = candidateRows(rows, 'pullback', displaySettings);
    const bounces = candidateRows(rows, 'bounce', displaySettings);

    expect(candidateTickerForStrategy(pullbacks, 'SCHW')).toBe('ATLO');
    expect(candidateTickerForStrategy(bounces, 'SCHW')).toBe('SCHW');
    expect(candidateTickerForStrategy([], 'SCHW')).toBeNull();
  });

  it('reconciles an obsolete saved filter to an undervalued-only scanner run', () => {
    const rows = [
      {
        Ticker: 'MCD',
        'Triggered Strategies': 'Undervalued',
        'Undervalued Strategy': 'YES'
      },
      {
        Ticker: 'GOGO',
        'Triggered Strategies': 'Undervalued',
        'Undervalued Strategy': 'YES'
      }
    ];

    expect(candidateStrategyForRows(rows, 'pullback', displaySettings)).toBe('undervalued');
    expect(candidateRows(rows, 'undervalued', displaySettings)).toHaveLength(2);
  });

  it('moves from a historical technical run to the latest undervalued run when selected', () => {
    const historicalRows = [{ Ticker: 'SCHW', 'Triggered Strategies': 'Bounce' }];
    const latestRows = [
      {
        Ticker: 'MCD',
        'Triggered Strategies': 'Undervalued',
        'Undervalued Strategy': 'YES'
      }
    ];

    const undervalued = candidateSelectionForStrategy(
      historicalRows,
      latestRows,
      'undervalued',
      7,
      displaySettings
    );
    const breakout = candidateSelectionForStrategy(
      historicalRows,
      latestRows,
      'breakout',
      7,
      displaySettings
    );

    expect(undervalued.runId).toBeNull();
    expect(undervalued.matchingRows.map((row) => row.Ticker)).toEqual(['MCD']);
    expect(breakout.runId).toBe(7);
    expect(breakout.matchingRows).toEqual([]);
  });
});
