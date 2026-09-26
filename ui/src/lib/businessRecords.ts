import { ApiError, apiClient } from '../api/client';

export type PlannedTrade = {
  id: string; ticker: string; strategy: string; plannedAt: string;
  entry: string; stop: string; target: string; status: 'planned';
};
export type CandidateLevels = { id: string; entry: string; stop: string; target: string };
export type RecordTypes = {
  plannedTrades: PlannedTrade;
  candidateEdits: CandidateLevels;
  valuationAssumptions: { id: string; assumptions: Record<string, number> };
  browserSettings: { id: string; values: Record<string, string | number | boolean> };
};
export type Collection = keyof RecordTypes;
export const collections: Collection[] = ['plannedTrades', 'candidateEdits', 'valuationAssumptions', 'browserSettings'];
export type BusinessData = { [K in Collection]: RecordTypes[K][] };
type BusinessRecord = RecordTypes[Collection];
type Envelope = { record: BusinessRecord | null; revision: number; updated_at: string | null };
type Operation = { collection: Collection; id: string; record: BusinessRecord | null };
export type Update<T> = T | ((current: T) => T);
type Client = Pick<typeof apiClient, 'request'>;

function emptyData(): BusinessData {
  return { plannedTrades: [], candidateEdits: [], valuationAssumptions: [], browserSettings: [] };
}

// Object key order is not a business change. Array order remains significant.
export function canonicalJson(value: unknown): string {
  return JSON.stringify(value, (_key, item) => {
    if (typeof item === 'number' && !Number.isFinite(item)) throw new Error('A saved number must be finite.');
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]]));
    }
    return item;
  });
}

function validateEnvelope(value: Envelope) {
  if (!value || !Number.isSafeInteger(value.revision) || value.revision < 0
      || (value.record !== null && (!value.record || typeof value.record.id !== 'string' || value.revision < 1))) {
    throw new Error('Unsupported business-record response. Editing has been stopped.');
  }
}

export async function readBusinessData(client: Client): Promise<{ data: BusinessData; revisions: Map<string, number> }> {
  const data = emptyData();
  const revisions = new Map<string, number>();
  await Promise.all(collections.map(async (collection) => {
    const response = await client.request<{ schema_version: number; collection: string; records: Envelope[] }>(
      `/api/v1/business-records/${collection}`
    );
    if (response.schema_version !== 1 || response.collection !== collection || !Array.isArray(response.records)) {
      throw new Error('The backend does not support version 1 business records.');
    }
    const records = response.records.map((envelope) => {
      validateEnvelope(envelope);
      if (!envelope.record) throw new Error('A listed business record is missing.');
      const key = recordKey(collection, envelope.record.id);
      if (revisions.has(key)) throw new Error('The backend returned duplicate business records.');
      revisions.set(key, envelope.revision);
      return envelope.record;
    });
    (data[collection] as BusinessRecord[]) = records;
  }));
  return { data, revisions };
}

const recordKey = (collection: Collection, id: string) => JSON.stringify([collection, id]);
const recordPath = (collection: Collection, id: string) => `/api/v1/business-records/${collection}/${encodeURIComponent(id)}`;

/** One shared optimistic draft, with serialized revision-checked writes across routes.
 * A lost response is NOT retried: it may have committed. Freeze and let the user
 * preserve the draft, then explicitly reload. Original localStorage is never used.
 */
export class BusinessRecordsStore {
  private listeners = new Set<() => void>();
  private revisions = new Map<string, number>();
  private queue: Operation[] = [];
  private loading: Promise<void> | null = null;
  private saving: Promise<void> | null = null;
  private snapshot = {
    phase: 'idle' as 'idle' | 'loading' | 'ready' | 'failed',
    data: emptyData(), pending: 0, loadError: '', saveError: ''
  };

  constructor(private client: Client = apiClient) {}
  getSnapshot = () => this.snapshot;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  private publish(patch: Partial<typeof this.snapshot>) {
    this.snapshot = { ...this.snapshot, ...patch };
    this.listeners.forEach((listener) => listener());
  }

