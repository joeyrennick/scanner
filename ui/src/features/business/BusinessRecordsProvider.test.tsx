import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BusinessRecordsGate, BusinessRecordsProvider, useBusinessCollection, useSavedSetting } from './BusinessRecordsProvider';
import { useCandidateEdits } from './useCandidateEdits';
import { BusinessRecordsStore } from '../../lib/businessRecords';
import { businessRecordsFixture, candidate, plannedTrade } from '../../test/businessRecordsFixture';

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('does not mount the application until all records load, including in StrictMode', async () => {
  const fixture = businessRecordsFixture({ plannedTrades: [plannedTrade] });
  let release!: () => void;
  const blocked = new Promise<void>((resolve) => { release = resolve; });
  fixture.intercept(() => blocked);
  const store = new BusinessRecordsStore(fixture.client);
  function Journal() {
    const [trades] = useBusinessCollection('plannedTrades');
    return <p>Saved trade: {trades[0]?.ticker}</p>;
  }
  render(<StrictMode><BusinessRecordsProvider store={store}><BusinessRecordsGate><Journal /></BusinessRecordsGate></BusinessRecordsProvider></StrictMode>);
  expect(screen.queryByText(/Saved trade:/)).not.toBeInTheDocument();
  await act(async () => { release(); });
  await screen.findByText('Saved trade: AAPL');
  expect(fixture.requests).toHaveLength(4);
});

it('offers retry when the backend is unavailable without showing an empty application', async () => {
  const fixture = businessRecordsFixture();
  fixture.intercept(async () => { throw new Error('Backend offline'); });
  const store = new BusinessRecordsStore(fixture.client);
  render(<BusinessRecordsProvider store={store}><BusinessRecordsGate><p>Application loaded</p></BusinessRecordsGate></BusinessRecordsProvider>);
  await screen.findByRole('alert');
  expect(screen.queryByText('Application loaded')).not.toBeInTheDocument();
  fixture.intercept(undefined);
  fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }));
  await screen.findByText('Application loaded');
});

it('shares imported settings across consumers and preserves partial settings and the original key', async () => {
  const id = 'swing-scanner.display-settings';
  localStorage.setItem(id, '{"minFiveDayRange":999}');
  const fixture = businessRecordsFixture({ browserSettings: [{ id, values: { minFiveDayRange: 14 } }] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  const defaults = { minFiveDayRange: 10, minStopDistancePercent: 1 };
  const { result } = renderHook(() => [useSavedSetting(id, defaults), useSavedSetting(id, defaults)], {
    wrapper: ({ children }) => <BusinessRecordsProvider store={store}>{children}</BusinessRecordsProvider>
  });
  expect(result.current[0][0]).toEqual({ minFiveDayRange: 14, minStopDistancePercent: 1 });
  await act(async () => {
    result.current[0][1]((current) => ({ ...current, minFiveDayRange: 18 }));
    await store.flush();
  });
  expect(result.current[1][0].minFiveDayRange).toBe(18);
  expect(fixture.rows.get(`browserSettings/${id}`)?.record).toEqual({ id, values: { minFiveDayRange: 18, minStopDistancePercent: 1 } });
  expect(localStorage.getItem(id)).toBe('{"minFiveDayRange":999}');
});

it('stores only chart preferences locally and uses database trade levels', async () => {
  const key = 'swing-scanner.candidates.chart-state';
  const legacy = JSON.stringify({ AAPL: { ...candidate, entry: '999', chartHeight: 450, chartZoom: 2 } });
  localStorage.setItem(key, legacy);
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  const { result } = renderHook(useCandidateEdits, {
    wrapper: ({ children }) => <BusinessRecordsProvider store={store}>{children}</BusinessRecordsProvider>
  });
  expect(result.current[0].AAPL).toMatchObject({ entry: '100', chartHeight: 450, chartZoom: 2 });
  await act(async () => {
    result.current[1]((current) => ({ ...current, AAPL: { ...current.AAPL, chartHeight: 500 } }));
    await store.flush();
  });
  expect(fixture.requests).toHaveLength(4);
  await act(async () => {
    result.current[1]((current) => ({ ...current, AAPL: { ...current.AAPL, entry: '110' } }));
    await store.flush();
  });
  expect(fixture.rows.get('candidateEdits/AAPL')?.record).toEqual({ ...candidate, entry: '110' });
  expect(JSON.parse(localStorage.getItem('swing-scanner.candidates.chart-preferences.v1')!)).toEqual({ AAPL: { chartHeight: 500, chartZoom: 2 } });
  expect(localStorage.getItem(key)).toBe(legacy);
});

it('shows saving status, warns before closing, and preserves the draft on failure until explicit discard', async () => {
  const fixture = businessRecordsFixture({ candidateEdits: [candidate] });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  let fail!: () => void;
  fixture.intercept(async (_path, init) => {
    if (init?.method) {
      await new Promise<void>((resolve) => { fail = resolve; });
      throw new Error('offline');
    }
  });
  render(<BusinessRecordsProvider store={store}><p>Application controls</p></BusinessRecordsProvider>);
  act(() => { store.update('candidateEdits', [{ ...candidate, entry: '110' }]); });
  expect(screen.getByRole('status')).toHaveTextContent('Saving 1 change');
  const close = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(close);
  expect(close.defaultPrevented).toBe(true);
  await act(async () => { fail(); await expect(store.flush()).rejects.toThrow(); });
  expect(screen.getByRole('alert')).toHaveTextContent('could not be confirmed');
  expect(screen.queryByText('Application controls')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Download draft for review' })).toBeEnabled();
  vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft and reload saved records' }));
  expect(store.getSnapshot().data.candidateEdits[0].entry).toBe('110');
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft and reload saved records' }));
  await waitFor(() => expect(store.getSnapshot().saveError).toBe(''));
  await waitFor(() => expect(store.getSnapshot().data.candidateEdits[0].entry).toBe('100'));
});
