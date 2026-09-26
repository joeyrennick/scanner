import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from '../../App';
import { BusinessRecordsGate, BusinessRecordsProvider } from './BusinessRecordsProvider';
import { BusinessRecordsStore } from '../../lib/businessRecords';
import { businessRecordsFixture, candidate, plannedTrade } from '../../test/businessRecordsFixture';

const apiRequest = vi.hoisted(() => vi.fn());
vi.mock('../../api/client', async (original) => ({
  ...await original<typeof import('../../api/client')>(), apiClient: { request: apiRequest }
}));

const row = { Ticker: 'AAPL', 'Triggered Strategies': 'Pullback', 'Current Price': 100,
  'Entry Area': '90', 'Suggested Stop': '85', 'Target Exit': '105', '5D Range': 20 };

beforeEach(() => {
  localStorage.clear();
  apiRequest.mockReset().mockImplementation(async (path: string) => {
    if (path === '/api/strategies') return [];
    if (path === '/api/cache/overview') return {};
    if (path === '/api/saved-watchlists') return { watchlists: [] };
    if (path === '/api/watchlist/latest') return { exists: true, path: 'fixture', run_id: 1, rows: [row] };
    if (path.startsWith('/api/market-data/history/')) return { rows: [] };
    if (path === '/api/market-data/massive/credential') return { configured: false };
    throw new Error('Test API: provider requests are disabled');
  });
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 0);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

async function openPage(path: string) {
  const fixture = businessRecordsFixture({
    plannedTrades: [plannedTrade], candidateEdits: [candidate],
    valuationAssumptions: [{ id: 'AAPL', assumptions: { discount_rate: 0.11 } }],
    browserSettings: [{ id: 'swing-scanner.display-settings', values: { minFiveDayRange: 14 } }]
  });
  const store = new BusinessRecordsStore(fixture.client);
  await store.load();
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<BusinessRecordsProvider store={store}><BusinessRecordsGate>
    <QueryClientProvider client={queries}><MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></MemoryRouter></QueryClientProvider>
  </BusinessRecordsGate></BusinessRecordsProvider>);
  return { store, fixture };
}

it('renders imported Planned Trades in Journal and deletes through the database without altering the browser archive', async () => {
  const legacy = JSON.stringify([{ ...plannedTrade, ticker: 'LEGACY' }]);
  localStorage.setItem('planned-trades', legacy);
  const { store, fixture } = await openPage('/journal');
  expect(screen.getByRole('checkbox', { name: 'Select AAPL' })).toBeInTheDocument();
  expect(screen.queryByText('LEGACY')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Remove', exact: true }));
  await act(async () => { await store.flush(); });
  expect(fixture.rows.get('plannedTrades/AAPL')?.record).toBeNull();
  expect(localStorage.getItem('planned-trades')).toBe(legacy);
});

it('uses imported candidate trade levels in the actual chart controls and saves edits to the API', async () => {
  localStorage.setItem('swing-scanner.candidates.chart-state', JSON.stringify({ AAPL: { ...candidate, entry: '999', chartHeight: 300 } }));
  const { store, fixture } = await openPage('/candidates');
  const entry = await screen.findByLabelText('Entry Area');
  expect(entry).toHaveValue('100');
  fireEvent.change(entry, { target: { value: '112' } });
  await act(async () => { await store.flush(); });
  expect(fixture.rows.get('candidateEdits/AAPL')?.record).toMatchObject({ entry: '112' });
  expect(JSON.parse(localStorage.getItem('swing-scanner.candidates.chart-state')!).AAPL.entry).toBe('999');
});

it('uses imported valuation assumptions for analysis and writes navigation to the preference-only key', async () => {
  const legacy = JSON.stringify({ version: 1, ticker: 'AAPL', assumptionsByTicker: { AAPL: { discount_rate: 0.99 } } });
  localStorage.setItem('swing-scanner.fundamentals.v1', legacy);
  await openPage('/fundamentals?ticker=AAPL');
  await waitFor(() => expect(apiRequest).toHaveBeenCalledWith('/api/fundamentals/AAPL', expect.objectContaining({
    body: expect.stringContaining('"discount_rate":0.11')
  })));
  fireEvent.change(screen.getByLabelText('Candidate strategy'), { target: { value: 'pullback' } });
  expect(JSON.parse(localStorage.getItem('swing-scanner.fundamentals.preferences.v1')!)).not.toHaveProperty('assumptionsByTicker');
  expect(localStorage.getItem('swing-scanner.fundamentals.v1')).toBe(legacy);
});

it('loads the actual settings page without copying legacy settings back into the database', async () => {
  const { store, fixture } = await openPage('/settings');
  const range = screen.getByLabelText(/Minimum 5D Range/);
  expect(range).toHaveValue(14);
  fireEvent.change(range, { target: { value: '16' } });
  await act(async () => { await store.flush(); });
  expect(fixture.rows.get('browserSettings/swing-scanner.display-settings')?.record).toMatchObject({ values: { minFiveDayRange: 16 } });
});
