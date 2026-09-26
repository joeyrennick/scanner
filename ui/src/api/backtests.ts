import { useMutation } from '@tanstack/react-query';
import { useApplicationApi } from '../platform/PlatformProvider';
import type { BacktestRequest, JobResponse } from './types';

export function useStartBacktest() {
  const apiClient = useApplicationApi();
  return useMutation({
    mutationFn: (request: BacktestRequest) =>
      apiClient.request<JobResponse>('/api/backtests', {
        method: 'POST',
        body: JSON.stringify(request)
      })
  });
}
