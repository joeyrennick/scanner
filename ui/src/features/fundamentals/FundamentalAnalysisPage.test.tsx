import { beforeEach, describe, expect, it } from 'vitest';
import { candidateRows, loadFundamentalState } from './FundamentalAnalysisPage';

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
        tab: 'quality',
        scrollY: 240,
        assumptionsByTicker: { MSFT: { discount_rate: 0.11 } }
      })
    );

    const state = loadFundamentalState(new URLSearchParams('ticker=AAPL&tab=valuation'));

    expect(state.ticker).toBe('AAPL');
    expect(state.tab).toBe('valuation');
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
});