  load = (): Promise<void> => {
    if (this.loading) return this.loading;
    if (this.snapshot.pending || this.snapshot.saveError) return Promise.resolve();
    this.publish({ phase: 'loading', loadError: '' });
    this.loading = readBusinessData(this.client).then(({ data, revisions }) => {
      this.revisions = revisions;
      this.publish({ data, phase: 'ready' });
    }).catch((error: unknown) => {
      this.publish({ phase: 'failed', loadError: error instanceof Error ? error.message : 'Could not load saved records.' });
    }).finally(() => { this.loading = null; });
    return this.loading;
  };

  update<K extends Collection>(collection: K, update: Update<RecordTypes[K][]>) {
    if (this.snapshot.phase !== 'ready' || this.snapshot.saveError) return;
    const previous = this.snapshot.data[collection];
    // Do not expose the shared draft to an updater that might mutate it in place.
    const copy = JSON.parse(canonicalJson(previous)) as RecordTypes[K][];
    const next = JSON.parse(canonicalJson(typeof update === 'function' ? update(copy) : update)) as RecordTypes[K][];
    const before = new Map(previous.map((record) => [record.id, record]));
    const after = new Map(next.map((record) => [record.id, record]));
    if (after.size !== next.length) throw new Error('Duplicate business record IDs.');
    const operations: Operation[] = [];
    for (const [id, record] of after) {
      if (canonicalJson(before.get(id)) !== canonicalJson(record)) operations.push({ collection, id, record });
    }
    for (const id of before.keys()) if (!after.has(id)) operations.push({ collection, id, record: null });
    if (!operations.length) return;
    this.queue.push(...operations);
    this.publish({ data: { ...this.snapshot.data, [collection]: next }, pending: this.queue.length });
    this.startSaving();
  }

  private startSaving() {
    if (this.saving || !this.queue.length || this.snapshot.saveError) return;
    this.saving = this.drain().finally(() => {
      this.saving = null;
      // A subscriber may enqueue an edit as the final confirmation is published.
      this.startSaving();
    });
  }

  private async drain() {
    while (this.queue.length) {
      const operation = this.queue[0];
      const { collection, id, record } = operation;
      const key = recordKey(collection, id);
      const path = recordPath(collection, id);
      try {
        let revision = this.revisions.get(key);
        if (revision === undefined) {
          // An absent row can have a deletion tombstone. Never assume revision 0.
          const current = await this.client.request<Envelope>(path);
          validateEnvelope(current);
          if (current.record !== null) throw new ApiError(409, 'This record was created in another window.');
          revision = current.revision;
        }
        if (record) {
          const saved = await this.client.request<Envelope>(path, {
            method: 'PUT', body: JSON.stringify({ record, expected_revision: revision })
          });
          validateEnvelope(saved);
          if (saved.revision !== revision + 1 || canonicalJson(saved.record) !== canonicalJson(record)) {
            throw new Error('The save response could not be verified.');
          }
          this.revisions.set(key, saved.revision);
        } else {
          const saved = await this.client.request<{ deleted: boolean; revision: number }>(
            `${path}?expected_revision=${revision}`, { method: 'DELETE' }
          );
          if (saved.deleted !== true || saved.revision !== revision + 1) throw new Error('The deletion response could not be verified.');
          this.revisions.set(key, saved.revision);
        }
        this.queue.shift();
        this.publish({ pending: this.queue.length });
      } catch (error) {
        const detail = error instanceof ApiError && error.status === 409
          ? 'A record changed in another window. Your edit was not used to overwrite it.'
          : 'A save could not be confirmed. Some earlier changes may already be saved.';
        this.publish({ saveError: `${detail} Editing has stopped; your draft is still available below.` });
        return;
      }
    }
  }

  async flush() {
    while (this.saving) await this.saving;
    if (this.snapshot.saveError) throw new Error(this.snapshot.saveError);
  }

  async discardDraftAndReload() {
    await this.saving;
    this.queue = [];
    this.publish({ phase: 'idle', pending: 0, saveError: '' });
    await this.load();
  }
}
