import { useMutation } from '@tanstack/react-query';
import { apiClient } from './client';
import type { JobResponse, PortfolioSimulationRequest } from './types';

export function useStartPortfolioSimulation() {
  return useMutation({
    mutationFn: (request: PortfolioSimulationRequest) =>
      apiClient.request<JobResponse>('/api/portfolio/simulations', {
        method: 'POST',
        body: JSON.stringify(request)
      })
  });
}
