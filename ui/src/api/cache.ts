import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApplicationApi } from '../platform/PlatformProvider';
import { queryKeys } from './queryKeys';
import type { CacheOverview, CacheWarmupRequest, JobResponse } from './types';

export function useCacheOverview() {
  const apiClient = useApplicationApi();
  return useQuery({
    queryKey: queryKeys.cacheOverview,
    queryFn: () => apiClient.request<CacheOverview>('/api/cache/overview')
  });
}

export function useStartCacheWarmup() {
  const apiClient = useApplicationApi();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CacheWarmupRequest) =>
      apiClient.request<JobResponse>('/api/cache/warmup', {
        method: 'POST',
        body: JSON.stringify(request)
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cacheOverview });
    }
  });
}
