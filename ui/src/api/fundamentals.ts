import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import { queryKeys } from './queryKeys';
import type { FundamentalAnalysis, FundamentalReportResponse } from './types';

export function useAnalyzeFundamentals() {
  return useMutation({
    mutationFn: ({ ticker, assumptions }: { ticker: string; assumptions: Record<string, number> }) =>
      apiClient.request<FundamentalAnalysis>(`/api/fundamentals/${encodeURIComponent(ticker)}`, {
        method: 'POST',
        body: JSON.stringify({ assumptions })
      })
  });
}

export function useGenerateFundamentalReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      ticker,
      analysis,
      pageState
    }: {
      ticker: string;
      analysis: FundamentalAnalysis;
      pageState: Record<string, unknown>;
    }) =>
      apiClient.request<FundamentalReportResponse>('/api/reports/fundamental-analysis', {
        method: 'POST',
        body: JSON.stringify({ ticker, analysis, page_state: pageState })
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.reports });
    }
  });
}
