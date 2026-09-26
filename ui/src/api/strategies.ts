import { useQuery } from '@tanstack/react-query';
import { useApplicationApi } from '../platform/PlatformProvider';
import { queryKeys } from './queryKeys';
import type { StrategyMetadata } from './types';

export function useStrategies() {
  const apiClient = useApplicationApi();
  return useQuery({
    queryKey: queryKeys.strategies,
    queryFn: () => apiClient.request<StrategyMetadata[]>('/api/strategies')
  });
}
