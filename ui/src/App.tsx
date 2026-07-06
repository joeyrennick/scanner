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
  Save,
  Settings,
  ShieldCheck,
  Trash2
} from 'lucide-react';
import {
  Link,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate
} from 'react-router-dom';
import { useCacheOverview, useStartCacheWarmup } from './api/cache';
import { useStartBacktest } from './api/backtests';
import { useJob } from './api/jobs';
import { useStartPortfolioSimulation } from './api/portfolio';
import { useGenerateDailyScannerReport, useReports } from './api/reports';
import {
  useLatestWatchlist,
  useRefreshWatchlistPrices,
  useStartScan,
  useUpdateCandidateTradeLevels
} from './api/scans';
import { useStrategies } from './api/strategies';
import type {
  BacktestRequest,
  CacheWarmupRequest,
  JobResponse,
  PortfolioSimulationRequest,
  ReportMetadata,
  ScanRequest,
  WatchlistRow
} from './api/types';
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
        <Route path="candidates" element={<CandidatesPage />} />
        <Route path="backtest" element={<BacktestPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="journal" element={<JournalPage />} />
        <Route path="reports" element={<ReportsPage />} />
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
  const navigate = useNavigate();
  const cacheOverview = useCacheOverview();
  const strategies = useStrategies();
  const latestWatchlist = useLatestWatchlist();
  const startScan = useStartScan();
  const refreshPrices = useRefreshWatchlistPrices();
  const generateDailyReport = useGenerateDailyScannerReport();
  const [displaySettings] = useScannerDisplaySettings();
  const [jobId, setJobId] = useState<string | null>(null);
  const autoRefreshedJobId = useRef<string | null>(null);
  const jobQuery = useJob(jobId);
  const job = jobQuery.data;
  const activeJob = isJobActive(job);
  const [selectedStrategy, setSelectedStrategy] = useState('all');
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [journalMessage, setJournalMessage] = useState<string | null>(null);
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
  const selectedRows = filteredRows.filter((row) =>
    selectedTickers.has(String(row.Ticker ?? '').toUpperCase())
  );
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

  async function generateReport() {
    const rowsToReport = selectedRows.length > 0 ? selectedRows : filteredRows;

    await generateDailyReport.mutateAsync({
      rows: rowsToReport,
      report_date: new Date().toISOString().slice(0, 10),
      archive_watchlist: true,
      suggested_hold_days: 5,
      reward_risk_multiple: 2
    });
  }

  function openCandidateBacktest() {
    const rowsToBacktest = selectedCandidates.length > 0 ? selectedCandidates : sortedCandidates;
    const tickers = rowsToBacktest.map((candidate) => candidate.ticker);

    navigate('/backtest', {
      state: {
        tickers,
        strategy: selectedStrategy === 'all' ? undefined : selectedStrategy,
        sourceLabel: selectedCandidates.length > 0 ? 'selected scanner candidates' : 'filtered scanner candidates'
      } satisfies ScannerBacktestState
    });
  }

  function openCandidate(candidate: DisplayCandidate) {
    navigate('/candidates', {
      state: {
        ticker: candidate.ticker
      } satisfies CandidateDetailState
    });
  }

  function addCandidateToJournal(candidate: DisplayCandidate) {
    const trade = plannedTradeFromCandidate(candidate);
    const current = readPlannedTradesFromStorage();

    if (current.some((item) => item.id === trade.id)) {
      setJournalMessage(`${candidate.ticker} is already in Planned Trades`);
      return;
    }

    window.localStorage.setItem('planned-trades', JSON.stringify([trade, ...current]));
    setJournalMessage(`Added ${candidate.ticker} to Planned Trades`);
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
            <button
              className="secondary-button"
              onClick={openCandidateBacktest}
              disabled={sortedCandidates.length === 0}
            >
              <BarChart3 size={18} />
              {selectedCount > 0 ? 'Backtest Selected' : 'Backtest Filtered'}
            </button>
            <button
              className="secondary-button"
              onClick={() => void generateReport()}
              disabled={sortedCandidates.length === 0 || generateDailyReport.isPending}
            >
              {generateDailyReport.isPending ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <FileText size={18} />
              )}
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

        {generateDailyReport.isError && (
          <div className="alert alert-danger">
            <AlertTriangle size={18} />
            <span>{generateDailyReport.error.message}</span>
          </div>
        )}

        {generateDailyReport.data && (
          <div className="alert alert-success">
            <CheckCircle2 size={18} />
            <span>
              Generated {generateDailyReport.data.report.name}.{' '}
              <a href={`/api/reports/${generateDailyReport.data.report.id}/download`}>
                Download report
              </a>
            </span>
          </div>
        )}

        {journalMessage && (
          <div className="alert alert-success">
            <CheckCircle2 size={18} />
            <span>{journalMessage}</span>
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
                      <button className="link-button" onClick={() => openCandidate(candidate)}>
                        Open
                      </button>
                      <button
                        className="link-button"
                        onClick={() => addCandidateToJournal(candidate)}
                      >
                        Add To Journal
                      </button>
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

function CandidatesPage() {
  const location = useLocation();
  const candidateState = isCandidateDetailState(location.state) ? location.state : null;
  const latestWatchlist = useLatestWatchlist();
  const cacheOverview = useCacheOverview();
  const [displaySettings] = useScannerDisplaySettings();
  const updateTradeLevels = useUpdateCandidateTradeLevels();
  const rows = latestWatchlist.data?.rows ?? [];
  const filteredRows = useMemo(
    () => rows.filter((row) => rowMatchesDisplaySettings(row, displaySettings)),
    [displaySettings, rows]
  );
  const candidates = useMemo(
    () =>
      filteredRows.map((row, index) =>
        candidateFromWatchlistRow(row, index, cacheOverview.data?.latest_bar_date)
      ),
    [cacheOverview.data?.latest_bar_date, filteredRows]
  );
  const [selectedTicker, setSelectedTicker] = useState<string | null>(
    candidateState?.ticker ?? null
  );
  const selected = candidates.find((candidate) => candidate.ticker === selectedTicker) ?? candidates[0];
  const [edits, setEdits] = useState<Record<string, CandidateTradeEdits>>({});
  const selectedEdits = selected ? edits[selected.ticker] : undefined;
  const entry = selectedEdits?.entry ?? selected?.entryArea ?? 'n/a';
  const stop = selectedEdits?.stop ?? selected?.stop ?? 'n/a';
  const target = selectedEdits?.target ?? selected?.targetExit ?? 'n/a';
  const chartHeight = selectedEdits?.chartHeight ?? 300;

  function updateSelected(changes: Partial<CandidateTradeEdits>) {
    if (!selected) {
      return;
    }

    setEdits((current) => ({
      ...current,
      [selected.ticker]: {
        ...current[selected.ticker],
        entry: selected.entryArea,
        stop: selected.stop,
        target: selected.targetExit,
        chartHeight,
        ...changes
      }
    }));
  }

  function resetSelected() {
    if (!selected) {
      return;
    }

    setEdits((current) => {
      const next = { ...current };
      delete next[selected.ticker];
      return next;
    });
  }

  async function saveSelected() {
    if (!selected) {
      return;
    }

    const entryValue = parseDisplayNumber(entry);
    const stopValue = parseDisplayNumber(stop);
    const targetValue = parseDisplayNumber(target);

    await updateTradeLevels.mutateAsync({
      ticker: selected.ticker,
      request: {
        run_id: latestWatchlist.data?.run_id ?? null,
        entry_area: entryValue,
        suggested_stop: stopValue,
        target_exit: targetValue,
        reset: false
      }
    });
    resetSelected();
  }

  async function resetPersistedSelected() {
    if (!selected) {
      return;
    }

    await updateTradeLevels.mutateAsync({
      ticker: selected.ticker,
      request: {
        run_id: latestWatchlist.data?.run_id ?? null,
        reset: true
      }
    });
    resetSelected();
  }

  return (
    <div className="content-grid candidate-layout">
      <section className="panel" aria-labelledby="candidate-list-title">
        <div className="panel-header">
          <div>
            <h2 id="candidate-list-title">Candidates</h2>
            <p>
              {candidates.length} scanner-filtered candidates from {rows.length} saved rows
            </p>
          </div>
        </div>

        <div className="table-wrap compact-table">
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Strategy</th>
                <th>Score</th>
                <th>Price</th>
                <th>Entry</th>
                <th>Stop</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr
                  key={candidate.ticker}
                  className={candidate.ticker === selected?.ticker ? 'selected-row' : ''}
                  onClick={() => setSelectedTicker(candidate.ticker)}
                >
                  <td className="ticker-cell">{candidate.ticker}</td>
                  <td>{candidate.strategy}</td>
                  <td>{candidate.score}</td>
                  <td>{candidate.currentPrice}</td>
                  <td>{candidate.entryArea}</td>
                  <td>{candidate.stop}</td>
                </tr>
              ))}
              {candidates.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty-cell">
                    No scanner candidates available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" aria-labelledby="candidate-detail-title">
        <div className="panel-header">
          <div>
            <h2 id="candidate-detail-title">{selected?.ticker ?? 'Candidate Detail'}</h2>
            <p>{selected?.strategy ?? 'Select a candidate'}</p>
          </div>
        </div>

        {selected ? (
          <div className="detail-stack">
            <div className="candidate-chart" style={{ minHeight: chartHeight }}>
              <div className="chart-gridline top" />
              <div className="chart-gridline middle" />
              <div className="chart-gridline bottom" />
              <TradeLevel label="Target" value={target} top="22%" />
              <TradeLevel label="Entry" value={entry} top="48%" />
              <TradeLevel label="Stop" value={stop} top="70%" danger />
            </div>
            <label>
              Chart Height
              <input
                type="range"
                min="240"
                max="520"
                value={chartHeight}
                onChange={(event) => updateSelected({ chartHeight: Number(event.target.value) })}
              />
            </label>

            <div className="checklist-panel">
              <div className="panel-header compact-header">
                <div>
                  <h2>Manual Trade Checklist</h2>
                  <p>{selected.priceSource} · {selected.priceAsOf}</p>
                </div>
                <button
                  className="secondary-button"
                  onClick={() => void resetPersistedSelected()}
                  disabled={updateTradeLevels.isPending}
                >
                  <RefreshCw size={16} />
                  Reset to suggested
                </button>
              </div>
              <div className="form-grid">
                <label>
                  Entry Area
                  <input
                    value={entry}
                    onChange={(event) => updateSelected({ entry: event.target.value })}
                  />
                </label>
                <label>
                  Suggested Stop
                  <input
                    value={stop}
                    onChange={(event) => updateSelected({ stop: event.target.value })}
                  />
                </label>
                <label>
                  Target/Exit
                  <input
                    value={target}
                    onChange={(event) => updateSelected({ target: event.target.value })}
                  />
                </label>
                <label>
                  Current Price
                  <input value={selected.currentPrice} readOnly />
                </label>
              </div>
              <div className="button-row">
                <button
                  className="primary-button"
                  onClick={() => void saveSelected()}
                  disabled={updateTradeLevels.isPending}
                >
                  {updateTradeLevels.isPending ? (
                    <LoaderCircle className="spin" size={18} />
                  ) : (
                    <Save size={18} />
                  )}
                  Save Levels
                </button>
              </div>
              {updateTradeLevels.isError && (
                <AlertMessage tone="danger" message={updateTradeLevels.error.message} />
              )}
            </div>
          </div>
        ) : (
          <p className="muted-text">Run the daily scanner to create candidates.</p>
        )}
      </section>
    </div>
  );
}

function BacktestPage() {
  const location = useLocation();
  const candidateState = isScannerBacktestState(location.state) ? location.state : null;
  const latestWatchlist = useLatestWatchlist();
  const cacheOverview = useCacheOverview();
  const [displaySettings] = useScannerDisplaySettings();
  const strategies = useStrategies();
  const startBacktest = useStartBacktest();
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId).data;
  const activeJob = isJobActive(job);
  const [tickerList, setTickerList] = useState(() => candidateState?.tickers.join(', ') ?? '');
  const [submittedBacktestRun, setSubmittedBacktestRun] = useState<BacktestSubmittedRun | null>(null);
  const [runningBacktestKey, setRunningBacktestKey] = useState<string | null>(null);
  const [backtestResults, setBacktestResults] = useState<Record<string, BacktestDisplayResult>>({});
  const [form, setForm] = useState<BacktestRequest>({
    ticker: '',
    universe: null,
    tickers: candidateState?.tickers ?? null,
    strategy: candidateState?.strategy ?? 'pullback',
    history_period: '5y',
    hold_days: 5,
    min_history_days: 252,
    allow_overlapping_trades: true,
    entry_reset_policy: 'none'
  });
  const parsedTickers = parseTickerList(tickerList);
  const currentBacktestKey = backtestResultKeyForRequest({
    ...form,
    tickers: parsedTickers.length > 0 ? parsedTickers : null,
    ticker:
      parsedTickers.length === 0 && form.ticker?.trim()
        ? form.ticker.trim().toUpperCase()
        : null,
    universe: parsedTickers.length === 0 && !form.ticker?.trim() ? form.universe : null
  });
  const recalculatingCurrentResult =
    runningBacktestKey !== null && runningBacktestKey === currentBacktestKey;
  const visibleBacktestResult = currentBacktestKey && !recalculatingCurrentResult
    ? backtestResults[currentBacktestKey]
    : undefined;
  const stats: Record<string, number> = visibleBacktestResult?.statistics ?? {};
  const trades = visibleBacktestResult?.trades ?? [];
  const filteredWatchlistRows = useMemo(
    () =>
      (latestWatchlist.data?.rows ?? []).filter((row) =>
        rowMatchesDisplaySettings(row, displaySettings)
      ),
    [displaySettings, latestWatchlist.data?.rows]
  );
  const backtestCandidates = useMemo(
    () =>
      filteredWatchlistRows
        .map((row, index) =>
          candidateFromWatchlistRow(row, index, cacheOverview.data?.latest_bar_date)
        )
        .sort((left, right) => left.ticker.localeCompare(right.ticker)),
    [cacheOverview.data?.latest_bar_date, filteredWatchlistRows]
  );
  const selectedCandidate = backtestCandidates.find(
    (candidate) => candidate.ticker === form.ticker
  );
  const selectedCandidateIndex = backtestCandidates.findIndex(
    (candidate) => candidate.ticker === form.ticker
  );

  useEffect(() => {
    if (
      candidateState?.tickers.length ||
      parsedTickers.length > 0 ||
      backtestCandidates.length === 0 ||
      selectedCandidate
    ) {
      return;
    }

    const firstCandidate = backtestCandidates[0];
    setForm((current) => ({
      ...current,
      ticker: firstCandidate.ticker,
      universe: null,
      strategy: strategyKeyForCandidate(firstCandidate, strategies.data) ?? current.strategy
    }));
  }, [
    backtestCandidates,
    candidateState?.tickers.length,
    parsedTickers.length,
    selectedCandidate,
    strategies.data
  ]);

  useEffect(() => {
    if (!submittedBacktestRun || job?.job_id !== submittedBacktestRun.jobId) {
      return;
    }

    if (job?.status === 'failed' || job?.status === 'stopped') {
      setRunningBacktestKey((current) =>
        current === submittedBacktestRun.resultKey ? null : current
      );
      return;
    }

    if (job?.status !== 'complete' || !job.result) {
      return;
    }

    const result = job.result as Record<string, unknown>;
    const statistics = (result.statistics ?? {}) as Record<string, number>;
    const resultTrades = Array.isArray(result.trades)
      ? (result.trades as Record<string, unknown>[])
      : [];

    setBacktestResults((current) => ({
      ...current,
      [submittedBacktestRun.resultKey]: {
        statistics,
        trades: resultTrades
      }
    }));
    setRunningBacktestKey((current) =>
      current === submittedBacktestRun.resultKey ? null : current
    );
  }, [job?.job_id, job?.result, job?.status, submittedBacktestRun]);

  async function submitBacktest() {
    const tickers = parseTickerList(tickerList);
    const request: BacktestRequest = {
      ...form,
      tickers: tickers.length > 0 ? tickers : null,
      ticker:
        tickers.length === 0 && form.ticker?.trim()
          ? form.ticker.trim().toUpperCase()
          : null,
      universe: tickers.length === 0 && !form.ticker?.trim() ? form.universe : null
    };
    const resultKey = backtestResultKeyForRequest(request);

    if (!resultKey) {
      return;
    }

    setRunningBacktestKey(resultKey);
    const response = await startBacktest.mutateAsync(request);
    setSubmittedBacktestRun({ jobId: response.job_id, resultKey });
    setJobId(response.job_id);
  }

  function clearTickerList() {
    setTickerList('');
    setForm((current) => ({
      ...current,
      tickers: null,
      ticker: backtestCandidates[0]?.ticker ?? current.ticker ?? ''
    }));
  }

  function selectCandidate(ticker: string) {
    const candidate = backtestCandidates.find((item) => item.ticker === ticker);

    setTickerList('');
    setForm((current) => ({
      ...current,
      ticker,
      universe: null,
      tickers: null,
      strategy: candidate
        ? strategyKeyForCandidate(candidate, strategies.data) ?? current.strategy
        : current.strategy
    }));
  }

  function selectAdjacentCandidate(direction: -1 | 1) {
    if (backtestCandidates.length === 0) {
      return;
    }

    const currentIndex = selectedCandidateIndex >= 0 ? selectedCandidateIndex : 0;
    const nextIndex =
      (currentIndex + direction + backtestCandidates.length) % backtestCandidates.length;
    selectCandidate(backtestCandidates[nextIndex].ticker);
  }

  return (
    <div className="page-stack">
      <section className="panel" aria-labelledby="backtest-form-title">
        <div className="panel-header">
          <div>
            <h2 id="backtest-form-title">Run Backtest</h2>
            <p>
              Standard historical strategy test using {backtestCandidates.length} scanner-filtered candidates
            </p>
          </div>
          <div className="button-row inline-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => selectAdjacentCandidate(-1)}
              disabled={backtestCandidates.length <= 1}
            >
              Previous
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => selectAdjacentCandidate(1)}
              disabled={backtestCandidates.length <= 1}
            >
              Next
            </button>
          </div>
        </div>
        <div className="scanner-control-grid">
          <label className="wide-field">
            Ticker List
            <textarea
              value={tickerList}
              onChange={(event) => setTickerList(event.target.value)}
              placeholder="Optional: AAPL, MSFT, NVDA"
              rows={3}
            />
          </label>
          <label>
            Candidate
            <select
              value={form.ticker ?? ''}
              onChange={(event) => selectCandidate(event.target.value)}
              disabled={backtestCandidates.length === 0}
            >
              {!form.ticker && backtestCandidates.length > 0 && (
                <option value="">Select candidate</option>
              )}
              {backtestCandidates.length === 0 ? (
                <option value="">No scanner candidates</option>
              ) : (
                backtestCandidates.map((candidate) => (
                  <option key={candidate.ticker} value={candidate.ticker}>
                    {candidate.ticker}
                  </option>
                ))
              )}
            </select>
          </label>
          <label>
            Universe
            <select
              value={form.universe ?? ''}
              onChange={(event) => setForm({ ...form, universe: event.target.value || null, ticker: event.target.value ? '' : form.ticker })}
              disabled={parsedTickers.length > 0}
            >
              <option value="">Single ticker</option>
              {universes.map((universe) => (
                <option key={universe} value={universe}>{universe.toUpperCase()}</option>
              ))}
            </select>
          </label>
          <label>
            Strategy
            <select value={form.strategy} onChange={(event) => setForm({ ...form, strategy: event.target.value })}>
              {(strategies.data ?? []).filter((strategy) => strategy.category === 'entry').map((strategy) => (
                <option key={strategy.key} value={strategy.key}>{strategy.display_name}</option>
              ))}
            </select>
          </label>
          <label>
            History
            <select value={form.history_period} onChange={(event) => setForm({ ...form, history_period: event.target.value })}>
              {historyPeriods.map((period) => <option key={period} value={period}>{period}</option>)}
            </select>
          </label>
          <label>
            Hold Days
            <input type="number" min="1" value={form.hold_days} onChange={(event) => setForm({ ...form, hold_days: Number(event.target.value) })} />
          </label>
          <label>
            Min History Days
            <input type="number" min="1" value={form.min_history_days} onChange={(event) => setForm({ ...form, min_history_days: Number(event.target.value) })} />
          </label>
          <label className="toggle-row">
            Allow overlap
            <input type="checkbox" checked={form.allow_overlapping_trades} onChange={(event) => setForm({ ...form, allow_overlapping_trades: event.target.checked })} />
          </label>
          <label>
            Reset Policy
            <select value={form.entry_reset_policy} onChange={(event) => setForm({ ...form, entry_reset_policy: event.target.value })}>
              <option value="none">None</option>
              <option value="signal-off">Signal off</option>
            </select>
          </label>
        </div>
        <div className="button-row">
          <button className="primary-button" onClick={() => void submitBacktest()} disabled={activeJob || startBacktest.isPending}>
            {activeJob ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}
            Run Backtest
          </button>
          {parsedTickers.length > 0 && (
            <button className="secondary-button" onClick={clearTickerList} disabled={activeJob}>
              Clear Candidate List
            </button>
          )}
        </div>
        {parsedTickers.length > 0 && (
          <div className="selection-strip">
            <span>
              {parsedTickers.length} tickers from {candidateState?.sourceLabel ?? 'ticker list'}
            </span>
            <span>{parsedTickers.slice(0, 8).join(', ')}{parsedTickers.length > 8 ? ', ...' : ''}</span>
          </div>
        )}
        {selectedCandidate && parsedTickers.length === 0 && (
          <div className="candidate-context">
            <Detail label="Selected Candidate" value={selectedCandidate.ticker} />
            <Detail label="Scanner Strategy" value={selectedCandidate.strategy} />
            <Detail label="Current Price" value={selectedCandidate.currentPrice} />
            <Detail label="Entry" value={selectedCandidate.entryArea} />
            <Detail label="Stop" value={selectedCandidate.stop} />
            <Detail label="Target/Exit" value={selectedCandidate.targetExit} />
            <Detail label="Score" value={selectedCandidate.score} />
            <Detail label="Price As Of" value={selectedCandidate.priceAsOf} />
          </div>
        )}
        {startBacktest.isError && <AlertMessage tone="danger" message={startBacktest.error.message} />}
      </section>

      <section className="metric-grid" aria-label="Backtest summary">
        <MetricCard icon={<ListChecks />} label="Trades" value={formatNumber(stats.total_trades)} tone="neutral" />
        <MetricCard icon={<CheckCircle2 />} label="Win Rate" value={formatPercent(stats.win_rate)} tone="green" />
        <MetricCard icon={<BarChart3 />} label="Average Return" value={formatPercent(stats.average_return)} tone="blue" />
        <MetricCard icon={<ShieldCheck />} label="Profit Factor" value={formatNumber(stats.profit_factor)} tone="amber" />
      </section>

      {job && <JobProgressPanel job={job} percent={progressPercent(job.progress)} />}

      <section className="panel" aria-labelledby="backtest-trades-title">
        <div className="panel-header">
          <div>
            <h2 id="backtest-trades-title">Trades</h2>
            <p>
              {visibleBacktestResult
                ? `${trades.length} generated trades`
                : 'No backtest result for the current selection'}
            </p>
          </div>
        </div>
        <SimpleRecordTable
          rows={trades.slice(0, 50)}
          emptyMessage="Run a backtest for the selected candidate to view trades."
        />
      </section>
    </div>
  );
}

