import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createApiClient } from '../api/client';
import { browserFilePresenter, createFileActions } from './files';
import { setMigrationPaused } from '../lib/browserExport';

beforeEach(() => localStorage.clear());
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

function fixture(status = 200, mediaType = 'application/pdf') {
  const fetcher = vi.fn(async () => new Response(status === 200 ? '%PDF-fixture' : JSON.stringify({ detail: 'File not available' }), {
    status, headers: { 'Content-Type': mediaType, 'Content-Disposition': "attachment; filename*=UTF-8''R%C3%A9sum%C3%A9%20report.pdf" }
  }));
  const api = createApiClient({ baseUrl: 'http://127.0.0.1:49999', bearerToken: 'test-launch-secret', fetcher });
  const target = { show: vi.fn(), close: vi.fn() };
  const presenter = { save: vi.fn(), preparePreview: vi.fn(() => target) };
  return { api, fetcher, presenter, target, files: createFileActions(api, presenter) };
}

it('downloads a report by ID with bearer headers, a preserved Unicode filename, and no token in the URL', async () => {
  const { files, fetcher, presenter } = fixture();
  await files.downloadReport('opaque-report==');
  expect(fetcher).toHaveBeenCalledWith('http://127.0.0.1:49999/api/v1/reports/opaque-report%3D%3D/download', expect.objectContaining({
    redirect: 'error', headers: expect.objectContaining({ authorization: 'Bearer test-launch-secret' })
  }));
  expect(presenter.save).toHaveBeenCalledWith(expect.objectContaining({ size: 12, type: 'application/pdf' }), 'Résumé report.pdf');
  expect(await presenter.save.mock.calls[0][0].text()).toBe('%PDF-fixture');
  expect(fetcher.mock.calls[0][0]).not.toContain('test-launch-secret');
});

it('encodes the job identity and output label without using a repository path', async () => {
  const { files, fetcher } = fixture();
  await files.downloadJobOutput('job-id', 'scan log');
  expect(fetcher.mock.calls[0][0]).toBe('http://127.0.0.1:49999/api/v1/jobs/job-id/outputs/scan%20log/download');
});

it('reserves a preview during the click and displays only the authenticated PDF blob', async () => {
  const { files, presenter, target, fetcher } = fixture();
  const pending = files.previewReport('id');
  expect(presenter.preparePreview).toHaveBeenCalledOnce();
  await pending;
  expect(target.show).toHaveBeenCalledWith(expect.objectContaining({ size: 12, type: 'application/pdf' }));
  expect(target.close).not.toHaveBeenCalled();
  expect(fetcher.mock.calls[0][0]).toContain('/api/v1/reports/id/view');
});

it('closes a reserved preview on an API failure without showing an error response as a file', async () => {
  const { files, target } = fixture(401);
  await expect(files.previewReport('id')).rejects.toThrow('File not available');
  expect(target.close).toHaveBeenCalledOnce();
  expect(target.show).not.toHaveBeenCalled();
});

it('refuses HTML preview even if a server incorrectly returns it successfully', async () => {
  const { files, target } = fixture(200, 'text/html');
  await expect(files.previewReport('id')).rejects.toThrow('Only PDF');
  expect(target.close).toHaveBeenCalledOnce();
  expect(target.show).not.toHaveBeenCalled();
});

it('does not produce a download on HTTP failure', async () => {
  const { files, presenter } = fixture(404);
  await expect(files.downloadReport('missing')).rejects.toThrow('File not available');
  expect(presenter.save).not.toHaveBeenCalled();
});

it('sanitizes filenames and preserves Headers-instance custom headers', async () => {
  const fetcher = vi.fn(async () => new Response('data', { headers: { 'Content-Disposition': "attachment; filename*=UTF-8''..%2Fsecret%5Cpath.csv" } }));
  const client = createApiClient({ fetcher, bearerToken: 'configured-token' });
  expect((await client.requestFile('/api/v1/reports/id/download')).name).toBe('.._secret_path.csv');
  const jsonFetch = vi.fn(async () => new Response('{}'));
  await createApiClient({ fetcher: jsonFetch, bearerToken: 'configured-token' }).request('/api/health', {
    headers: new Headers({ 'X-Request': 'fixture', Authorization: 'do-not-override-runtime' }), redirect: 'follow'
  });
  expect(jsonFetch.mock.calls[0][1]).toMatchObject({ redirect: 'error', headers: { authorization: 'Bearer configured-token', 'x-request': 'fixture' } });
});

it('blocks file requests while the browser migration pause is active', async () => {
  const fetcher = vi.fn();
  const client = createApiClient({ pauseDuringBrowserBackup: true, fetcher });
  setMigrationPaused(true);
  await expect(client.requestFile('/api/v1/reports/id/download')).rejects.toMatchObject({ status: 503 });
  expect(fetcher).not.toHaveBeenCalled();
});

it('refuses absolute and non-API paths before sending credentials', async () => {
  const { api, fetcher } = fixture();
  for (const path of ['https://example.invalid/file', '//example.invalid/file', '/file', '/api/file#fragment']) {
    await expect(api.requestFile(path)).rejects.toMatchObject({ status: 400 });
  }
  expect(fetcher).not.toHaveBeenCalled();
});

it('revokes browser download URLs and does not navigate away from the app', () => {
  vi.useFakeTimers();
  URL.createObjectURL = vi.fn(() => 'blob:fixture');
  URL.revokeObjectURL = vi.fn();
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  browserFilePresenter.save(new Blob(['data']), 'report.csv');
  expect(click).toHaveBeenCalledOnce();
  expect(URL.revokeObjectURL).not.toHaveBeenCalled();
  vi.advanceTimersByTime(1000);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fixture');
});

it('reports popup blocking and disconnects a preview from its opener', () => {
  const popup = vi.spyOn(window, 'open').mockReturnValueOnce(null);
  expect(() => browserFilePresenter.preparePreview()).toThrow('Allow a popup');
  const target = { opener: window, closed: false, close: vi.fn(), location: { replace: vi.fn() } };
  popup.mockReturnValueOnce(target as unknown as Window);
  browserFilePresenter.preparePreview();
  expect(target.opener).toBeNull();
});
