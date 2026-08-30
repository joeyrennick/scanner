export type RecentTickerSource =
  | 'candidates'
  | 'daily-scanner'
  | 'fundamentals'
  | 'watchlists';

export const recentTickerStorageKey = 'swing-scanner.recent-ticker.v1';

export type RecentTickerSelection = {
  version: 1;
  ticker: string;
  source: RecentTickerSource;
  selectedAt: number;
  savedWatchlistId?: number;
};

export function rememberRecentTicker(
  ticker: string,
  source: RecentTickerSource,
  savedWatchlistId?: number | null
): void {
  const normalized = normalizeTicker(ticker);
  if (!normalized) return;

  const selection: RecentTickerSelection = {
    version: 1,
    ticker: normalized,
    source,
    selectedAt: Date.now(),
    ...(typeof savedWatchlistId === 'number' && Number.isInteger(savedWatchlistId)
      ? { savedWatchlistId }
      : {})
  };
  localStorage.setItem(recentTickerStorageKey, JSON.stringify(selection));
}

export function loadRecentTicker(): string | null {
  return loadRecentTickerSelection()?.ticker ?? null;
}

export function loadRecentTickerSelection(): RecentTickerSelection | null {
  const stored = localStorage.getItem(recentTickerStorageKey);
  if (!stored) return null;

  try {
    const parsed = JSON.parse(stored) as Partial<RecentTickerSelection> | null;
    if (parsed?.version !== 1 || typeof parsed.ticker !== 'string') {
      return null;
    }
    const ticker = normalizeTicker(parsed.ticker);
    if (!ticker) return null;
    return {
      version: 1,
      ticker,
      source: isRecentTickerSource(parsed.source) ? parsed.source : 'candidates',
      selectedAt: typeof parsed.selectedAt === 'number' ? parsed.selectedAt : 0,
      ...(typeof parsed.savedWatchlistId === 'number' && Number.isInteger(parsed.savedWatchlistId)
        ? { savedWatchlistId: parsed.savedWatchlistId }
        : {})
    };
  } catch {
    localStorage.removeItem(recentTickerStorageKey);
    return null;
  }
}

function isRecentTickerSource(value: unknown): value is RecentTickerSource {
  return ['candidates', 'daily-scanner', 'fundamentals', 'watchlists'].includes(String(value));
}

function normalizeTicker(ticker: string): string {
  return ticker.trim().toUpperCase();
}
