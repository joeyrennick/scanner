export const migrationPauseKey = 'swing-scanner.migration.pause.v1';
const businessKeys = [
  'planned-trades',
  'swing-scanner.candidates.chart-state',
  'swing-scanner.fundamentals.v1'
] as const;
const settingsFields: Record<string, Record<string, 'number' | 'string' | 'boolean'>> = {
  'swing-scanner.recommendation-settings': { rewardRiskMultiple: 'number', suggestedHoldDays: 'number', stopMethod: 'string', atrPeriod: 'number', riskPerTradePercent: 'number', defaultExportScope: 'string', includeAdjustedChecklistValues: 'boolean' },
  'swing-scanner.cache-settings': { historyPeriod: 'string', staleAfterDays: 'number', batchSize: 'number', batchDelayMs: 'number', stopOnRateLimit: 'boolean' },
  'swing-scanner.market-data-settings.v2': { primaryProvider: 'string', backupProvider: 'string', requestMode: 'string', maxProviderBatches: 'number', testSymbol: 'string' },
  'swing-scanner.appearance-settings': { density: 'string', tablePageSize: 'number', defaultChartRange: 'string', rememberChartResize: 'boolean' },
  'swing-scanner.display-settings': { minStopDistancePercent: 'number', minFiveDayRange: 'number' }
};
const exportKeys = [...businessKeys, ...Object.keys(settingsFields)];
export const maxExportBytes = 5 * 1024 * 1024;

export function isMigrationPaused() {
  return localStorage.getItem(migrationPauseKey) !== null;
}

export function setMigrationPaused(paused: boolean) {
  if (paused) localStorage.setItem(migrationPauseKey, '1');
  else localStorage.removeItem(migrationPauseKey);
  window.dispatchEvent(new Event('scanner-migration-pause'));
}

export function subscribeMigrationPause(callback: () => void) {
  window.addEventListener('storage', callback);
  window.addEventListener('scanner-migration-pause', callback);
  return () => {
    window.removeEventListener('storage', callback);
    window.removeEventListener('scanner-migration-pause', callback);
  };
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('A saved browser record is malformed. Its original data has been retained.');
  }
  return value as Record<string, unknown>;
}

function string(value: unknown, field: string, limit = 2000): string {
  if (typeof value !== 'string' || value.length > limit) {
    throw new Error(`Invalid ${field} in saved browser data. The original data has been retained.`);
  }
  return value;
}

function id(value: unknown): string {
  const result = string(value, 'record ID', 128);
  if (!result.trim()) throw new Error('A saved browser record has an empty ID.');
  return result;
}

function parse(raw: string | null, fallback: unknown): unknown {
  if (raw === null) return fallback;
  try { return JSON.parse(raw); }
  catch { throw new Error('Saved browser data contains invalid JSON. Its original data has been retained.'); }
}

export function readBrowserBusinessData(raw: (string | null)[]) {
  if (raw.reduce((total, item) => total + (item?.length ?? 0), 0) > maxExportBytes) {
    throw new Error('Browser export exceeds the 5 MB limit.');
  }
  const planned = parse(raw[0], []);
  if (!Array.isArray(planned) || planned.length > 10000) throw new Error('Invalid Planned Trades collection.');
  const seen = new Set<string>();
  const plannedTrades = planned.map((value) => {
    const row = object(value);
    const recordId = id(row.id);
    if (seen.has(recordId)) throw new Error('Duplicate Planned Trade IDs need review before export.');
    seen.add(recordId);
    if (row.status !== 'planned') throw new Error('Unsupported Planned Trade status.');
    return {
      id: recordId, ticker: id(row.ticker), strategy: string(row.strategy, 'strategy'),
      plannedAt: string(row.plannedAt, 'planned date', 64),
      entry: string(row.entry, 'entry'), stop: string(row.stop, 'stop'),
      target: string(row.target, 'target'), status: 'planned' as const
    };
  });
  const candidateEdits = Object.entries(object(parse(raw[1], {}))).map(([ticker, value]) => {
    const row = object(value);
    return { id: id(ticker), entry: string(row.entry, 'entry'),
      stop: string(row.stop, 'stop'), target: string(row.target, 'target') };
  });
  const fundamentals = object(parse(raw[2], { version: 1, assumptionsByTicker: {} }));
  if (fundamentals.version !== 1) throw new Error('Unsupported saved fundamentals version.');
  const valuationAssumptions = Object.entries(object(fundamentals.assumptionsByTicker ?? {}))
    .map(([ticker, value]) => {
      const assumptions = object(value);
      for (const [key, number] of Object.entries(assumptions)) {
        if (!/^[a-z_]{1,80}$/.test(key) || typeof number !== 'number' || !Number.isFinite(number)) {
          throw new Error('Invalid saved valuation assumption.');
        }
      }
      return { id: id(ticker), assumptions };
    });
  if (candidateEdits.length > 10000 || valuationAssumptions.length > 10000) {
    throw new Error('Too many browser business records to export.');
  }
  const browserSettings = Object.entries(settingsFields).flatMap(([key, fields], index) => {
    const stored = raw[index + businessKeys.length] ?? null;
    if (stored === null) return [];
    const source = object(parse(stored, {}));
    const values: Record<string, unknown> = {};
    for (const [field, type] of Object.entries(fields)) {
      const value = source[field];
      if (value === undefined) continue;
      if (typeof value !== type || (type === 'number' && !Number.isFinite(value))
          || (typeof value === 'string' && value.length > 256)) {
        throw new Error('Invalid saved browser setting. The original data has been retained.');
      }
      values[field] = value;
    }
    return [{ id: key, values }];
  });
  return { plannedTrades, candidateEdits, valuationAssumptions, browserSettings };
}

export async function createBrowserExport() {
  if (!isMigrationPaused()) throw new Error('Pause browser editing before exporting.');
  const raw = exportKeys.map((key) => localStorage.getItem(key));
  const collections = readBrowserBusinessData(raw);
  const counts = Object.fromEntries(Object.entries(collections).map(([key, rows]) => [key, rows.length]));
  const payloadJson = JSON.stringify({
    source: { origin: window.location.origin, exportId: crypto.randomUUID(),
      exportedAt: new Date().toISOString(), writePauseConfirmed: true },
    counts, collections
  });
  const encoded = new TextEncoder().encode(payloadJson);
  if (encoded.length > maxExportBytes) throw new Error('Browser export exceeds the 5 MB limit.');
  const digest = await crypto.subtle.digest('SHA-256', encoded);
  if (!isMigrationPaused() || exportKeys.some((key, index) => localStorage.getItem(key) !== raw[index])) {
    throw new Error('Browser data changed during export. Close other scanner tabs and try again.');
  }
  const sha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  return { format: 'swing-scanner.browser-export', version: 1, payloadJson, sha256 };
}
