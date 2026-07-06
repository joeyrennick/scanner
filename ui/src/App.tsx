import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileText,
  Info,
  LayoutDashboard,
  ListChecks,
  LoaderCircle,
  Play,
  RefreshCw,
  Settings,
  ShieldCheck
} from 'lucide-react';
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { useCacheOverview, useStartCacheWarmup } from './api/cache';
import { useJob } from './api/jobs';
import { useLatestWatchlist, useRefreshWatchlistPrices, useStartScan } from './api/scans';
import { useStrategies } from './api/strategies';
import type { CacheWarmupRequest, JobResponse, ScanRequest, WatchlistRow } from './api/types';
import { formatDuration, formatNumber, isJobActive, progressPercent } from './lib/progress';
import {
  candidateFromWatchlistRow,
  mergeWatchlistRows,
  rowMatchesDisplaySettings,
  rowMatchesStrategy,
  sortCandidates,
  type CandidateSort,
  type CandidateSortKey,
  type DisplayCandidate
} from './lib/watchlist';
import { useScannerDisplaySettings } from './lib/scannerSettings';
import { appRoutes, getRouteMeta } from './routes';

const universes = ['all', 'sp500', 'djia', 'nasdaq', 'nyse'];
const historyPeriods = ['6mo', '1y', '5y'];

