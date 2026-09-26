import { beforeEach, expect, it } from 'vitest';
import { BusinessRecordsStore, canonicalJson, collections } from './businessRecords';
import { businessRecordsFixture, candidate, plannedTrade } from '../test/businessRecordsFixture';
import { createApiClient } from '../api/client';
import { setMigrationPaused } from './browserExport';

beforeEach(() => localStorage.clear());

it('loads all four collections, never reads or overwrites legacy business storage, and never writes on hydration', async () => {
  localStorage.setItem('planned-trades', '["legacy-only"]');
  const data = { plannedTrades: [plannedTrade], candidateEdits: [candidate],
    valuationAssumptions: [{ id: 'AAPL', assumptions: { discount_rate: 0.1 } }],
    browserSettings: [{ id: 'swing-scanner.display-settings', values: { minFiveDayRange: 14 } }] };
  const fixture = businessRecordsFixture(data);
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  expect(store.getSnapshot().data).toEqual(data);
  expect(fixture.requests).toHaveLength(4);
  expect(fixture.requests.every(({ init }) => !init?.method)).toBe(true);
  expect(localStorage.getItem('planned-trades')).toBe('["legacy-only"]');
});

it('deduplicates concurrent initial loads and refuses writes before all records load', async () => {
  const fixture = businessRecordsFixture();
  const store = new BusinessRecordsStore(fixture.client);
  const first = store.load();
  store.update('candidateEdits', [candidate]);
  expect(store.load()).toBe(first);
  await first;
  expect(fixture.requests).toHaveLength(4);
  expect(store.getSnapshot().data.candidateEdits).toEqual([]);
});

it('keeps rapid edits in order using each confirmed revision and survives a reload', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  for (const entry of ['101', '102', '103']) store.update('candidateEdits', (rows) => rows.map((row) => ({ ...row, entry })));
  expect(store.getSnapshot().data.candidateEdits[0].entry).toBe('103');
  expect(store.getSnapshot().pending).toBe(3);
  await store.flush();
  expect(fixture.requests.filter(({ init }) => init?.method === 'PUT').map(({ init }) => JSON.parse(String(init?.body)).expected_revision)).toEqual([1, 2, 3]);
  const reopened = new BusinessRecordsStore(fixture.client);
  await reopened.load();
  expect(reopened.getSnapshot().data.candidateEdits[0].entry).toBe('103');
  expect(store.getSnapshot().pending).toBe(0);
});

it('uses a tombstone when re-creating a deleted record, including after relaunch', async () => {
  const fixture = businessRecordsFixture({ plannedTrades: [plannedTrade] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  store.update('plannedTrades', []);
  await store.flush();
  const reopened = new BusinessRecordsStore(fixture.client);
  await reopened.load();
  reopened.update('plannedTrades', [plannedTrade]);
  await reopened.flush();
  expect(fixture.rows.get('plannedTrades/AAPL')?.revision).toBe(3);
});

it('supports deletion and immediate re-creation before the deletion confirms', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  store.update('candidateEdits', []);
  store.update('candidateEdits', [{ ...candidate, target: '120' }]);
  await store.flush();
  expect(fixture.rows.get('candidateEdits/AAPL')).toMatchObject({ revision: 3, record: { target: '120' } });
});

it('stops the queue on a conflict, retains all drafts, and never retries or overwrites the other edit', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  fixture.rows.set('candidateEdits/AAPL', { record: { ...candidate, entry: '150' }, revision: 2, updated_at: 'other-client' });
  store.update('candidateEdits', [{ ...candidate, entry: '101' }]);
  store.update('plannedTrades', [plannedTrade]);
  await expect(store.flush()).rejects.toThrow('another window');
  await store.load();
  store.update('candidateEdits', []);
  expect(store.getSnapshot().data.candidateEdits[0].entry).toBe('101');
  expect(store.getSnapshot().data.plannedTrades).toEqual([plannedTrade]);
  expect(fixture.rows.get('candidateEdits/AAPL')?.record).toMatchObject({ entry: '150' });
  expect(fixture.requests.filter(({ init }) => init?.method === 'PUT')).toHaveLength(1);
  await store.discardDraftAndReload();
  expect(store.getSnapshot()).toMatchObject({ pending: 0, saveError: '' });
  expect(store.getSnapshot().data.candidateEdits[0].entry).toBe('150');
  expect(store.getSnapshot().data.plannedTrades).toEqual([]);
});

it('does not overwrite a record created in another window after the initial load', async () => {
  const fixture = businessRecordsFixture();
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  fixture.rows.set('candidateEdits/AAPL', { record: candidate, revision: 1, updated_at: 'other-client' });
  store.update('candidateEdits', [{ ...candidate, entry: '102' }]);
  await expect(store.flush()).rejects.toThrow('another window');
  expect(fixture.requests.some(({ init }) => init?.method === 'PUT')).toBe(false);
});

it('retains the draft on an ambiguous network failure and does not automatically retry', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  fixture.intercept(async (_path, init) => { if (init?.method === 'PUT') throw new TypeError('Network connection lost'); });
  store.update('candidateEdits', [{ ...candidate, entry: '102' }]);
  await expect(store.flush()).rejects.toThrow('could not be confirmed');
  expect(store.getSnapshot().data.candidateEdits[0].entry).toBe('102');
  expect(fixture.requests.filter(({ init }) => init?.method === 'PUT')).toHaveLength(1);
});

it('ignores object key reordering without emitting writes', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  store.update('candidateEdits', [{ target: '115', stop: '95', entry: '100', id: 'AAPL' }]);
  await store.flush();
  expect(fixture.requests).toHaveLength(4);
  expect(canonicalJson({ b: 2, a: 1 })).toBe(canonicalJson({ a: 1, b: 2 }));
});

it('blocks loading when any collection fails or has an unsupported API schema', async () => {
  for (const collection of collections) {
    const fixture = businessRecordsFixture();
    const store = new BusinessRecordsStore({ request: async <T,>(path: string): Promise<T> =>
      path.endsWith(collection) ? { schema_version: 2 } as T : fixture.client.request<T>(path) });
    await store.load();
    expect(store.getSnapshot().phase).toBe('failed');
    store.update('plannedTrades', [plannedTrade]);
    expect(store.getSnapshot().pending).toBe(0);
  }
});

it('does not lose an edit enqueued by a final-save subscriber', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  let added = false;
  store.subscribe(() => {
    if (!added && store.getSnapshot().pending === 0) {
      added = true;
      store.update('plannedTrades', [plannedTrade]);
    }
  });
  store.update('candidateEdits', [{ ...candidate, entry: '104' }]);
  await store.flush();
  expect(fixture.rows.get('plannedTrades/AAPL')?.record).toEqual(plannedTrade);
});

it('stops mutations if the browser pause is set after loading', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const client = createApiClient({ pauseDuringBrowserBackup: true, fetcher: async (path, init) =>
    new Response(JSON.stringify(await fixture.client.request(String(path), init))) });
  const store = new BusinessRecordsStore(client);
  await store.load();
  setMigrationPaused(true);
  store.update('candidateEdits', [{ ...candidate, entry: '104' }]);
  await expect(store.flush()).rejects.toThrow('could not be confirmed');
  expect(fixture.requests.some(({ init }) => init?.method === 'PUT')).toBe(false);
});
