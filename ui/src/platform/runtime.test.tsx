import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { createApiClient } from '../api/client';
import { connectDesktop, createRuntime, type RuntimeInfo } from './runtime';
import { PlatformProvider } from './PlatformProvider';
import { RuntimeReadiness } from '../features/settings/RuntimeReadiness';
import { FileActionButton } from '../components/FileActionButton';
import { useReports } from '../api/reports';
import { useMassiveCredentialStatus } from '../api/settings';
import { BusinessRecordsGate, BusinessRecordsProvider, useBusinessCollection } from '../features/business/BusinessRecordsProvider';
import { businessRecordsFixture, plannedTrade } from '../test/businessRecordsFixture';

afterEach(cleanup);
const presenter = { save: vi.fn(), preparePreview: vi.fn() };
const info: RuntimeInfo = {
  schema_version: 1, application: 'Swing Scanner', api_versions: [1], mode: 'browser', compatibility_api: '/api',
  capabilities: { scanner_workflows: true, business_records: true, report_files: true, job_output_files: true,
    legacy_credential_controls: true, native_keychain: false, native_file_dialogs: false, desktop_lifecycle: false },
  paths: { data: '/test/data', cache: '/test/cache', reports: '/test/reports', logs: '/test/logs', exports: '/test/exports' }
};

it('reads versioned runtime capabilities and rejects an incompatible schema', async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify(info)));
  const runtime = createRuntime('browser', createApiClient({ fetcher }), presenter);
  await expect(runtime.readInfo()).resolves.toEqual(info);
  fetcher.mockResolvedValueOnce(new Response(JSON.stringify({ ...info, schema_version: 2 })));
  await expect(runtime.readInfo()).rejects.toThrow('runtime contract');
  fetcher.mockResolvedValueOnce(new Response(JSON.stringify({ ...info, capabilities: {} })));
  await expect(runtime.readInfo()).rejects.toThrow('runtime contract');
});

it('gets desktop connection details from the host and keeps the bearer out of returned display configuration', async () => {
  const token = 'private-launch-token-'.repeat(3);
  const host = { configure: vi.fn(async () => ({ baseUrl: 'http://127.0.0.1:49999', bearerToken: token, mode: 'desktop' })) };
  const fetcher = vi.fn(async () => new Response(JSON.stringify(info)));
  const connected = await connectDesktop(host, true, fetcher);
  expect(host.configure).toHaveBeenCalledWith(true);
  expect(connected.config).toEqual({ baseUrl: 'http://127.0.0.1:49999', mode: 'desktop' });
  await connected.runtime.readInfo();
  expect(fetcher.mock.calls[0][1]?.headers).toMatchObject({ authorization: `Bearer ${token}` });
  expect(JSON.stringify(connected.config)).not.toContain(token);
  expect(() => connected.runtime.files.save(new Blob(['test']), 'test.csv')).toThrow('not available');
});

it.each(['http://example.invalid:8000', 'https://127.0.0.1:8000', 'http://user:password@127.0.0.1:8000', 'http://127.0.0.1:8000/?token=test', 'http://127.0.0.1:8000/path', 'http://127.0.0.1'])('refuses invalid desktop endpoint %s', async (baseUrl) => {
  await expect(connectDesktop({ configure: async () => ({ baseUrl, bearerToken: 'x'.repeat(64), mode: 'desktop' }) })).rejects.toThrow('invalid private connection');
});

it('routes existing report and credential hooks through an injected connection', async () => {
  const request = vi.fn(async (path: string) => path === '/api/reports' ? [] : { configured: true });
  const runtime = createRuntime('browser', { request, requestFile: vi.fn() }, presenter);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { result } = renderHook(() => ({ reports: useReports(), credential: useMassiveCredentialStatus() }), {
    wrapper: ({ children }) => <PlatformProvider runtime={runtime}><QueryClientProvider client={queryClient}>{children}</QueryClientProvider></PlatformProvider>
  });
  await act(async () => { await queryClient.ensureQueryData({ queryKey: ['test'], queryFn: async () => null }); });
  expect(request).toHaveBeenCalledWith('/api/reports');
  expect(request).toHaveBeenCalledWith('/api/market-data/massive/credential');
  expect(result.current).toBeDefined();
});

it('initializes business records with the same injected runtime client', async () => {
  const fixture = businessRecordsFixture({ plannedTrades: [plannedTrade] });
  const runtime = createRuntime('browser', { ...fixture.client, requestFile: vi.fn() }, presenter);
  function Journal() { const [trades] = useBusinessCollection('plannedTrades'); return <p>{trades[0]?.ticker}</p>; }
  render(<PlatformProvider runtime={runtime}><BusinessRecordsProvider><BusinessRecordsGate><Journal /></BusinessRecordsGate></BusinessRecordsProvider></PlatformProvider>);
  await screen.findByText('AAPL');
  expect(fixture.requests).toHaveLength(4);
});

it('shows resolved paths and reports failure rather than fabricated readiness', async () => {
  const runtime = createRuntime('browser', createApiClient({ fetcher: async () => new Response(JSON.stringify(info)) }), presenter);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<PlatformProvider runtime={runtime}><QueryClientProvider client={client}><RuntimeReadiness /></QueryClientProvider></PlatformProvider>);
  await screen.findByText('/test/reports');
  expect(screen.getByText('Native Keychain integration is not yet enabled.')).toBeInTheDocument();
});

it('reports a file error inline and allows a deliberate retry through the adapter', async () => {
  const runtime = createRuntime('browser', createApiClient(), presenter);
  runtime.files.downloadReport = vi.fn().mockRejectedValueOnce(new Error('Download unavailable')).mockResolvedValue(undefined);
  render(<PlatformProvider runtime={runtime}><FileActionButton reportId="opaque">Download PDF</FileActionButton></PlatformProvider>);
  fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('alert')).toHaveTextContent('Download unavailable');
  fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
  await act(async () => {});
  expect(runtime.files.downloadReport).toHaveBeenCalledTimes(2);
  expect(runtime.files.downloadReport).toHaveBeenLastCalledWith('opaque');
});
