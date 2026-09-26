import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useApplicationApi } from '../platform/PlatformProvider';
import { queryKeys } from './queryKeys';
import type {
  FundamentalAnalysis,
  FundamentalReportResponse,
  JobResponse,
  WatchlistRiskClassificationRequest
} from './types';

export function useAnalyzeFundamentals() {
  const apiClient = useApplicationApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ticker, assumptions, runId }: { ticker: string; assumptions: Record<string, number>; runId: number | null }) =>
      apiClient.request<FundamentalAnalysis>(`/api/fundamentals/${encodeURIComponent(ticker)}`, {
        method: 'POST',
        body: JSON.stringify({ assumptions, run_id: runId })
      }),
    onSuccess: (_analysis, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.latestWatchlist });
      if (variables.runId !== null) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.watchlistRun(variables.runId) });
      }
    }
  });
}

export function useGenerateFundamentalReport() {
  const apiClient = useApplicationApi();
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

export function useClassifyWatchlistRisk() {
  const apiClient = useApplicationApi();
  return useMutation({
    mutationFn: (request: WatchlistRiskClassificationRequest) =>
      apiClient.request<JobResponse>('/api/watchlist/classify-risk', {
        method: 'POST',
        body: JSON.stringify(request)
      })
  });
}
