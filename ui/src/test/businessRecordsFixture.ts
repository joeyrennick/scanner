import { ApiError } from '../api/client';
import { collections, type BusinessData, type Collection, type RecordTypes } from '../lib/businessRecords';

export function businessRecordsFixture(initial: Partial<BusinessData> = {}) {
  const rows = new Map<string, { record: RecordTypes[Collection] | null; revision: number; updated_at: string | null }>();
  for (const collection of collections) for (const record of initial[collection] ?? []) {
    rows.set(`${collection}/${record.id}`, { record, revision: 1, updated_at: 'fixture' });
  }
  const requests: { path: string; init?: RequestInit }[] = [];
  let beforeRequest: ((path: string, init?: RequestInit) => Promise<void>) | undefined;
  const client = { async request<T>(path: string, init?: RequestInit): Promise<T> {
    requests.push({ path, init });
    await beforeRequest?.(path, init);
    const [raw, query] = path.replace('/api/v1/business-records/', '').split('?');
    const [collection, encoded] = raw.split('/') as [Collection, string | undefined];
    if (!encoded) return {
      schema_version: 1, collection,
      records: [...rows.entries()].filter(([key, row]) => key.startsWith(`${collection}/`) && row.record).map(([, row]) => row)
    } as T;
    const key = `${collection}/${decodeURIComponent(encoded)}`;
    const current = rows.get(key) ?? { record: null, revision: 0, updated_at: null };
    if (!init?.method || init.method === 'GET') return current as T;
    if (init.method === 'DELETE') {
      if (!current.record || current.revision !== Number(new URLSearchParams(query).get('expected_revision'))) throw new ApiError(409, 'conflict');
      rows.set(key, { record: null, revision: current.revision + 1, updated_at: null });
      return { deleted: true, revision: current.revision + 1 } as T;
    }
    const body = JSON.parse(String(init.body));
    if (body.expected_revision !== current.revision) throw new ApiError(409, 'conflict');
    const next = { record: body.record, revision: current.revision + 1, updated_at: 'fixture' };
    rows.set(key, next);
    return next as T;
  } };
  return { client, rows, requests, intercept: (callback: typeof beforeRequest) => { beforeRequest = callback; } };
}

export const candidate = { id: 'AAPL', entry: '100', stop: '95', target: '115' };
export const plannedTrade = { ...candidate, ticker: 'AAPL', strategy: 'pullback', plannedAt: '2026-09-12', status: 'planned' as const };
