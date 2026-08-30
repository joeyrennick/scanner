export type RecentTickerSource = 'candidates' | 'daily-scanner';

export const recentTickerStorageKey = 'swing-scanner.recent-ticker.v1';

type RecentTickerSelection = {
  version: 1;
  ticker: string;
  source: RecentTickerSource;
  selectedAt: number;
};

export function rememberRecentTicker(
  ticker: string,
  source: RecentTickerSource
): void {
  const normalized = normalizeTicker(ticker);
  if (!normalized) return;

  const selection: RecentTickerSelection = {
    version: 1,
    ticker: normalized,
    source,
    selectedAt: Date.now()
  };
  localStorage.setItem(recentTickerStorageKey, JSON.stringify(selection));
}

export function loadRecentTicker(): string | null {
  const stored = localStorage.getItem(recentTickerStorageKey);
  if (!stored) return null;

  try {
    const parsed = JSON.parse(stored) as Partial<RecentTickerSelection> | null;
    if (parsed?.version !== 1 || typeof parsed.ticker !== 'string') {
      return null;
    }
    return normalizeTicker(parsed.ticker) || null;
  } catch {
    localStorage.removeItem(recentTickerStorageKey);
    return null;
  }
}

function normalizeTicker(ticker: string): string {
  return ticker.trim().toUpperCase();
}
