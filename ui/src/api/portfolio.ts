import { useMutation } from '@tanstack/react-query';
import { useApplicationApi } from '../platform/PlatformProvider';
import type { JobResponse, PortfolioSimulationRequest } from './types';

export function useStartPortfolioSimulation() {
  const apiClient = useApplicationApi();
  return useMutation({
    mutationFn: (request: PortfolioSimulationRequest) =>
      apiClient.request<JobResponse>('/api/portfolio/simulations', {
        method: 'POST',
        body: JSON.stringify(request)
      })
  });
}
