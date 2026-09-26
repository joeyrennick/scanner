// @vitest-environment node
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { createInterface } from 'node:readline';
import { expect, it } from 'vitest';
import { createApiClient } from '../api/client';
import { loadSetup, saveSetup } from '../api/setup';
import { createRuntime } from '../platform/runtime';
import { BusinessRecordsStore } from './businessRecords';
import { candidate, plannedTrade } from '../test/businessRecordsFixture';

async function bridge(root: string) {
  const repository = resolve(process.cwd(), '..');
  const child = spawn(process.env.SCANNER_TEST_PYTHON ?? resolve(repository, '.venv313/bin/python'), ['tests/support/browser_api_bridge.py', root], {
    cwd: repository, env: { ...process.env, PYTHONPATH: resolve(repository, 'src') }, stdio: ['pipe', 'pipe', 'pipe']
  });
  let nextId = 0;
  let errors = '';
  const pending = new Map<number, { resolve: (value: unknown) => void; reject: (reason: Error) => void }>();
  let ready!: () => void;
  let failed!: (reason: Error) => void;
  const started = new Promise<void>((resolve, reject) => { ready = resolve; failed = reject; });
  const exited = new Promise<void>((resolve) => child.on('exit', () => {
    const error = new Error(`Test API process exited: ${errors}`);
    failed(error);
    pending.forEach(({ reject }) => reject(error));
    resolve();
  }));
  child.on('error', failed);
  child.stderr.on('data', (data) => { errors += String(data); });
  createInterface({ input: child.stdout }).on('line', (line) => {
    const result = JSON.parse(line);
    if (result.ready) { ready(); return; }
    const request = pending.get(result.id);
    pending.delete(result.id);
    request?.resolve(result);
  });
  await started;
  return {
    client: createApiClient({ fetcher: (path, init) => new Promise<Response>((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve: (value) => {
        const response = value as { content: string; status: number; headers: Record<string, string> };
        resolve(new Response(Buffer.from(response.content, 'base64'), { status: response.status, headers: response.headers }));
      }, reject });
      child.stdin.write(`${JSON.stringify({ id, path: String(path), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined })}\n`);
    }) }),
    close: async () => {
      child.stdin.end();
      const timeout = setTimeout(() => child.kill('SIGTERM'), 3000);
      await exited;
      clearTimeout(timeout);
    }
  };
}

it('persists all UI collections through the real API, restarts SQLite, and rejects cross-window conflicts', async () => {
  const root = await mkdtemp(resolve(tmpdir(), 'scanner-ui-api-test-'));
  let api: Awaited<ReturnType<typeof bridge>> | undefined;
  try {
    api = await bridge(root);
    const initialSetup = await loadSetup(api.client);
    expect(initialSetup.configuration.revision).toBe(0);
    const savedSetup = await saveSetup(api.client, { application_name: 'Scanner integration test', contact_email: 'test@example.com' }, 0);
    expect(savedSetup.configuration.revision).toBe(1);
    const store = new BusinessRecordsStore(api.client);
    await store.load();
    expect(store.getSnapshot().phase).toBe('ready');
    const data = {
      plannedTrades: [plannedTrade], candidateEdits: [candidate],
      valuationAssumptions: [{ id: 'AAPL', assumptions: { discount_rate: 0.11 } }],
      browserSettings: [{ id: 'swing-scanner.display-settings', values: { minFiveDayRange: 14 } }]
    };
    store.update('plannedTrades', data.plannedTrades);
    store.update('candidateEdits', data.candidateEdits);
    store.update('valuationAssumptions', data.valuationAssumptions);
    store.update('browserSettings', data.browserSettings);
    await store.flush();
    const downloaded: { blob: Blob; name: string }[] = [];
    const runtime = createRuntime('browser', api.client, {
      save: (blob, name) => { downloaded.push({ blob, name }); },
      preparePreview: () => { throw new Error('No UI preview in transport test'); }
    });
    expect((await runtime.readInfo()).capabilities.report_files).toBe(true);
    await runtime.files.downloadReport(Buffer.from('Résumé report.pdf').toString('base64').replace(/\+/g, '-').replace(/\//g, '_'));
    expect(downloaded[0].name).toBe('Résumé report.pdf');
    expect(await downloaded[0].blob.text()).toBe('%PDF-fixture-from-python');
    await api.close();
    api = await bridge(root);
    expect((await loadSetup(api.client)).configuration).toEqual(savedSetup.configuration);
    await expect(saveSetup(api.client, { application_name: 'Stale test', contact_email: 'test@example.com' }, 0)).rejects.toThrow('another window');
    const reopened = new BusinessRecordsStore(api.client);
    const otherWindow = new BusinessRecordsStore(api.client);
    await Promise.all([reopened.load(), otherWindow.load()]);
    expect(reopened.getSnapshot().data).toEqual(data);
    reopened.update('candidateEdits', [{ ...candidate, entry: '110' }]);
    await reopened.flush();
    otherWindow.update('candidateEdits', [{ ...candidate, entry: '120' }]);
    await expect(otherWindow.flush()).rejects.toThrow('another window');
    expect(otherWindow.getSnapshot().data.candidateEdits[0].entry).toBe('120');
    await otherWindow.discardDraftAndReload();
    expect(otherWindow.getSnapshot().data.candidateEdits[0].entry).toBe('110');
    reopened.update('plannedTrades', []);
    await reopened.flush();
    const afterDelete = new BusinessRecordsStore(api.client);
    await afterDelete.load();
    afterDelete.update('plannedTrades', [plannedTrade]);
    await afterDelete.flush();
    expect(await api.client.request('/api/v1/business-records/plannedTrades/AAPL')).toMatchObject({ revision: 3, record: plannedTrade });
  } finally {
    await api?.close();
    await rm(root, { recursive: true });
  }
}, 30000);
