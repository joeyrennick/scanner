import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createBrowserExport, isMigrationPaused, readBrowserBusinessData, setMigrationPaused } from './browserExport';
import { createApiClient } from '../api/client';

const trade = { id: 'AAPL', ticker: 'AAPL', strategy: 'breakout', plannedAt: '2026-09-11',
  entry: '$100', stop: '$95', target: '$115', status: 'planned' };

describe('browser business export', () => {
  beforeEach(() => { localStorage.clear(); vi.stubGlobal('crypto', webcrypto); });
  afterEach(() => vi.unstubAllGlobals());

  it('preserves IDs and user-entered business values, with a verifiable digest and counts', async () => {
    localStorage.setItem('planned-trades', JSON.stringify([trade]));
    localStorage.setItem('swing-scanner.candidates.chart-state', JSON.stringify({ AAPL: { entry: '101', stop: '96', target: '117', chartHeight: 300 } }));
    localStorage.setItem('swing-scanner.fundamentals.v1', JSON.stringify({ version: 1, assumptionsByTicker: { AAPL: { discount_rate: 0.1 } } }));
    localStorage.setItem('unrelated-api-key', 'never-export-this');
    localStorage.setItem('swing-scanner.market-data-settings.v2', JSON.stringify({ primaryProvider: 'massive', apiKey: 'never-export-this' }));
    setMigrationPaused(true);
    const result = await createBrowserExport();
    const payload = JSON.parse(result.payloadJson);
    expect(payload.collections.plannedTrades).toEqual([trade]);
    expect(payload.counts).toEqual({ plannedTrades: 1, candidateEdits: 1, valuationAssumptions: 1, browserSettings: 1 });
    expect(result.payloadJson).not.toContain('never-export-this');
    expect(result.payloadJson).not.toContain('chartHeight');
    const hash = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(result.payloadJson));
    expect(result.sha256).toBe(Buffer.from(hash).toString('hex'));
    expect(localStorage.getItem('planned-trades')).toBe(JSON.stringify([trade]));
    expect(isMigrationPaused()).toBe(true);
  });

  it('requires a pause and blocks API requests while browser backup is paused', async () => {
    await expect(createBrowserExport()).rejects.toThrow('Pause');
    setMigrationPaused(true);
    const fetcher = vi.fn();
    await expect(createApiClient({ fetcher, pauseDuringBrowserBackup: true }).request('/api/scans', { method: 'POST' })).rejects.toThrow('paused');
    expect(fetcher).not.toHaveBeenCalled();
    const desktopFetcher = vi.fn().mockResolvedValue(new Response('{"status":"ok"}', { status: 200 }));
    await expect(createApiClient({ fetcher: desktopFetcher, bearerToken: 'fixture-desktop-token' })
      .request('/api/desktop/health')).resolves.toEqual({ status: 'ok' });
    setMigrationPaused(false);
    expect(isMigrationPaused()).toBe(false);
  });

  it('rejects corrupted, duplicate, oversized, and unsupported records without deleting originals', async () => {
    localStorage.setItem('planned-trades', '{broken');
    setMigrationPaused(true);
    await expect(createBrowserExport()).rejects.toThrow('invalid JSON');
    expect(localStorage.getItem('planned-trades')).toBe('{broken');
    expect(() => readBrowserBusinessData([JSON.stringify([trade, trade]), null, null])).toThrow('Duplicate');
    expect(() => readBrowserBusinessData(['x'.repeat(5 * 1024 * 1024 + 1), null, null])).toThrow('limit');
    expect(() => readBrowserBusinessData([null, null, '{"version":2}'])).toThrow('version');
  });

  it('rejects an export if another tab changes records while its digest is calculated', async () => {
    const digest = vi.fn(async () => {
      localStorage.setItem('planned-trades', JSON.stringify([trade]));
      return new ArrayBuffer(32);
    });
    vi.stubGlobal('crypto', { randomUUID: () => 'fixture-id', subtle: { digest } });
    setMigrationPaused(true);
    await expect(createBrowserExport()).rejects.toThrow('changed during export');
  });
});
