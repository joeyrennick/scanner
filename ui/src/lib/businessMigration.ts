import { createApiClient } from '../api/client';
import { createBrowserExport, isMigrationPaused, setMigrationPaused } from './browserExport';
import { canonicalJson, collections, readBusinessData, type BusinessData, type Collection } from './businessRecords';

const sourceKey = 'swing-scanner.business-source.v1';
type ImportStatus = {
  schema_version: number; imported: boolean; import_id: string;
  browser_origin: string; imported_counts: Record<Collection, number>;
};

function sorted(data: BusinessData) {
  return Object.fromEntries(collections.map((name) => [name,
    [...data[name]].sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
  ]));
}

export async function checkImportedBrowserRecords(client = createApiClient()) {
  if (!isMigrationPaused()) throw new Error('Pause editing before checking the import.');
  // This client is used ONLY for these GETs while paused. Normal API calls remain blocked.
  const original = JSON.parse((await createBrowserExport()).payloadJson).collections as BusinessData;
  const legacyJson = canonicalJson(sorted(original));
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(legacyJson));
  const legacySha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  const status = await client.request<ImportStatus>('/api/v1/business-records/migration-status');
  if (status.schema_version !== 1 || status.imported !== true || !status.import_id) {
    throw new Error('A completed import was not found. Keep editing paused.');
  }
  if (status.browser_origin !== window.location.origin) {
    throw new Error(`Use the original Scanner browser address (${status.browser_origin}) to confirm this import.`);
  }
  const { data } = await readBusinessData(client);
  const marker = localStorage.getItem(sourceKey);
  const previous = marker ? JSON.parse(marker) : null;
  if (previous?.importId === status.import_id && previous?.origin === status.browser_origin) {
    if (previous.legacySha256 !== legacySha256) throw new Error('Original browser records changed after the database switch. Keep editing paused for review.');
  } else {
    if (collections.some((name) => status.imported_counts?.[name] !== original[name].length)
        || canonicalJson(sorted(data)) !== legacyJson) {
      throw new Error('Imported records do not exactly match the original browser records. Keep editing paused for review.');
    }
  }
  const after = JSON.parse((await createBrowserExport()).payloadJson).collections as BusinessData;
  if (canonicalJson(sorted(after)) !== legacyJson) throw new Error('Browser records changed during the check. Keep editing paused.');
  return {
    importId: status.import_id, origin: status.browser_origin, legacySha256,
    counts: Object.fromEntries(collections.map((name) => [name, data[name].length])) as Record<Collection, number>
  };
}

export async function resumeImportedBrowserRecords(client = createApiClient()) {
  // Check again at the actual switch, not only when the review button was pressed.
  const verified = await checkImportedBrowserRecords(client);
  localStorage.setItem(sourceKey, JSON.stringify({
    importId: verified.importId, origin: verified.origin, legacySha256: verified.legacySha256
  }));
  setMigrationPaused(false);
}
