import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  loadRecentTicker,
  loadRecentTickerSelection,
  recentTickerStorageKey,
  rememberRecentTicker
} from './recentTicker';

describe('recent ticker selection', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('stores a normalized ticker and the page that selected it', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1234);

    rememberRecentTicker(' msft ', 'candidates');

    expect(loadRecentTicker()).toBe('MSFT');
    expect(JSON.parse(localStorage.getItem(recentTickerStorageKey) ?? '{}')).toEqual({
      version: 1,
      ticker: 'MSFT',
      source: 'candidates',
      selectedAt: 1234
    });
  });

  it('uses the most recent selection regardless of its source page', () => {
    rememberRecentTicker('AAPL', 'candidates');
    rememberRecentTicker('NVDA', 'daily-scanner');
    rememberRecentTicker('TSLA', 'fundamentals');

    expect(loadRecentTicker()).toBe('TSLA');
  });

  it('preserves saved-watchlist navigation context', () => {
    rememberRecentTicker('AAPL', 'watchlists', 14);

    expect(loadRecentTickerSelection()).toMatchObject({
      ticker: 'AAPL',
      source: 'watchlists',
      savedWatchlistId: 14
    });
  });

  it('ignores malformed persisted selections', () => {
    localStorage.setItem(recentTickerStorageKey, '{broken');

    expect(loadRecentTicker()).toBeNull();
    expect(localStorage.getItem(recentTickerStorageKey)).toBeNull();
  });
});
