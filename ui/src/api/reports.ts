import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import { queryKeys } from './queryKeys';
import type {
  DailyScannerReportRequest,
  DailyScannerReportResponse,
  ReportMetadata
} from './types';

export function useReports() {
  return useQuery({
    queryKey: queryKeys.reports,
    queryFn: () => apiClient.request<ReportMetadata[]>('/api/reports')
  });
}

export function useGenerateDailyScannerReport() {
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
