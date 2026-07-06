import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';
import { queryKeys } from './queryKeys';
import type { StrategyMetadata } from './types';

export function useStrategies() {
  return useQuery({
    queryKey: queryKeys.strategies,
    queryFn: () => apiClient.request<StrategyMetadata[]>('/api/strategies')
  });
}
