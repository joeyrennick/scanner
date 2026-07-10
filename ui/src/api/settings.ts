import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import { queryKeys } from './queryKeys';
import type { MarketDataCredentialRequest, MarketDataCredentialStatus } from './types';

export function useMassiveCredentialStatus() {
  return useQuery({
    queryKey: queryKeys.massiveCredential,
    queryFn: () =>
      apiClient.request<MarketDataCredentialStatus>('/api/market-data/massive/credential')
  });
}

export function useSaveMassiveCredential() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: MarketDataCredentialRequest) =>
      apiClient.request<MarketDataCredentialStatus>('/api/market-data/massive/credential', {
        method: 'PUT',
        body: JSON.stringify(request)
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.massiveCredential });
    }
  });
}

export function useDeleteMassiveCredential() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiClient.request<MarketDataCredentialStatus>('/api/market-data/massive/credential', {
        method: 'DELETE'
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.massiveCredential });
    }
  });
}
