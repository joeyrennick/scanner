import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { checkImportedBrowserRecords, resumeImportedBrowserRecords } from './businessMigration';
import { isMigrationPaused, setMigrationPaused } from './browserExport';
import { businessRecordsFixture, plannedTrade } from '../test/businessRecordsFixture';
import type { BusinessData } from './businessRecords';

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('crypto', webcrypto);
  localStorage.setItem('planned-trades', JSON.stringify([plannedTrade]));
  setMigrationPaused(true);
});
afterEach(() => vi.unstubAllGlobals());

function fixture(options: { imported?: boolean; origin?: string; data?: Partial<BusinessData> } = {}) {
  const store = businessRecordsFixture(options.data ?? { plannedTrades: [plannedTrade] });
  const status = {
    schema_version: 1, imported: options.imported ?? true, import_id: 'fixture-import',
    browser_origin: options.origin ?? window.location.origin,
    imported_counts: { plannedTrades: 1, candidateEdits: 0, valuationAssumptions: 0, browserSettings: 0 }
  };
  return { ...store, client: { request: async <T,>(path: string, init?: RequestInit): Promise<T> =>
    path.endsWith('/migration-status') ? status as T : store.client.request<T>(path, init) } };
}

it('checks exact records read-only, retaining the pause and original browser keys', async () => {
  const server = fixture();
  const original = localStorage.getItem('planned-trades');
  const result = await checkImportedBrowserRecords(server.client);
  expect(result.counts.plannedTrades).toBe(1);
  expect(isMigrationPaused()).toBe(true);
  expect(localStorage.getItem('planned-trades')).toBe(original);
  expect(server.requests.every(({ init }) => !init?.method)).toBe(true);
});

it('resumes only after rechecking, recording identity and a digest rather than business records', async () => {
  await resumeImportedBrowserRecords(fixture().client);
  expect(isMigrationPaused()).toBe(false);
  const marker = JSON.parse(localStorage.getItem('swing-scanner.business-source.v1')!);
  expect(marker).toEqual({ importId: 'fixture-import', origin: window.location.origin, legacySha256: expect.stringMatching(/^[0-9a-f]{64}$/) });
  expect(localStorage.getItem('planned-trades')).toBe(JSON.stringify([plannedTrade]));
});

it('rejects an unimported or wrong-origin backend and leaves editing paused', async () => {
  await expect(resumeImportedBrowserRecords(fixture({ imported: false }).client)).rejects.toThrow('completed import');
  await expect(resumeImportedBrowserRecords(fixture({ origin: 'http://127.0.0.1:5173' }).client)).rejects.toThrow('original Scanner browser address');
  expect(isMigrationPaused()).toBe(true);
  expect(localStorage.getItem('swing-scanner.business-source.v1')).toBeNull();
});

it('rejects equal counts with different records and rechecks after a successful review', async () => {
  await checkImportedBrowserRecords(fixture().client);
  const changed = fixture({ data: { plannedTrades: [{ ...plannedTrade, entry: '999' }] } });
  await expect(resumeImportedBrowserRecords(changed.client)).rejects.toThrow('do not exactly match');
  expect(isMigrationPaused()).toBe(true);
});

it('permits later database edits after a verified switch without re-importing old browser data', async () => {
  await resumeImportedBrowserRecords(fixture().client);
  setMigrationPaused(true);
  const changed = fixture({ data: { plannedTrades: [{ ...plannedTrade, entry: '120' }] } });
  await expect(checkImportedBrowserRecords(changed.client)).resolves.toMatchObject({ counts: { plannedTrades: 1 } });
  expect(localStorage.getItem('planned-trades')).toBe(JSON.stringify([plannedTrade]));
});

it('detects legacy writes after the verified switch and refuses to hide them', async () => {
  await resumeImportedBrowserRecords(fixture().client);
  setMigrationPaused(true);
  localStorage.setItem('planned-trades', JSON.stringify([{ ...plannedTrade, entry: '110' }]));
  await expect(resumeImportedBrowserRecords(fixture().client)).rejects.toThrow('changed after the database switch');
  expect(isMigrationPaused()).toBe(true);
});

it('detects browser changes during the import check', async () => {
  const server = fixture();
  server.intercept(async () => { localStorage.setItem('planned-trades', JSON.stringify([{ ...plannedTrade, entry: '110' }])); });
  await expect(checkImportedBrowserRecords(server.client)).rejects.toThrow('changed during the check');
  expect(isMigrationPaused()).toBe(true);
});
