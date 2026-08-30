import { beforeEach, describe, expect, it } from 'vitest';
import { loadWatchlistPageState } from './WatchlistsPage';

const storageKey = 'swing-scanner.saved-watchlists.page.v1';

describe('saved watchlist page state', () => {
  beforeEach(() => localStorage.clear());

  it('restores the active list, filters, sort, columns, selection, and scroll position', () => {
    localStorage.setItem(storageKey, JSON.stringify({
      version: 1,
      activeWatchlistId: 7,
      activeTicker: 'MSFT',
      selectedTickers: ['MSFT', 'AAPL'],
      search: 'soft',
      filters: { risk: 'low', minPrice: 20 },
      sort: { key: 'risk', direction: 'desc' },
      widths: { ticker: 240 },
      visibility: { fairValue: false },
      scrollTop: 180,
      scrollLeft: 90
    }));

    const state = loadWatchlistPageState();
    expect(state).toMatchObject({
      activeWatchlistId: 7,
      activeTicker: 'MSFT',
      selectedTickers: ['MSFT', 'AAPL'],
      search: 'soft',
      sort: { key: 'risk', direction: 'desc' },
      scrollTop: 180,
      scrollLeft: 90
    });
    expect(state.filters.risk).toEqual(['low']);
    expect(state.filters.minPrice).toBe(20);
    expect(state.widths.ticker).toBe(240);
    expect(state.visibility.fairValue).toBe(false);
    expect(state.visibility.ticker).toBe(true);
  });

  it('falls back safely when saved state is malformed', () => {
    localStorage.setItem(storageKey, '{broken');

    const state = loadWatchlistPageState();
    expect(state.activeWatchlistId).toBeNull();
    expect(state.sort).toEqual({ key: 'ticker', direction: 'asc' });
    expect(localStorage.getItem(storageKey)).toBeNull();
  });
});
