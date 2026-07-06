import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';
import { queryKeys } from './queryKeys';
import type { JobResponse } from './types';

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.job(jobId),
    enabled: Boolean(jobId),
    queryFn: () => apiClient.request<JobResponse>(`/api/jobs/${jobId}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'running' ? 1000 : false;
    }
  });
}
