export const queryKeys = {
  cacheOverview: ['cache', 'overview'] as const,
  marketDataHistory: (ticker: string | null, provider: string, period: string) =>
    ['market-data', 'history', ticker, provider, period] as const,
  massiveCredential: ['market-data', 'massive', 'credential'] as const,
  strategies: ['strategies'] as const,
  job: (jobId: string | null) => ['jobs', jobId] as const,
  latestWatchlist: ['watchlist', 'latest'] as const,
  watchlistRun: (runId: number | null) => ['watchlist', 'run', runId] as const,
  fundamentals: (ticker: string, assumptions: Record<string, number>) =>
    ['fundamentals', ticker, assumptions] as const,
  reports: ['reports'] as const
};
