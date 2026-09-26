import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApplicationApi } from '../platform/PlatformProvider';
import { queryKeys } from './queryKeys';
import type {
  SavedWatchlist,
  SavedWatchlistItem,
  SavedWatchlistListResponse,
  WatchlistRow
} from './types';

export function useSavedWatchlists() {
  const apiClient = useApplicationApi();
  return useQuery({
    queryKey: queryKeys.savedWatchlists,
    queryFn: () =>
      apiClient.request<SavedWatchlistListResponse>('/api/saved-watchlists'),
    refetchOnMount: 'always'
  });
}

export function useSavedWatchlist(watchlistId: number | null) {
  const apiClient = useApplicationApi();
  return useQuery({
    queryKey: queryKeys.savedWatchlist(watchlistId),
    queryFn: () =>
      apiClient.request<SavedWatchlist>(`/api/saved-watchlists/${watchlistId}`),
    enabled: watchlistId !== null
  });
}

function useInvalidateSavedWatchlists() {
  const queryClient = useQueryClient();
  return (watchlistId?: number | null) => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.savedWatchlists });
    if (watchlistId !== undefined) {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.savedWatchlist(watchlistId)
      });
    }
  };
}

export function useCreateSavedWatchlist() {
  const apiClient = useApplicationApi();
  const invalidate = useInvalidateSavedWatchlists();
  return useMutation({
    mutationFn: (name: string) =>
      apiClient.request<SavedWatchlist>('/api/saved-watchlists', {
        method: 'POST',
        body: JSON.stringify({ name })
      }),
    onSuccess: (watchlist) => invalidate(watchlist.id)
  });
}

export function useRenameSavedWatchlist() {
  const apiClient = useApplicationApi();
  const invalidate = useInvalidateSavedWatchlists();
  return useMutation({
    mutationFn: ({ watchlistId, name }: { watchlistId: number; name: string }) =>
      apiClient.request<SavedWatchlist>(`/api/saved-watchlists/${watchlistId}`, {
        method: 'PATCH',
        body: JSON.stringify({ name })
      }),
    onSuccess: (watchlist) => invalidate(watchlist.id)
  });
}

export function useDeleteSavedWatchlist() {
  const apiClient = useApplicationApi();
  const invalidate = useInvalidateSavedWatchlists();
  return useMutation({
    mutationFn: (watchlistId: number) =>
      apiClient.request<{ deleted: boolean }>(`/api/saved-watchlists/${watchlistId}`, {
        method: 'DELETE'
      }),
    onSuccess: (_response, watchlistId) => invalidate(watchlistId)
  });
}

export function useAddSavedWatchlistItem() {
  const apiClient = useApplicationApi();
  const invalidate = useInvalidateSavedWatchlists();
  return useMutation({
    mutationFn: ({
      watchlistId,
      ticker,
      source,
      data
    }: {
      watchlistId: number;
      ticker: string;
      source: string;
      data: WatchlistRow;
    }) =>
      apiClient.request<SavedWatchlistItem>(
        `/api/saved-watchlists/${watchlistId}/items`,
        {
          method: 'POST',
          body: JSON.stringify({ ticker, source, data })
        }
      ),
    onSuccess: (_item, variables) => invalidate(variables.watchlistId)
  });
}

export function useRemoveSavedWatchlistItem() {
  const apiClient = useApplicationApi();
  const invalidate = useInvalidateSavedWatchlists();
  return useMutation({
    mutationFn: ({ watchlistId, ticker }: { watchlistId: number; ticker: string }) =>
      apiClient.request<{ deleted: boolean }>(
        `/api/saved-watchlists/${watchlistId}/items/${encodeURIComponent(ticker)}`,
        { method: 'DELETE' }
      ),
    onSuccess: (_response, variables) => invalidate(variables.watchlistId)
  });
}
