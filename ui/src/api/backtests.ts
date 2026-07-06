import { useMutation } from '@tanstack/react-query';
import { apiClient } from './client';
import type { BacktestRequest, JobResponse } from './types';

export function useStartBacktest() {
  return useMutation({
    mutationFn: (request: BacktestRequest) =>
      apiClient.request<JobResponse>('/api/backtests', {
        method: 'POST',
        body: JSON.stringify(request)
      })
  });
}