const routeIcons: Record<string, ReactNode> = {
  '/': <LayoutDashboard />,
  '/daily-scanner': <Activity />,
  '/candidates': <ListChecks />,
  '/backtest': <BarChart3 />,
  '/portfolio': <BriefcaseBusiness />,
  '/journal': <FileText />,
  '/reports': <FileText />,
  '/cache-warmup': <Database />,
  '/settings': <Settings />
};

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="daily-scanner" element={<DailyScannerPage />} />
        <Route path="candidates" element={<PlaceholderPage title="Candidates" />} />
        <Route path="backtest" element={<PlaceholderPage title="Backtest" />} />
        <Route path="portfolio" element={<PlaceholderPage title="Portfolio" />} />
        <Route path="journal" element={<PlaceholderPage title="Journal" />} />
        <Route path="reports" element={<PlaceholderPage title="Reports" />} />
        <Route path="cache-warmup" element={<CacheWarmupPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function AppShell() {
  const location = useLocation();
  const route = getRouteMeta(location.pathname);
  const cacheOverview = useCacheOverview();
  const strategies = useStrategies();
  const cache = cacheOverview.data;
  const activeStrategies = useMemo(
    () => strategies.data?.filter((strategy) => strategy.category === 'entry') ?? [],
    [strategies.data]
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/">
          <BarChart3 aria-hidden="true" />
          <span>Swing Scanner</span>
        </Link>
        <nav className="nav-list" aria-label="Primary">
          {appRoutes.map((navRoute) => (
            <NavItem
              key={navRoute.path}
              icon={routeIcons[navRoute.path]}
              label={navRoute.navLabel}
              to={navRoute.path}
            />
          ))}
        </nav>
        <div className="connection">
          <span className="status-dot" />
          <span>Connected</span>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{route.title}</h1>
            <p>
              {route.description}
              {route.path === '/' ? `; ${activeStrategies.length} entry strategies available` : ''}
            </p>
          </div>
          <CacheStrip cache={cache} />
        </header>

        <Outlet />
      </main>
    </div>
  );
}

function DashboardPage() {
  const cacheOverview = useCacheOverview();
  const strategies = useStrategies();
  const cache = cacheOverview.data;
  const activeStrategies =
    strategies.data?.filter((strategy) => strategy.category === 'entry').length ?? 0;

  return (
    <div className="page-stack">
      <CacheMetrics cache={cache} />

      <div className="overview-grid">
        <section className="panel" aria-labelledby="scanner-readiness-title">
          <div className="panel-header">
            <div>
              <h2 id="scanner-readiness-title">Scanner Readiness</h2>
              <p>Local data and strategy availability</p>
            </div>
          </div>
          <div className="detail-grid">
            <Detail label="Provider" value={cache?.provider ?? 'n/a'} />
            <Detail label="Entry Strategies" value={formatNumber(activeStrategies)} />
            <Detail label="Earliest Bar" value={cache?.earliest_bar_date ?? 'n/a'} />
            <Detail
              label="Refresh Age"
              value={
                cache?.days_since_refresh === 0
                  ? 'Today'
                  : `${cache?.days_since_refresh ?? 'n/a'} days`
              }
            />
          </div>
        </section>

        <section className="panel" aria-labelledby="quick-actions-title">
          <div className="panel-header">
            <div>
              <h2 id="quick-actions-title">Quick Actions</h2>
              <p>Common setup and review workflows</p>
            </div>
          </div>
          <div className="action-grid">
            <Link className="action-card" to="/cache-warmup">
              <Database />
              <span>Cache Warmup</span>
            </Link>
            <Link className="action-card" to="/daily-scanner">
              <Activity />
              <span>Daily Scanner</span>
            </Link>
            <Link className="action-card" to="/backtest">
              <BarChart3 />
              <span>Backtest</span>
            </Link>
            <Link className="action-card" to="/journal">
              <FileText />
              <span>Journal</span>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}

function DailyScannerPage() {
  const cacheOverview = useCacheOverview();
  const strategies = useStrategies();
  const latestWatchlist = useLatestWatchlist();
  const startScan = useStartScan();
  const refreshPrices = useRefreshWatchlistPrices();
  const [displaySettings] = useScannerDisplaySettings();
  const [jobId, setJobId] = useState<string | null>(null);
  const autoRefreshedJobId = useRef<string | null>(null);
  const jobQuery = useJob(jobId);
  const job = jobQuery.data;
  const activeJob = isJobActive(job);
  const [selectedStrategy, setSelectedStrategy] = useState('all');
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [candidateSort, setCandidateSort] = useState<CandidateSort>({
    key: 'score',
    direction: 'desc'
  });
  const [form, setForm] = useState<ScanRequest>({
    universe: 'all',
    history_period: '1y',
    min_price: 20,
    max_price: 50,
    warm_market_data_cache: true,
    cache_warmup_batch_size: 50,
    cache_warmup_max_provider_batches: 10,
    cache_warmup_batch_delay_ms: 500
  });
  const [refreshedRows, setRefreshedRows] = useState<WatchlistRow[] | null>(null);
  const currentJobRunId = scanRunIdFromJob(job);
  const latestWatchlistRunId = latestWatchlist.data?.run_id ?? null;

  const baseRows = useMemo(() => {
    const jobRows = scanRowsFromJob(job);
    const latestRows = latestWatchlist.data?.rows;

    if (
      currentJobRunId !== null &&
      latestWatchlistRunId === currentJobRunId &&
      latestRows
    ) {
      return latestRows;
    }

    return jobRows ?? latestRows ?? [];
  }, [
    currentJobRunId,
    job,
    latestWatchlistRunId,
    latestWatchlist.data?.rows
  ]);
  const rawRows = refreshedRows ?? baseRows;
  const filteredRows = useMemo(
    () =>
      rawRows.filter(
        (row) =>
          rowMatchesStrategy(row, selectedStrategy) &&
          rowMatchesDisplaySettings(row, displaySettings)
      ),
    [displaySettings, rawRows, selectedStrategy]
  );
  const candidates = useMemo(
    () =>
      filteredRows.map((row, index) =>
        candidateFromWatchlistRow(row, index, cacheOverview.data?.latest_bar_date)
      ),
    [cacheOverview.data?.latest_bar_date, filteredRows]
  );
  const sortedCandidates = useMemo(
    () => sortCandidates(candidates, candidateSort),
    [candidateSort, candidates]
  );
  const selectedCandidates = sortedCandidates.filter((candidate) => selectedTickers.has(candidate.id));
  const selectedCount = selectedCandidates.length;
  const exportScope = selectedCount > 0 ? `${selectedCount} selected` : `${sortedCandidates.length} filtered`;
  const percent = progressPercent(job?.progress);
  const activeStrategies = strategies.data?.filter((strategy) => strategy.category === 'entry') ?? [];
  const anyCachedPrice = candidates.some((candidate) => candidate.priceSource === 'Cached Close');
  const currentRunId = currentJobRunId ?? latestWatchlistRunId;

  useEffect(() => {
    setRefreshedRows(null);
  }, [job?.job_id, latestWatchlist.data?.run_id]);

  useEffect(() => {
    const jobRows = scanRowsFromJob(job);

    if (
      !job?.job_id ||
      job.status !== 'complete' ||
      !jobRows ||
      jobRows.length === 0 ||
      autoRefreshedJobId.current === job.job_id
    ) {
      return;
    }

    autoRefreshedJobId.current = job.job_id;
    void refreshVisiblePrices(jobRows.filter((row) => rowMatchesStrategy(row, selectedStrategy)));
  }, [job, selectedStrategy]);

  async function submitScan() {
    setSelectedTickers(new Set());
    setRefreshedRows(null);
    const response = await startScan.mutateAsync({
      ...form,
      min_price: emptyNumberToNull(form.min_price),
      max_price: emptyNumberToNull(form.max_price)
    });
    setJobId(response.job_id);
  }

  async function refreshVisiblePrices(rowsToRefresh = filteredRows) {
    if (rowsToRefresh.length === 0) {
      return;
    }

    const response = await refreshPrices.mutateAsync({
      rows: rowsToRefresh,
      run_id: currentRunId,
      market_data_provider: form.market_data_provider ?? 'yahoo',
      period: '5d',
      reward_risk_multiple: 2,
      suggested_hold_days: 5
    });
    setRefreshedRows((current) => {
      const rows = current ?? baseRows;
      return mergeWatchlistRows(rows, response.rows);
    });
  }

  function toggleTicker(ticker: string) {
    setSelectedTickers((current) => {
      const next = new Set(current);
      if (next.has(ticker)) {
        next.delete(ticker);
      } else {
        next.add(ticker);
      }
      return next;
    });
  }

  function toggleAllCandidates() {
    setSelectedTickers((current) => {
      const visibleIds = new Set(sortedCandidates.map((candidate) => candidate.id));
      const visibleSelectedCount = sortedCandidates.filter((candidate) => current.has(candidate.id)).length;

      if (visibleSelectedCount === sortedCandidates.length) {
        const next = new Set(current);
        visibleIds.forEach((id) => next.delete(id));
        return next;
      }

      return new Set([...current, ...visibleIds]);
    });
  }

  function exportCsv() {
    const rowsToExport = selectedCandidates.length > 0 ? selectedCandidates : sortedCandidates;
    downloadCandidatesCsv(rowsToExport);
  }

  function changeSort(key: CandidateSortKey) {
    setCandidateSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc'
    }));
  }

  return (
    <div className="page-stack">
      <section className="panel scanner-controls" aria-labelledby="scanner-controls-title">
        <div className="panel-header">
          <div>
            <h2 id="scanner-controls-title">Run Scanner</h2>
            <p>Cache-aware scan using local history and controlled provider calls</p>
          </div>
          <button
            className="icon-button"
            title="The scanner uses cached history for indicators and refreshes final candidate prices when backend support is available. Verify live prices in your trading platform before trading."
            aria-label="Scanner price information"
          >
            <Info size={18} />
          </button>
        </div>

        <div className="scanner-control-grid">
          <label>
            Universe
            <select
              value={form.universe}
              onChange={(event) => setForm({ ...form, universe: event.target.value })}
              disabled={activeJob}
            >
              {universes.map((universe) => (
                <option key={universe} value={universe}>
                  {universe.toUpperCase()}
                </option>
              ))}
            </select>
          </label>

          <label>
            History
            <select
              value={form.history_period}
              onChange={(event) => setForm({ ...form, history_period: event.target.value })}
              disabled={activeJob}
            >
              {historyPeriods.map((period) => (
                <option key={period} value={period}>
                  {period}
                </option>
              ))}
            </select>
          </label>

          <label>
            Min Price
            <input
              type="number"
              min="0"
              value={form.min_price ?? ''}
              onChange={(event) =>
                setForm({ ...form, min_price: inputNumberOrNull(event.target.value) })
              }
              disabled={activeJob}
            />
          </label>

          <label>
            Max Price
            <input
              type="number"
              min="0"
              value={form.max_price ?? ''}
              onChange={(event) =>
                setForm({ ...form, max_price: inputNumberOrNull(event.target.value) })
              }
              disabled={activeJob}
            />
          </label>

          <label>
            Batch Size
            <input
              type="number"
              min="1"
              value={form.cache_warmup_batch_size}
              onChange={(event) =>
                setForm({ ...form, cache_warmup_batch_size: Number(event.target.value) })
              }
              disabled={activeJob}
            />
          </label>

          <label>
            Max Batches
            <input
              type="number"
              min="0"
              value={form.cache_warmup_max_provider_batches ?? ''}
              onChange={(event) =>
                setForm({
                  ...form,
                  cache_warmup_max_provider_batches: inputNumberOrNull(event.target.value)
                })
              }
              disabled={activeJob}
            />
          </label>

          <label>
            Batch Delay
            <input
              type="number"
              min="0"
              step="100"
              value={form.cache_warmup_batch_delay_ms}
              onChange={(event) =>
                setForm({ ...form, cache_warmup_batch_delay_ms: Number(event.target.value) })
              }
              disabled={activeJob}
            />
          </label>

          <label className="toggle-row">
            Warm cache first
            <input
              type="checkbox"
              checked={form.warm_market_data_cache}
              onChange={(event) =>
                setForm({ ...form, warm_market_data_cache: event.target.checked })
              }
              disabled={activeJob}
            />
          </label>
        </div>

        <div className="scanner-toolbar">
          <div className="segmented-control" aria-label="Strategy filter">
            <button
              className={selectedStrategy === 'all' ? 'active' : ''}
              onClick={() => setSelectedStrategy('all')}
              disabled={activeJob}
            >
              All
            </button>
            {activeStrategies.map((strategy) => (
              <button
                key={strategy.key}
                className={selectedStrategy === strategy.key ? 'active' : ''}
                onClick={() => setSelectedStrategy(strategy.key)}
                disabled={activeJob}
              >
                {strategy.display_name.replace(' Strategy', '')}
              </button>
            ))}
          </div>

          <button
            className="primary-button"
            onClick={() => void submitScan()}
            disabled={activeJob || startScan.isPending}
          >
            {activeJob ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}
            Run Scan
          </button>
        </div>

        {startScan.isError && (
          <div className="alert alert-danger">
            <AlertTriangle size={18} />
            <span>{startScan.error.message}</span>
          </div>
        )}
      </section>

      <section className="summary-grid" aria-label="Scan summary">
        <MetricCard
          icon={<ListChecks />}
          label="Analyzed"
          value={formatNumber(job?.progress.symbols_checked ?? rowCountFromJob(job))}
          tone="neutral"
        />
        <MetricCard icon={<CheckCircle2 />} label="Candidates" value={formatNumber(candidates.length)} tone="green" />
        <MetricCard
          icon={<Database />}
          label="Provider Symbols"
          value={formatNumber(job?.progress.provider_symbols_attempted)}
          tone="blue"
        />
        <MetricCard
          icon={<Clock3 />}
          label="Elapsed"
          value={formatDuration(job?.progress.elapsed_seconds)}
          tone={job?.progress.rate_limited ? 'amber' : 'neutral'}
        />
      </section>

      {activeJob && (
        <section className="panel compact-progress" aria-label="Scanner progress">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${percent}%` }} />
          </div>
          <div className="progress-summary">
            <strong>{job?.progress.current_step ?? 'Starting scan'}</strong>
            <span>{percent}%</span>
          </div>
        </section>
      )}

      {job?.progress.rate_limited && (
        <div className="alert alert-warning">
          <AlertTriangle size={18} />
          <span>Rate limit stopped provider calls. Results may be partial and use cached history.</span>
        </div>
      )}

      {anyCachedPrice && (
        <div className="alert alert-warning">
          <Info size={18} />
          <span>Some rows use Cached Close because current-price refresh data is not available.</span>
        </div>
      )}

      <section className="panel scanner-results" aria-labelledby="scanner-results-title">
        <div className="panel-header">
          <div>
            <h2 id="scanner-results-title">Scanner Results</h2>
            <p>
              {latestWatchlist.data?.exists
                ? `${sortedCandidates.length} displayed candidates from ${latestWatchlist.data.path}`
                : 'No watchlist has been generated yet'}
            </p>
          </div>
          <div className="button-row inline-actions">
            <button
              className="secondary-button"
              onClick={() => void refreshVisiblePrices()}
              disabled={sortedCandidates.length === 0 || refreshPrices.isPending}
            >
              {refreshPrices.isPending ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <RefreshCw size={18} />
              )}
              Refresh Prices
            </button>
            <button
              className="secondary-button"
              onClick={exportCsv}
              disabled={sortedCandidates.length === 0}
              title={`Export ${exportScope} candidates`}
            >
              <Download size={18} />
              Export CSV
            </button>
            <button className="secondary-button" disabled={sortedCandidates.length === 0}>
              <BarChart3 size={18} />
              {selectedCount > 0 ? 'Backtest Selected' : 'Backtest Filtered'}
            </button>
            <button className="secondary-button" disabled={sortedCandidates.length === 0}>
              <FileText size={18} />
              Generate Daily Report
            </button>
          </div>
        </div>

        {refreshPrices.isError && (
          <div className="alert alert-danger">
            <AlertTriangle size={18} />
            <span>{refreshPrices.error.message}</span>
          </div>
        )}

        <div className="selection-strip">
          <span>{selectedCount > 0 ? `${selectedCount} selected` : 'No rows selected'}</span>
          <span>
            Min stop {displaySettings.minStopDistancePercent}% · Min 5D range{' '}
            {displaySettings.minFiveDayRange}
          </span>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={sortedCandidates.length > 0 && selectedCount === sortedCandidates.length}
                    onChange={toggleAllCandidates}
                    aria-label="Select all scanner candidates"
                  />
                </th>
                <SortableHeader label="Ticker" sortKey="ticker" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="Strategy" sortKey="strategy" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="Score" sortKey="score" sort={candidateSort} onSort={changeSort} />
                <SortableHeader
                  label={
                  <span className="th-with-info">
                    Current Price
                    <Info
                      size={14}
                      aria-label="Current Price comes from Yahoo/latest provider data and may be delayed or stale. Confirm the live price in your trading platform, such as TradingView or thinkorswim, before placing a trade."
                    />
                  </span>
                  }
                  sortKey="currentPrice"
                  sort={candidateSort}
                  onSort={changeSort}
                />
                <SortableHeader label="Price As Of" sortKey="priceAsOf" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="Source" sortKey="priceSource" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="RS" sortKey="relativeStrength" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="RVOL" sortKey="relativeVolume" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="ATR" sortKey="atr" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="5D Range" sortKey="fiveDayRange" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="Entry" sortKey="entryArea" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="Stop" sortKey="stop" sort={candidateSort} onSort={changeSort} />
                <SortableHeader label="Target/Exit" sortKey="targetExit" sort={candidateSort} onSort={changeSort} />
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {sortedCandidates.map((candidate) => (
                <tr key={candidate.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedTickers.has(candidate.id)}
                      onChange={() => toggleTicker(candidate.id)}
                      aria-label={`Select ${candidate.ticker}`}
                    />
                  </td>
                  <td className="ticker-cell">{candidate.ticker}</td>
                  <td>{candidate.strategy}</td>
                  <td>{candidate.score}</td>
                  <td>{candidate.currentPrice}</td>
                  <td>{candidate.priceAsOf}</td>
                  <td>
                    <span
                      className={
                        candidate.priceSource === 'Cached Close'
                          ? 'source-pill cached'
                          : 'source-pill'
                      }
                    >
                      {candidate.priceSource}
                    </span>
                  </td>
                  <td>{candidate.relativeStrength}</td>
                  <td>{candidate.relativeVolume}</td>
                  <td>{candidate.atr}</td>
                  <td>{candidate.fiveDayRange}</td>
                  <td>{candidate.entryArea}</td>
                  <td>{candidate.stop}</td>
                  <td>{candidate.targetExit}</td>
                  <td>
                    <div className="row-actions">
                      <button className="link-button">Open</button>
                      <button className="link-button">Add To Journal</button>
                    </div>
                  </td>
                </tr>
              ))}
              {sortedCandidates.length === 0 && (
                <tr>
                  <td colSpan={15} className="empty-cell">
                    {activeJob ? 'Scan is running.' : 'No candidates match the current filter.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function CacheWarmupPage() {
  const cacheOverview = useCacheOverview();
  const startWarmup = useStartCacheWarmup();
  const [jobId, setJobId] = useState<string | null>(null);
  const jobQuery = useJob(jobId);
  const job = jobQuery.data;
  const [form, setForm] = useState<CacheWarmupRequest>({
    universe: 'all',
    history_period: '6mo',
    batch_size: 50,
    max_provider_batches: 10,
    batch_delay_ms: 500,
    cache_only_preview: true,
    stop_on_rate_limit: true
  });
  const activeJob = isJobActive(job);
  const cache = cacheOverview.data;
  const percent = progressPercent(job?.progress);

  async function submitWarmup(cacheOnlyPreview: boolean) {
    const response = await startWarmup.mutateAsync({
      ...form,
      cache_only_preview: cacheOnlyPreview
    });
    setJobId(response.job_id);
  }

  return (
    <div className="page-stack">
      <CacheMetrics cache={cache} />

      <div className="content-grid">
        <section className="panel warmup-panel" aria-labelledby="warmup-title">
          <div className="panel-header">
            <div>
              <h2 id="warmup-title">Cache Warmup</h2>
              <p>{cache?.provider ?? 'Provider'} historical data</p>
            </div>
            <button
              className="icon-button"
              title="Preview Cache makes no provider calls. Warm Cache fetches missing or stale history in controlled batches."
              aria-label="Cache mode information"
            >
              <Info size={18} />
            </button>
          </div>

          <div className="form-grid">
            <label>
              Universe
              <select
                value={form.universe}
                onChange={(event) => setForm({ ...form, universe: event.target.value })}
                disabled={activeJob}
              >
                {universes.map((universe) => (
                  <option key={universe} value={universe}>
                    {universe.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>

            <label>
              History
              <select
                value={form.history_period}
                onChange={(event) => setForm({ ...form, history_period: event.target.value })}
                disabled={activeJob}
              >
                {historyPeriods.map((period) => (
                  <option key={period} value={period}>
                    {period}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Batch Size
              <input
                type="number"
                min="1"
                value={form.batch_size}
                onChange={(event) => setForm({ ...form, batch_size: Number(event.target.value) })}
                disabled={activeJob}
              />
            </label>

            <label>
              Max Batches
              <input
                type="number"
                min="0"
                value={form.max_provider_batches ?? ''}
                onChange={(event) =>
                  setForm({
                    ...form,
                    max_provider_batches: event.target.value ? Number(event.target.value) : null
                  })
                }
                disabled={activeJob}
              />
            </label>

            <label>
              Delay
              <input
                type="number"
                min="0"
                step="100"
                value={form.batch_delay_ms}
                onChange={(event) =>
                  setForm({ ...form, batch_delay_ms: Number(event.target.value) })
                }
                disabled={activeJob}
              />
            </label>

            <label className="toggle-row">
              Stop on rate limit
              <input
                type="checkbox"
                checked={form.stop_on_rate_limit}
                onChange={(event) =>
                  setForm({ ...form, stop_on_rate_limit: event.target.checked })
                }
                disabled={activeJob}
              />
            </label>
          </div>

          <div className="button-row">
            <button
              className="secondary-button"
              onClick={() => void submitWarmup(true)}
              disabled={activeJob || startWarmup.isPending}
            >
              <RefreshCw size={18} />
              Preview Cache
            </button>
            <button
              className="primary-button"
              onClick={() => void submitWarmup(false)}
              disabled={activeJob || startWarmup.isPending}
            >
              {activeJob ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}
              Warm Cache
            </button>
          </div>

          {startWarmup.isError && (
            <div className="alert alert-danger">
              <AlertTriangle size={18} />
              <span>{startWarmup.error.message}</span>
            </div>
          )}
        </section>

        <JobProgressPanel job={job} percent={percent} />
      </div>
    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  sort,
  onSort
}: {
  label: ReactNode;
  sortKey: CandidateSortKey;
  sort: CandidateSort;
  onSort: (key: CandidateSortKey) => void;
}) {
  const active = sort.key === sortKey;

  return (
    <th>
      <button
        className={active ? 'sort-header active' : 'sort-header'}
        type="button"
        onClick={() => onSort(sortKey)}
        aria-label={`Sort by ${String(sortKey)}${
          active ? `, currently ${sort.direction}` : ''
        }`}
      >
        <span>{label}</span>
        <span className="sort-indicator">{active ? (sort.direction === 'asc' ? '^' : 'v') : '-'}</span>
      </button>
    </th>
  );
}

function SettingsPage() {
  const [settings, setSettings] = useScannerDisplaySettings();

  return (
    <div className="settings-grid">
      <section className="panel" aria-labelledby="scanner-display-settings-title">
        <div className="panel-header">
          <div>
            <h2 id="scanner-display-settings-title">Scanner Display</h2>
            <p>Filter scanner candidates by practical trade range</p>
          </div>
        </div>

        <div className="settings-form">
          <label>
            Minimum Stop Distance
            <div className="input-with-suffix">
              <input
                type="number"
                min="0"
                step="0.1"
                value={settings.minStopDistancePercent}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    minStopDistancePercent: inputNumberOrNull(event.target.value) ?? 0
                  })
                }
              />
              <span>%</span>
            </div>
          </label>

          <label>
            Minimum 5D Range
            <div className="input-with-suffix">
              <input
                type="number"
                min="0"
                step="1"
                value={settings.minFiveDayRange}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    minFiveDayRange: inputNumberOrNull(event.target.value) ?? 0
                  })
                }
              />
              <span>integer</span>
            </div>
          </label>
        </div>
      </section>
    </div>
  );
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="panel placeholder-panel" aria-labelledby="placeholder-title">
      <div>
        <h2 id="placeholder-title">{title}</h2>
        <p>This screen is ready for the next implementation pass.</p>
      </div>
    </section>
  );
}

function CacheStrip({ cache }: { cache?: ReturnType<typeof useCacheOverview>['data'] }) {
  return (
    <div className="cache-strip">
      <span>Cache: {formatNumber(cache?.cached_tickers)} tickers</span>
      <span>Latest bar: {cache?.latest_bar_date ?? 'n/a'}</span>
      <span>
        {cache?.days_since_refresh === 0
          ? 'Refreshed today'
          : `${cache?.days_since_refresh ?? 'n/a'} days old`}
      </span>
    </div>
  );
}

function CacheMetrics({ cache }: { cache?: ReturnType<typeof useCacheOverview>['data'] }) {
  return (
    <section className="metric-grid" aria-label="Cache status">
      <MetricCard
        icon={<Database />}
        label="Cached Tickers"
        value={formatNumber(cache?.cached_tickers)}
        tone="blue"
      />
      <MetricCard
        icon={<BarChart3 />}
        label="Cached Bars"
        value={formatNumber(cache?.cached_bars)}
        tone="neutral"
      />
      <MetricCard
        icon={<Clock3 />}
        label="Latest Bar"
        value={cache?.latest_bar_date ?? 'n/a'}
        tone="green"
      />
      <MetricCard icon={<ShieldCheck />} label="Retention" value="5 years" tone="amber" />
    </section>
  );
}

function NavItem({ icon, label, to }: { icon: ReactNode; label: string; to: string }) {
  return (
    <NavLink className="nav-item" to={to} end={to === '/'}>
      {icon}
      <span>{label}</span>
    </NavLink>
  );
}

function MetricCard({
  icon,
  label,
  value,
  tone
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone: 'blue' | 'green' | 'amber' | 'neutral';
}) {
  return (
    <div className={`metric-card ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function JobProgressPanel({ job, percent }: { job?: JobResponse; percent: number }) {
  const progress = job?.progress;
  const complete = job?.status === 'complete';
  const failed = job?.status === 'failed';
  const stopped = job?.status === 'stopped' || progress?.rate_limited;

  return (
    <section className="panel progress-panel" aria-labelledby="progress-title">
      <div className="panel-header">
        <div>
          <h2 id="progress-title">Job Progress</h2>
          <p>{job?.job_type ? job.job_type.replace('_', ' ') : 'No active job'}</p>
        </div>
        <StatusPill status={job?.status ?? 'idle'} />
      </div>

      <div className="progress-track" aria-label="Job progress">
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="progress-summary">
        <strong>{progress?.current_step ?? 'Ready'}</strong>
        <span>{percent}%</span>
      </div>

      <div className="detail-grid">
        <Detail label="Checked" value={formatNumber(progress?.symbols_checked)} />
        <Detail label="Total" value={formatNumber(progress?.symbols_total)} />
        <Detail label="Kept" value={formatNumber(progress?.symbols_kept)} />
        <Detail label="Skipped" value={formatNumber(progress?.symbols_skipped)} />
        <Detail label="Provider Batches" value={formatNumber(progress?.provider_batches_attempted)} />
        <Detail label="Provider Symbols" value={formatNumber(progress?.provider_symbols_attempted)} />
        <Detail label="Elapsed" value={formatDuration(progress?.elapsed_seconds)} />
        <Detail label="ETA" value={formatDuration(progress?.estimated_seconds_remaining)} />
      </div>

      {complete && (
        <div className="alert alert-success">
          <CheckCircle2 size={18} />
          <span>{job.message}</span>
        </div>
      )}
      {stopped && (
        <div className="alert alert-warning">
          <AlertTriangle size={18} />
          <span>Rate limit stop</span>
        </div>
      )}
      {failed && (
        <div className="alert alert-danger">
          <AlertTriangle size={18} />
          <span>{job.error}</span>
        </div>
      )}
    </section>
  );
}

function scanRowsFromJob(job?: JobResponse): WatchlistRow[] | null {
  const rows = job?.result?.rows;
  return Array.isArray(rows) ? (rows as WatchlistRow[]) : null;
}

function scanRunIdFromJob(job?: JobResponse): number | null {
  const runId = job?.result?.scanner_run_id;
  return typeof runId === 'number' ? runId : null;
}

function rowCountFromJob(job?: JobResponse): number | undefined {
  const analyses = job?.result?.analyses;
  return typeof analyses === 'number' ? analyses : undefined;
}

function inputNumberOrNull(value: string): number | null {
  if (value.trim() === '') {
    return null;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function emptyNumberToNull(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function downloadCandidatesCsv(candidates: DisplayCandidate[]) {
  const header = [
    'Ticker',
    'Strategy',
    'Score',
    'Current Price',
    'Price As Of',
    'Price Source',
    'Relative Strength',
    'Relative Volume',
    'ATR',
    'Entry Area',
    'Stop',
    'Target Exit'
  ];
  const rows = candidates.map((candidate) => [
    candidate.ticker,
    candidate.strategy,
    candidate.score,
    candidate.currentPrice,
    candidate.priceAsOf,
    candidate.priceSource,
    candidate.relativeStrength,
    candidate.relativeVolume,
    candidate.atr,
    candidate.entryArea,
    candidate.stop,
    candidate.targetExit
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'scanner_candidates.csv';
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${status}`}>{status}</span>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
