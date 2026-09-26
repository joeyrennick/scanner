import { createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { BusinessRecordsStore, type Collection, type RecordTypes, type Update } from '../../lib/businessRecords';
import { usePlatform } from '../../platform/PlatformProvider';

const StoreContext = createContext<BusinessRecordsStore | null>(null);

export function useBusinessStore() {
  const store = useContext(StoreContext);
  if (!store) throw new Error('Business records require the application data provider.');
  return store;
}

export function BusinessRecordsProvider({ children, store: supplied }: { children: ReactNode; store?: BusinessRecordsStore }) {
  const { api, files } = usePlatform();
  const [downloadError, setDownloadError] = useState('');
  const [store] = useState(() => supplied ?? new BusinessRecordsStore(api));
  const snapshot = useSyncExternalStore(store.subscribe, store.getSnapshot);
  useEffect(() => {
    if (!snapshot.pending && !snapshot.saveError) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [snapshot.pending, snapshot.saveError]);

  async function downloadDraft() {
    setDownloadError('');
    const blob = new Blob([JSON.stringify({
      format: 'swing-scanner.unsaved-draft', version: 1,
      capturedAt: new Date().toISOString(), collections: snapshot.data,
      warning: 'Review against the database before restoring. Some edits may already have been saved.'
    }, null, 2)], { type: 'application/json' });
    try { await files.save(blob, `scanner-unsaved-draft-${Date.now()}.json`); }
    catch (error) {
      setDownloadError(`Draft download failed. Keep this window open; your draft is still here. ${error instanceof Error ? error.message : ''}`);
    }
  }

  return <StoreContext.Provider value={store}>
    {snapshot.saveError ? <main className="business-records-gate">
      <h1>Saved records need attention</h1>
      <p role="alert">{snapshot.saveError}</p>
      <p>Download your draft before reloading. Reloading discards unconfirmed edits and reads the database again; it does not retry or overwrite anything.</p>
      <button onClick={downloadDraft}>Download draft for review</button>{' '}
      {downloadError && <p role="alert">{downloadError}</p>}
      <button onClick={() => {
        if (window.confirm('Discard the unconfirmed draft and reload saved records? Download a copy first if you need to keep your edits.')) {
          void store.discardDraftAndReload();
        }
      }}>Discard draft and reload saved records</button>
    </main> : <>
      {snapshot.pending > 0 && <div className="business-save-status" role="status">Saving {snapshot.pending} change{snapshot.pending === 1 ? '' : 's'} to the database… Keep this window open.</div>}
      {children}
    </>}
  </StoreContext.Provider>;
}

export function BusinessRecordsGate({ children }: { children: ReactNode }) {
  const store = useBusinessStore();
  const snapshot = useSyncExternalStore(store.subscribe, store.getSnapshot);
  useEffect(() => { if (store.getSnapshot().phase === 'idle') void store.load(); }, [store]);
  if (snapshot.phase === 'ready') return <>{children}</>;
  return <main className="business-records-gate">
    <h1>{snapshot.phase === 'failed' ? 'Saved records are unavailable' : 'Loading saved records…'}</h1>
    {snapshot.loadError && <p role="alert">{snapshot.loadError}</p>}
    <p>The Scanner will not open with empty records while the database is unavailable. Original browser records remain untouched.</p>
    {snapshot.phase === 'failed' && <button onClick={() => { void store.load(); }}>Retry connection</button>}
  </main>;
}

export function useBusinessCollection<K extends Collection>(collection: K) {
  const store = useBusinessStore();
  const snapshot = useSyncExternalStore(store.subscribe, store.getSnapshot);
  const update = useCallback((next: Update<RecordTypes[K][]>) => store.update(collection, next), [store, collection]);
  return [snapshot.data[collection], update] as const;
}

export function useSavedSetting<T extends Record<string, string | number | boolean>>(id: string, defaults: T) {
  const [records, update] = useBusinessCollection('browserSettings');
  const values = records.find((record) => record.id === id)?.values;
  const setting = useMemo(() => ({ ...defaults, ...values }) as T, [defaults, values]);
  const setSetting = useCallback((next: Update<T>) => {
    update((current) => {
      const previous = current.find((record) => record.id === id);
      const merged = { ...defaults, ...previous?.values } as T;
      const values = typeof next === 'function' ? next(merged) : next;
      const record = { id, values: { ...previous?.values, ...values } };
      return [...current.filter((item) => item.id !== id), record];
    });
  }, [defaults, id, update]);
  return [setting, setSetting] as const;
}
