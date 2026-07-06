import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import { queryKeys } from './queryKeys';
import type {
  JobResponse,
  ScanRequest,
  WatchlistPriceRefreshRequest,
  WatchlistPriceRefreshResponse,
  WatchlistResponse
} from './types';

export function useLatestWatchlist() {
  return useQuery({
    queryKey: queryKeys.latestWatchlist,
    queryFn: () => apiClient.request<WatchlistResponse>('/api/watchlist/latest')
  });
}

export function useStartScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ScanRequest) =>
      apiClient.request<JobResponse>('/api/scans', {
        method: 'POST',
        body: JSON.stringify(request)
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.latestWatchlist });
      void queryClient.invalidateQueries({ queryKey: queryKeys.cacheOverview });
    }
  });
}

export function useRefreshWatchlistPrices() {
  return useMutation({
    mutationFn: (request: WatchlistPriceRefreshRequest) =>
      apiClient.request<WatchlistPriceRefreshResponse>('/api/watchlist/refresh-prices', {
        method: 'POST',
        body: JSON.stringify(request)
      })
  });
}
