import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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

export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) =>
      apiClient.request<JobResponse>(`/api/jobs/${jobId}/cancel`, {
        method: 'POST'
      }),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.job(job.job_id) });
    }
  });
}
