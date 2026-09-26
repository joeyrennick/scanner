import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApplicationApi } from '../platform/PlatformProvider';
import { queryKeys } from './queryKeys';
import type {
  DailyScannerReportRequest,
  DailyScannerReportResponse,
  ReportMetadata,
  SavedWatchlistReportResponse
} from './types';

export function useReports() {
  const apiClient = useApplicationApi();
  return useQuery({
    queryKey: queryKeys.reports,
    queryFn: () => apiClient.request<ReportMetadata[]>('/api/reports')
  });
}

export function useGenerateDailyScannerReport() {
  const apiClient = useApplicationApi();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: DailyScannerReportRequest) =>
      apiClient.request<DailyScannerReportResponse>('/api/reports/daily-scanner', {
        method: 'POST',
        body: JSON.stringify(request)
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.reports });
    }
  });
}

export function useGenerateSavedWatchlistReport() {
  const apiClient = useApplicationApi();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (watchlistId: number) =>
      apiClient.request<SavedWatchlistReportResponse>(
        `/api/reports/saved-watchlist/${watchlistId}`,
        { method: 'POST' }
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.reports });
    }
  });
}
