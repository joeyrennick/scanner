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
        headers: expect.objectContaining({ 'content-type': 'application/json' })
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

  it('adds a desktop bearer token without dropping request headers', async () => {
    const fetcher = vi.fn(async () =>
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:49152',
      bearerToken: 'desktop-secret',
      fetcher
    });

    await client.request('/api/desktop/health', {
      headers: { 'X-Test-Request': 'phase-zero' }
    });

    expect(fetcher).toHaveBeenCalledWith(
      'http://127.0.0.1:49152/api/desktop/health',
      expect.objectContaining({
        headers: expect.objectContaining({
          authorization: 'Bearer desktop-secret',
          'content-type': 'application/json',
          'x-test-request': 'phase-zero'
        })
      })
    );
  });
});
