import { describe, expect, it, vi } from 'vitest';
import { ApiError, createApiClient } from './client';

describe('api client', () => {
  it('returns JSON responses', async () => {
    const fetcher = vi.fn(async () =>
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );
    const client = createApiClient({ baseUrl: 'http://localhost', fetcher });

    await expect(client.request('/api/health')).resolves.toEqual({ status: 'ok' });
    expect(fetcher).toHaveBeenCalledWith(
      'http://localhost/api/health',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' })
      })
    );
  });

  it('throws ApiError with backend detail when request fails', async () => {
    const fetcher = vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Job not found' }), {
        status: 404,
        statusText: 'Not Found',
        headers: { 'Content-Type': 'application/json' }
      })
    );
    const client = createApiClient({ fetcher });

    await expect(client.request('/api/jobs/missing')).rejects.toMatchObject({
      status: 404,
      message: 'Job not found'
    });
  });
});
