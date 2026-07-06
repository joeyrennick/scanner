export const queryKeys = {
  cacheOverview: ['cache', 'overview'] as const,
  strategies: ['strategies'] as const,
  job: (jobId: string | null) => ['jobs', jobId] as const,
  latestWatchlist: ['watchlist', 'latest'] as const
};
