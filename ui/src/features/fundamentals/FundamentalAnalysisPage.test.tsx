import { beforeEach, describe, expect, it } from 'vitest';
import { candidateRows, loadFundamentalState } from './FundamentalAnalysisPage';

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
    expect(state.runId).toBe(8);
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

    expect(candidateRows(rows, 'pullback').map((row) => row.Ticker)).toEqual(['AAPL']);
    expect(candidateRows(rows, 'all')).toHaveLength(2);
  });
});