function PortfolioPage() {
  const startSimulation = useStartPortfolioSimulation();
  const [jobId, setJobId] = useState<string | null>(null);
  const [positionsPage, setPositionsPage] = useState(1);
  const job = useJob(jobId).data;
  const activeJob = isJobActive(job);
  const [form, setForm] = useState<PortfolioSimulationRequest>({
    trades_csv: 'output/sp500_pullback_trades.csv',
    initial_cash: 100000,
    max_open_positions: 10,
    max_positions_per_ticker: null,
    position_size_percent: 0.1,
    commission_per_trade: 0,
    commission_per_share: 0,
    slippage_percent: 0,
    stop_loss_percent: null,
    trailing_stop_percent: null
  });
  const summary = (job?.result?.summary ?? {}) as Record<string, number>;
  const equityCurve = Array.isArray(job?.result?.equity_curve)
    ? (job.result?.equity_curve as Record<string, unknown>[])
    : [];
  const positions = Array.isArray(job?.result?.positions)
    ? (job.result?.positions as Record<string, unknown>[])
    : [];

  async function submitSimulation() {
    setPositionsPage(1);
    const response = await startSimulation.mutateAsync(form);
    setJobId(response.job_id);
  }

  return (
    <div className="page-stack">
      <section className="panel" aria-labelledby="portfolio-form-title">
        <div className="panel-header">
          <div>
            <h2 id="portfolio-form-title">Portfolio Simulation</h2>
            <p>Model sizing, cash, exposure, slippage, and stops from a trade CSV</p>
          </div>
        </div>
        <div className="scanner-control-grid">
          <label className="wide-field">
            Trade CSV
            <input value={form.trades_csv} onChange={(event) => setForm({ ...form, trades_csv: event.target.value })} />
          </label>
          <label>
            Initial Cash
            <input type="number" min="0" value={form.initial_cash} onChange={(event) => setForm({ ...form, initial_cash: Number(event.target.value) })} />
          </label>
          <label>
            Max Positions
            <input type="number" min="1" value={form.max_open_positions} onChange={(event) => setForm({ ...form, max_open_positions: Number(event.target.value) })} />
          </label>
          <label>
            Position Size
            <input type="number" min="0" step="0.01" value={form.position_size_percent} onChange={(event) => setForm({ ...form, position_size_percent: Number(event.target.value) })} />
          </label>
          <label>
            Commission / Trade
            <input type="number" min="0" step="0.01" value={form.commission_per_trade} onChange={(event) => setForm({ ...form, commission_per_trade: Number(event.target.value) })} />
          </label>
          <label>
            Slippage %
            <input type="number" min="0" step="0.01" value={form.slippage_percent} onChange={(event) => setForm({ ...form, slippage_percent: Number(event.target.value) })} />
          </label>
          <label>
            Stop Loss %
            <input type="number" min="0" step="0.1" value={form.stop_loss_percent ?? ''} onChange={(event) => setForm({ ...form, stop_loss_percent: inputNumberOrNull(event.target.value) })} />
          </label>
          <label>
            Trailing Stop %
            <input type="number" min="0" step="0.1" value={form.trailing_stop_percent ?? ''} onChange={(event) => setForm({ ...form, trailing_stop_percent: inputNumberOrNull(event.target.value) })} />
          </label>
        </div>
        <div className="button-row">
          <button className="primary-button" onClick={() => void submitSimulation()} disabled={activeJob || startSimulation.isPending}>
            {activeJob ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}
            Run Simulation
          </button>
        </div>
        {startSimulation.isError && <AlertMessage tone="danger" message={startSimulation.error.message} />}
      </section>

      {job && <JobProgressPanel job={job} percent={progressPercent(job.progress)} />}

      <section className="metric-grid" aria-label="Portfolio summary">
        <MetricCard icon={<BarChart3 />} label="Total Return" value={formatPercent(summary['Total Return'])} tone="blue" />
        <MetricCard icon={<Clock3 />} label="CAGR" value={formatPercent(summary.CAGR)} tone="green" />
        <MetricCard icon={<ShieldCheck />} label="Max Drawdown" value={formatPercent(summary['Max Drawdown'])} tone="amber" />
        <MetricCard icon={<ListChecks />} label="Positions" value={formatNumber(summary.Positions)} tone="neutral" />
      </section>

      <div className="content-grid">
        <section className="panel" aria-labelledby="equity-title">
          <div className="panel-header">
            <div>
              <h2 id="equity-title">Equity Curve</h2>
              <p>{equityCurve.length} points</p>
            </div>
          </div>
          <div className="mini-chart">
            {equityCurve.slice(-40).map((point, index) => (
              <span
                key={index}
                style={{ height: `${equityBarHeight(point.Equity, equityCurve)}%` }}
                title={`${point.Date ?? ''}: ${point.Equity ?? ''}`}
              />
            ))}
          </div>
        </section>
        <section className="panel" aria-labelledby="positions-title">
          <div className="panel-header">
            <div>
              <h2 id="positions-title">Positions</h2>
              <p>{positions.length} simulated positions; showing 50 per page</p>
            </div>
          </div>
          <SimpleRecordTable
            rows={positions}
            emptyMessage="Run a simulation to view positions."
            page={positionsPage}
            pageSize={50}
            onPageChange={setPositionsPage}
          />
        </section>
      </div>
    </div>
  );
}

function JournalPage() {
  const latestWatchlist = useLatestWatchlist();
  const candidates = useMemo(
    () =>
      (latestWatchlist.data?.rows ?? []).map((row, index) =>
        candidateFromWatchlistRow(row, index)
      ),
    [latestWatchlist.data?.rows]
  );
  const [plannedTrades, setPlannedTrades] = useLocalStorage<PlannedTrade[]>('planned-trades', []);

  function addCandidate(candidate: DisplayCandidate) {
    setPlannedTrades((current) => {
      if (current.some((trade) => trade.id === candidate.ticker)) {
        return current;
      }

      return [plannedTradeFromCandidate(candidate), ...current];
    });
  }

  function deleteTrade(id: string) {
    setPlannedTrades((current) => current.filter((trade) => trade.id !== id));
  }

  return (
    <div className="page-stack">
      <section className="summary-grid" aria-label="Journal summary">
        <MetricCard icon={<ListChecks />} label="Planned Trades" value={formatNumber(plannedTrades.length)} tone="blue" />
        <MetricCard icon={<BriefcaseBusiness />} label="Open Trades" value="Broker sync pending" tone="neutral" />
        <MetricCard icon={<CheckCircle2 />} label="Closed Trades" value="Broker sync pending" tone="neutral" />
        <MetricCard icon={<BarChart3 />} label="Win/Loss" value="n/a" tone="amber" />
      </section>

      <div className="content-grid">
        <section className="panel" aria-labelledby="planned-trades-title">
          <div className="panel-header">
            <div>
              <h2 id="planned-trades-title">Planned Trades</h2>
              <p>Editable trades created from scanner candidates</p>
            </div>
          </div>
          <div className="table-wrap compact-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Strategy</th>
                  <th>Planned</th>
                  <th>Entry</th>
                  <th>Stop</th>
                  <th>Target</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {plannedTrades.map((trade) => (
                  <tr key={trade.id}>
                    <td className="ticker-cell">{trade.ticker}</td>
                    <td>{trade.strategy}</td>
                    <td>{trade.plannedAt}</td>
                    <td>{trade.entry}</td>
                    <td>{trade.stop}</td>
                    <td>{trade.target}</td>
                    <td>
                      <button className="link-button danger-link" onClick={() => deleteTrade(trade.id)}>
                        <Trash2 size={15} />
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {plannedTrades.length === 0 && (
                  <tr>
                    <td colSpan={7} className="empty-cell">No planned trades yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel" aria-labelledby="add-from-scanner-title">
          <div className="panel-header">
            <div>
              <h2 id="add-from-scanner-title">Add From Scanner</h2>
              <p>Creates planned trades that can later be reconciled with broker fills</p>
            </div>
          </div>
          <div className="candidate-add-list">
            {candidates.slice(0, 12).map((candidate) => (
              <button key={candidate.ticker} className="candidate-add-row" onClick={() => addCandidate(candidate)}>
                <span>
                  <strong>{candidate.ticker}</strong>
                  <small>{candidate.strategy}</small>
                </span>
                <Save size={16} />
              </button>
            ))}
            {candidates.length === 0 && <p className="muted-text">Run the scanner to add planned trades.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}

function ReportsPage() {
  const reports = useReports();
  const [typeFilter, setTypeFilter] = useState('all');
  const filteredReports = (reports.data ?? []).filter((report) => typeFilter === 'all' || report.type === typeFilter);
  const reportTypes = Array.from(new Set((reports.data ?? []).map((report) => report.type))).sort();

  return (
    <section className="panel" aria-labelledby="reports-title">
      <div className="panel-header">
        <div>
          <h2 id="reports-title">Reports</h2>
          <p>{filteredReports.length} generated files</p>
        </div>
        <select className="compact-select" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option value="all">All types</option>
          {reportTypes.map((type) => (
            <option key={type} value={type}>{type.replaceAll('_', ' ')}</option>
          ))}
        </select>
      </div>

      {reports.isError && <AlertMessage tone="danger" message={reports.error.message} />}
      <ReportsTable reports={filteredReports} />
    </section>
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

function TradeLevel({
  label,
  value,
  top,
  danger = false
}: {
  label: string;
  value: string;
  top: string;
  danger?: boolean;
}) {
  return (
    <div className={danger ? 'trade-level danger' : 'trade-level'} style={{ top }}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AlertMessage({ tone, message }: { tone: 'danger' | 'warning'; message: string }) {
  return (
    <div className={tone === 'danger' ? 'alert alert-danger' : 'alert alert-warning'}>
      <AlertTriangle size={18} />
      <span>{message}</span>
    </div>
  );
}

function SimpleRecordTable({
  rows,
  emptyMessage,
  page,
  pageSize,
  onPageChange,
}: {
  rows: Record<string, unknown>[];
  emptyMessage: string;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
}) {
  const columns = rows.length > 0 ? Object.keys(rows[0]).slice(0, 8) : [];
  const resolvedPageSize = pageSize ?? rows.length;
  const totalPages = Math.max(1, Math.ceil(rows.length / resolvedPageSize));
  const currentPage = Math.min(Math.max(page ?? 1, 1), totalPages);
  const startIndex = (currentPage - 1) * resolvedPageSize;
  const visibleRows = rows.slice(startIndex, startIndex + resolvedPageSize);

  return (
    <>
      <div className="table-wrap compact-table">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, rowIndex) => (
              <tr key={startIndex + rowIndex}>
                {columns.map((column) => (
                  <td key={column}>{formatUnknown(row[column])}</td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} className="empty-cell">
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {pageSize && rows.length > pageSize && onPageChange && (
        <div className="pagination-row">
          <span>
            Showing {startIndex + 1}-{Math.min(startIndex + pageSize, rows.length)} of{' '}
            {rows.length}
          </span>
          <div className="button-row inline-actions">
            <button
              className="secondary-button"
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
            >
              Previous
            </button>
            <span className="page-indicator">
              Page {currentPage} of {totalPages}
            </span>
            <button
              className="secondary-button"
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function ReportsTable({ reports }: { reports: ReportMetadata[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Modified</th>
            <th>Size</th>
            <th>Path</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((report) => (
            <tr key={report.id}>
              <td className="ticker-cell">{report.name}</td>
              <td>{report.type.replaceAll('_', ' ')}</td>
              <td>{formatDateTime(report.modified_at)}</td>
              <td>{formatFileSize(report.size_bytes)}</td>
              <td>{report.path}</td>
              <td>
                <a className="link-button" href={`/api/reports/${report.id}/download`}>
                  Download
                </a>
              </td>
            </tr>
          ))}
          {reports.length === 0 && (
            <tr>
              <td colSpan={6} className="empty-cell">No generated reports found.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SettingsPage() {
  const cacheOverview = useCacheOverview();
  const strategies = useStrategies();
  const [displaySettings, setDisplaySettings] = useScannerDisplaySettings();
  const [recommendationSettings, setRecommendationSettings] = useLocalStorage<RecommendationSettings>(
    'swing-scanner.recommendation-settings',
    defaultRecommendationSettings
  );
  const [cacheSettings, setCacheSettings] = useLocalStorage<CacheSettings>(
    'swing-scanner.cache-settings',
    defaultCacheSettings
  );
  const [marketDataSettings, setMarketDataSettings] = useLocalStorage<MarketDataSettings>(
    'swing-scanner.market-data-settings',
    defaultMarketDataSettings
  );
  const [appearanceSettings, setAppearanceSettings] = useLocalStorage<AppearanceSettings>(
    'swing-scanner.appearance-settings',
    defaultAppearanceSettings
  );
  const cache = cacheOverview.data;

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
                value={displaySettings.minStopDistancePercent}
                onChange={(event) =>
                  setDisplaySettings({
                    ...displaySettings,
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
                value={displaySettings.minFiveDayRange}
                onChange={(event) =>
                  setDisplaySettings({
                    ...displaySettings,
                    minFiveDayRange: inputNumberOrNull(event.target.value) ?? 0
                  })
                }
              />
              <span>integer</span>
            </div>
          </label>
        </div>
      </section>

      <section className="panel" aria-labelledby="recommendation-settings-title">
        <div className="panel-header">
          <div>
            <h2 id="recommendation-settings-title">Recommendation Defaults</h2>
            <p>Used for future checklist values, exports, and generated reports</p>
          </div>
        </div>

        <div className="settings-form two-column-settings">
          <label>
            Reward/Risk Multiple
            <div className="input-with-suffix">
              <input
                type="number"
                min="0.1"
                step="0.1"
                value={recommendationSettings.rewardRiskMultiple}
                onChange={(event) =>
                  setRecommendationSettings({
                    ...recommendationSettings,
                    rewardRiskMultiple: inputNumberOrNull(event.target.value) ?? 2
                  })
                }
              />
              <span>x</span>
            </div>
          </label>
          <label>
            Suggested Hold
            <div className="input-with-suffix">
              <input
                type="number"
                min="1"
                step="1"
                value={recommendationSettings.suggestedHoldDays}
                onChange={(event) =>
                  setRecommendationSettings({
                    ...recommendationSettings,
                    suggestedHoldDays: inputNumberOrNull(event.target.value) ?? 5
                  })
                }
              />
              <span>days</span>
            </div>
          </label>
          <label>
            Stop Method
            <select
              value={recommendationSettings.stopMethod}
              onChange={(event) =>
                setRecommendationSettings({
                  ...recommendationSettings,
                  stopMethod: event.target.value
                })
              }
            >
              <option value="2atr">2 * ATR</option>
              <option value="swing-low">Recent swing low</option>
              <option value="percent">Fixed percent</option>
            </select>
          </label>
          <label>
            ATR Period
            <input
              type="number"
              min="1"
              value={recommendationSettings.atrPeriod}
              onChange={(event) =>
                setRecommendationSettings({
                  ...recommendationSettings,
                  atrPeriod: inputNumberOrNull(event.target.value) ?? 14
                })
              }
            />
          </label>
          <label>
            Risk Per Trade
            <div className="input-with-suffix">
              <input
                type="number"
                min="0"
                step="0.1"
                value={recommendationSettings.riskPerTradePercent}
                onChange={(event) =>
                  setRecommendationSettings({
                    ...recommendationSettings,
                    riskPerTradePercent: inputNumberOrNull(event.target.value) ?? 1
                  })
                }
              />
              <span>%</span>
            </div>
          </label>
          <label>
            CSV Export Scope
            <select
              value={recommendationSettings.defaultExportScope}
              onChange={(event) =>
                setRecommendationSettings({
                  ...recommendationSettings,
                  defaultExportScope: event.target.value
                })
              }
            >
              <option value="filtered">Filtered rows</option>
              <option value="selected">Selected rows first</option>
              <option value="all">All scanner rows</option>
            </select>
          </label>
          <label className="toggle-row wide-field">
            Include adjusted checklist values in exports and reports
            <input
              type="checkbox"
              checked={recommendationSettings.includeAdjustedChecklistValues}
              onChange={(event) =>
                setRecommendationSettings({
                  ...recommendationSettings,
                  includeAdjustedChecklistValues: event.target.checked
                })
              }
            />
          </label>
        </div>
      </section>

      <section className="panel" aria-labelledby="cache-settings-title">
        <div className="panel-header">
          <div>
            <h2 id="cache-settings-title">Cache</h2>
            <p>Local market data health and default refresh behavior</p>
          </div>
          <Link className="secondary-button" to="/cache-warmup">
            <Database size={18} />
            Warm Cache
          </Link>
        </div>

        <div className="detail-grid settings-detail-grid">
          <Detail label="Cached Tickers" value={formatNumber(cache?.cached_tickers)} />
          <Detail label="Cached Bars" value={formatNumber(cache?.cached_bars)} />
          <Detail label="Latest Bar" value={cache?.latest_bar_date ?? 'n/a'} />
          <Detail
            label="Refresh Age"
            value={
              cache?.days_since_refresh === 0
                ? 'Today'
                : `${cache?.days_since_refresh ?? 'n/a'} days`
            }
          />
        </div>

        <div className="settings-form two-column-settings">
          <label>
            History Window
            <select
              value={cacheSettings.historyPeriod}
              onChange={(event) =>
                setCacheSettings({ ...cacheSettings, historyPeriod: event.target.value })
              }
            >
              {historyPeriods.map((period) => (
                <option key={period} value={period}>
                  {period}
                </option>
              ))}
            </select>
          </label>
          <label>
            Stale After
            <div className="input-with-suffix">
              <input
                type="number"
                min="0"
                value={cacheSettings.staleAfterDays}
                onChange={(event) =>
                  setCacheSettings({
                    ...cacheSettings,
                    staleAfterDays: inputNumberOrNull(event.target.value) ?? 1
                  })
                }
              />
              <span>days</span>
            </div>
          </label>
          <label>
            Batch Size
            <input
              type="number"
              min="1"
              value={cacheSettings.batchSize}
              onChange={(event) =>
                setCacheSettings({
                  ...cacheSettings,
                  batchSize: inputNumberOrNull(event.target.value) ?? 50
                })
              }
            />
          </label>
          <label>
            Batch Delay
            <div className="input-with-suffix">
              <input
                type="number"
                min="0"
                step="100"
                value={cacheSettings.batchDelayMs}
                onChange={(event) =>
                  setCacheSettings({
                    ...cacheSettings,
                    batchDelayMs: inputNumberOrNull(event.target.value) ?? 500
                  })
                }
              />
              <span>ms</span>
            </div>
          </label>
          <label className="toggle-row wide-field">
            Stop provider calls when rate-limited
            <input
              type="checkbox"
              checked={cacheSettings.stopOnRateLimit}
              onChange={(event) =>
                setCacheSettings({ ...cacheSettings, stopOnRateLimit: event.target.checked })
              }
            />
          </label>
        </div>
      </section>

      <section className="panel" aria-labelledby="market-data-settings-title">
        <div className="panel-header">
          <div>
            <h2 id="market-data-settings-title">Market Data</h2>
            <p>Provider preference and request safety defaults</p>
          </div>
          <button
            className="icon-button"
            title="Yahoo Finance is unofficial and can rate-limit automated requests. Cache-first mode reduces repeated provider calls."
            aria-label="Market data provider information"
          >
            <Info size={18} />
          </button>
        </div>

        <div className="settings-form two-column-settings">
          <label>
            Primary Provider
            <select
              value={marketDataSettings.primaryProvider}
              onChange={(event) =>
                setMarketDataSettings({
                  ...marketDataSettings,
                  primaryProvider: event.target.value
                })
              }
            >
              <option value="yahoo">Yahoo</option>
              <option value="alpha_vantage">Alpha Vantage</option>
            </select>
          </label>
          <label>
            Backup Provider
            <select
              value={marketDataSettings.backupProvider}
              onChange={(event) =>
                setMarketDataSettings({
                  ...marketDataSettings,
                  backupProvider: event.target.value
                })
              }
            >
              <option value="none">None</option>
              <option value="alpha_vantage">Alpha Vantage</option>
              <option value="yahoo">Yahoo</option>
            </select>
          </label>
          <label>
            Request Mode
            <select
              value={marketDataSettings.requestMode}
              onChange={(event) =>
                setMarketDataSettings({
                  ...marketDataSettings,
                  requestMode: event.target.value
                })
              }
            >
              <option value="cache-first">Cache first</option>
              <option value="provider-only">Provider only</option>
              <option value="cache-only">Cache only</option>
            </select>
          </label>
          <label>
            Max Provider Batches
            <input
              type="number"
              min="0"
              value={marketDataSettings.maxProviderBatches}
              onChange={(event) =>
                setMarketDataSettings({
                  ...marketDataSettings,
                  maxProviderBatches: inputNumberOrNull(event.target.value) ?? 10
                })
              }
            />
          </label>
          <label>
            Test Symbol
            <input
              value={marketDataSettings.testSymbol}
              onChange={(event) =>
                setMarketDataSettings({
                  ...marketDataSettings,
                  testSymbol: event.target.value.toUpperCase()
                })
              }
            />
          </label>
        </div>
      </section>

      <section className="panel" aria-labelledby="strategy-settings-title">
        <div className="panel-header">
          <div>
            <h2 id="strategy-settings-title">Strategy Rules</h2>
            <p>Backend strategy defaults available to scanner and backtest screens</p>
          </div>
        </div>

        <div className="strategy-settings-list">
          {(strategies.data ?? [])
            .filter((strategy) => strategy.category === 'entry')
            .map((strategy) => (
              <div className="strategy-settings-row" key={strategy.key}>
                <div>
                  <strong>{strategy.display_name}</strong>
                  <span>{strategy.key}</span>
                </div>
                <div className="strategy-field-list">
                  {strategy.fields.slice(0, 5).map((field) => (
                    <span key={field.name}>
                      {field.name}: {formatUnknown(field.default)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          {strategies.isError && <AlertMessage tone="danger" message={strategies.error.message} />}
        </div>
      </section>

      <section className="panel" aria-labelledby="appearance-settings-title">
        <div className="panel-header">
          <div>
            <h2 id="appearance-settings-title">Appearance</h2>
            <p>Local display preferences only; scanner calculations are unchanged</p>
          </div>
        </div>

        <div className="settings-form two-column-settings">
          <label>
            Density
            <select
              value={appearanceSettings.density}
              onChange={(event) =>
                setAppearanceSettings({ ...appearanceSettings, density: event.target.value })
              }
            >
              <option value="comfortable">Comfortable</option>
              <option value="compact">Compact</option>
            </select>
          </label>
          <label>
            Table Page Size
            <input
              type="number"
              min="10"
              step="10"
              value={appearanceSettings.tablePageSize}
              onChange={(event) =>
                setAppearanceSettings({
                  ...appearanceSettings,
                  tablePageSize: inputNumberOrNull(event.target.value) ?? 50
                })
              }
            />
          </label>
          <label>
            Default Chart Range
            <select
              value={appearanceSettings.defaultChartRange}
              onChange={(event) =>
                setAppearanceSettings({
                  ...appearanceSettings,
                  defaultChartRange: event.target.value
                })
              }
            >
              <option value="3mo">3mo</option>
              <option value="6mo">6mo</option>
              <option value="1y">1y</option>
            </select>
          </label>
          <label className="toggle-row">
            Remember chart resize
            <input
              type="checkbox"
              checked={appearanceSettings.rememberChartResize}
              onChange={(event) =>
                setAppearanceSettings({
                  ...appearanceSettings,
                  rememberChartResize: event.target.checked
                })
              }
            />
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
  const [detailsExpanded, setDetailsExpanded] = useState(true);

  useEffect(() => {
    if (isJobActive(job)) {
      setDetailsExpanded(true);
      return;
    }

    if (job?.status === 'complete') {
      setDetailsExpanded(false);
    }
  }, [job?.job_id, job?.status, job]);

  return (
    <section className="panel progress-panel" aria-labelledby="progress-title">
      <div className="panel-header">
        <div>
          <h2 id="progress-title">Job Progress</h2>
          <p>{job?.job_type ? job.job_type.replace('_', ' ') : 'No active job'}</p>
        </div>
        <div className="button-row inline-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={() => setDetailsExpanded((current) => !current)}
          >
            {detailsExpanded ? 'Hide Details' : 'Show Details'}
          </button>
          <StatusPill status={job?.status ?? 'idle'} />
        </div>
      </div>

      <div className="progress-track" aria-label="Job progress">
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="progress-summary">
        <strong>{progress?.current_step ?? 'Ready'}</strong>
        <span>{percent}%</span>
      </div>

      {detailsExpanded && (
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
      )}

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

type CandidateTradeEdits = {
  entry: string;
  stop: string;
  target: string;
  chartHeight: number;
};

type ScannerBacktestState = {
  tickers: string[];
  strategy?: string;
  sourceLabel?: string;
};

type BacktestDisplayResult = {
  statistics: Record<string, number>;
  trades: Record<string, unknown>[];
};

type BacktestSubmittedRun = {
  jobId: string;
  resultKey: string;
};

type CandidateDetailState = {
  ticker: string;
};

type PlannedTrade = {
  id: string;
  ticker: string;
  strategy: string;
  plannedAt: string;
  entry: string;
  stop: string;
  target: string;
  status: 'planned';
};

type RecommendationSettings = {
  rewardRiskMultiple: number;
  suggestedHoldDays: number;
  stopMethod: string;
  atrPeriod: number;
  riskPerTradePercent: number;
  defaultExportScope: string;
  includeAdjustedChecklistValues: boolean;
};

type CacheSettings = {
  historyPeriod: string;
  staleAfterDays: number;
  batchSize: number;
  batchDelayMs: number;
  stopOnRateLimit: boolean;
};

type MarketDataSettings = {
  primaryProvider: string;
  backupProvider: string;
  requestMode: string;
  maxProviderBatches: number;
  testSymbol: string;
};

type AppearanceSettings = {
  density: string;
  tablePageSize: number;
  defaultChartRange: string;
  rememberChartResize: boolean;
};

const defaultRecommendationSettings: RecommendationSettings = {
  rewardRiskMultiple: 2,
  suggestedHoldDays: 5,
  stopMethod: '2atr',
  atrPeriod: 14,
  riskPerTradePercent: 1,
  defaultExportScope: 'filtered',
  includeAdjustedChecklistValues: true
};

const defaultCacheSettings: CacheSettings = {
  historyPeriod: '6mo',
  staleAfterDays: 1,
  batchSize: 50,
  batchDelayMs: 500,
  stopOnRateLimit: true
};

const defaultMarketDataSettings: MarketDataSettings = {
  primaryProvider: 'yahoo',
  backupProvider: 'alpha_vantage',
  requestMode: 'cache-first',
  maxProviderBatches: 10,
  testSymbol: 'AAPL'
};

const defaultAppearanceSettings: AppearanceSettings = {
  density: 'comfortable',
  tablePageSize: 50,
  defaultChartRange: '6mo',
  rememberChartResize: true
};

function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    const stored = window.localStorage.getItem(key);

    if (!stored) {
      return initialValue;
    }

    try {
      return JSON.parse(stored) as T;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  return [value, setValue] as const;
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

function formatPercent(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}%` : 'n/a';
}

function formatDateTime(value: string): string {
  const timestamp = Date.parse(value);

  if (!Number.isFinite(timestamp)) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(timestamp);
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUnknown(value: unknown): string {
  if (value === null || value === undefined) {
    return 'n/a';
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toFixed(2).replace(/\.00$/, '') : 'n/a';
  }

  return String(value);
}

function parseDisplayNumber(value: string): number | null {
  const parsed = Number(value.replace(/[$,%"]/g, '').replace(/,/g, '').trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function plannedTradeFromCandidate(candidate: DisplayCandidate): PlannedTrade {
  return {
    id: candidate.ticker,
    ticker: candidate.ticker,
    strategy: candidate.strategy,
    plannedAt: new Date().toISOString().slice(0, 10),
    entry: candidate.entryArea,
    stop: candidate.stop,
    target: candidate.targetExit,
    status: 'planned'
  };
}

function readPlannedTradesFromStorage(): PlannedTrade[] {
  const stored = window.localStorage.getItem('planned-trades');

  if (!stored) {
    return [];
  }

  try {
    const parsed = JSON.parse(stored);
    return Array.isArray(parsed) ? (parsed as PlannedTrade[]) : [];
  } catch {
    return [];
  }
}

function parseTickerList(value: string): string[] {
  const seen = new Set<string>();
  const tickers = [];

  for (const item of value.split(/[\s,]+/)) {
    const ticker = item.trim().toUpperCase();

    if (!ticker || seen.has(ticker)) {
      continue;
    }

    tickers.push(ticker);
    seen.add(ticker);
  }

  return tickers;
}

function backtestResultKeyForRequest(request: BacktestRequest): string | null {
  const target = backtestTargetKey(request);

  if (!target) {
    return null;
  }

  return [
    target,
    request.strategy,
    request.history_period,
    request.hold_days,
    request.min_history_days,
    request.allow_overlapping_trades ? 'overlap' : 'no-overlap',
    request.entry_reset_policy
  ].join('|');
}

function backtestTargetKey(request: BacktestRequest): string | null {
  if (request.tickers?.length) {
    return `tickers:${request.tickers.map((ticker) => ticker.toUpperCase()).join(',')}`;
  }

  if (request.ticker) {
    return `ticker:${request.ticker.toUpperCase()}`;
  }

  if (request.universe) {
    return `universe:${request.universe}`;
  }

  return null;
}

function isScannerBacktestState(value: unknown): value is ScannerBacktestState {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Partial<ScannerBacktestState>;
  return Array.isArray(candidate.tickers) && candidate.tickers.every((ticker) => typeof ticker === 'string');
}

function isCandidateDetailState(value: unknown): value is CandidateDetailState {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Partial<CandidateDetailState>;
  return typeof candidate.ticker === 'string' && candidate.ticker.trim() !== '';
}

function strategyKeyForCandidate(
  candidate: DisplayCandidate,
  strategies?: Array<{ key: string; display_name: string }>
): string | undefined {
  const candidateStrategy = candidate.strategy.toLowerCase();
  return strategies?.find((strategy) =>
    candidateStrategy.includes(strategy.display_name.toLowerCase())
    || candidateStrategy.includes(strategy.key.toLowerCase())
  )?.key;
}

function equityBarHeight(value: unknown, rows: Record<string, unknown>[]): number {
  const equityValues = rows
    .map((row) => (typeof row.Equity === 'number' ? row.Equity : Number(row.Equity)))
    .filter((item) => Number.isFinite(item));
  const numeric = typeof value === 'number' ? value : Number(value);

  if (!Number.isFinite(numeric) || equityValues.length === 0) {
    return 10;
  }

  const min = Math.min(...equityValues);
  const max = Math.max(...equityValues);

  if (max === min) {
    return 55;
  }

  return 12 + ((numeric - min) / (max - min)) * 82;
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
