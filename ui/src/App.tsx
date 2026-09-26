import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { CSSProperties, PointerEvent as ReactPointerEvent, ReactNode } from 'react';
import { createPortal } from 'react-dom';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bookmark,
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
  Square,
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
import { useCancelJob, useJob } from './api/jobs';
import { useStartPortfolioSimulation } from './api/portfolio';
import { useGenerateDailyScannerReport, useReports } from './api/reports';
import {
  useLatestWatchlist,
  useMarketDataHistory,
  useRefreshWatchlistPrices,
  useStartScan,
  useUpdateCandidateTradeLevels
} from './api/scans';
import { useSavedWatchlist, useSavedWatchlists } from './api/savedWatchlists';
import {
  useDeleteMassiveCredential,
  useMassiveCredentialStatus,
  useSaveMassiveCredential
} from './api/settings';
import { useStrategies } from './api/strategies';
import type {
  BacktestRequest,
  CacheWarmupRequest,
  JobResponse,
  MarketDataHistoryPoint,
  PortfolioSimulationRequest,
  ReportMetadata,
  ScanRequest,
  WatchlistRow
} from './api/types';
import { formatDuration, formatNumber, isJobActive, progressPercent } from './lib/progress';
import {
  chartFrequencyOption,
  chartFrequencyOptions,
  defaultChartFrequency,
  type ChartFrequency
} from './lib/chartFrequency';
import { pinnedTrailingPosition } from './lib/chartViewport';
import {
  candidateFromWatchlistRow,
  defaultScannerResultFilters,
  mergeWatchlistRows,
  normalizeScannerResultFilters,
  rowMatchesDisplaySettings,
  rowMatchesScannerResultFilters,
  rowMatchesStrategy,
  sortCandidates,
  type CandidateSort,
  type CandidateSortKey,
  type DisplayCandidate,
  type ScannerResultFilters
} from './lib/watchlist';
import { useScannerDisplaySettings } from './lib/scannerSettings';
import {
  loadRecentTickerSelection,
  rememberRecentTicker
} from './lib/recentTicker';
import {
  clampScannerColumnWidth,
  defaultScannerColumnVisibility,
  defaultScannerColumnWidths,
  normalizeScannerColumnVisibility,
  normalizeScannerColumnWidths,
  type ScannerColumnKey,
  type ScannerColumnVisibility,
  type ScannerColumnWidths
} from './lib/scannerColumns';
import { appRoutes, getRouteMeta } from './routes';
import { FundamentalAnalysisPage } from './features/fundamentals/FundamentalAnalysisPage';
import { WatchlistsPage } from './features/watchlists/WatchlistsPage';
import { SavedWatchlistButton } from './features/watchlists/SavedWatchlistButton';
import { MultiSelectFilter } from './components/MultiSelectFilter';
import { useBusinessCollection, useSavedSetting } from './features/business/BusinessRecordsProvider';
import { useCandidateEdits, type CandidateTradeEdits } from './features/business/useCandidateEdits';
import type { PlannedTrade } from './lib/businessRecords';
import { FileActionButton } from './components/FileActionButton';
import { RuntimeReadiness } from './features/settings/RuntimeReadiness';
import { SECContactSetup } from './features/settings/SECContactSetup';
import { usePlatform } from './platform/PlatformProvider';
import type { FileActions } from './platform/files';

const universes = ['all', 'sp500', 'djia', 'nasdaq', 'nyse'];
const historyPeriods = ['6mo', '1y', '5y'];
const currentPriceInfoText =
  'Current Price comes from the selected market-data provider (Massive/Polygon by default). If fresh provider data is unavailable, the scanner may use a cached closing price. Prices may be delayed; confirm the live price in your trading platform before placing a trade.';
const scannerColumnLabels: Record<ScannerColumnKey, string> = {
  select: 'Row Selection',
  ticker: 'Ticker',
  strategy: 'Strategy',
  score: 'Score',
  currentPrice: 'Current Price',
  fairValue: 'Fair Value',
  dcfUpside: 'DCF Upside',
  validation: 'Validation',
  quality: 'Business Quality',
  dcfEstimate: 'DCF Estimate',
  risk: 'Risk',
  relativeStrength: 'Relative Strength',
  relativeVolume: 'Relative Volume',
  atr: 'ATR',
  fiveDayRange: '5D Range',
  entry: 'Entry',
  stop: 'Stop',
  target: 'Target/Exit'
};
const validationResultFilterOptions = [
  { value: 'validated', label: 'Validated' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;
const qualityResultFilterOptions = [
  { value: 'strong', label: 'Strong' },
  { value: 'acceptable', label: 'Acceptable' },
  { value: 'weak', label: 'Weak' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;
const dcfResultFilterOptions = [
  { value: 'undervalued', label: 'Undervalued' },
  { value: 'fairly_valued', label: 'Fairly Valued' },
  { value: 'overvalued', label: 'Overvalued' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;
const riskResultFilterOptions = [
  { value: 'low', label: 'Low' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'high', label: 'High' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;

const routeIcons: Record<string, ReactNode> = {
  '/': <LayoutDashboard />,
  '/daily-scanner': <Activity />,
  '/candidates': <ListChecks />,
  '/watchlists': <Bookmark />,
  '/fundamentals': <ShieldCheck />,
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
        <Route path="watchlists" element={<WatchlistsPage />} />
        <Route path="fundamentals" element={<FundamentalAnalysisPage />} />
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
  const { files } = usePlatform();
  const [csvError, setCsvError] = useState('');
  const navigate = useNavigate();
  const cacheOverview = useCacheOverview();
  const strategies = useStrategies();
  const latestWatchlist = useLatestWatchlist();
  const startScan = useStartScan();
  const cancelJob = useCancelJob();
  const refreshPrices = useRefreshWatchlistPrices();
  const generateDailyReport = useGenerateDailyScannerReport();
  const [displaySettings] = useScannerDisplaySettings();
  const [marketDataSettings] = useSavedSetting<MarketDataSettings>(
    'swing-scanner.market-data-settings.v2',
    defaultMarketDataSettings
  );
  const [jobId, setJobId] = useState<string | null>(null);
  const autoRefreshedJobId = useRef<string | null>(null);
  const scannerResultsTableRef = useRef<HTMLTableElement | null>(null);
  const jobQuery = useJob(jobId);
  const job = jobQuery.data;
  const activeJob = isJobActive(job);
  const [selectedStrategy, setSelectedStrategy] = useLocalStorage(
    'swing-scanner.daily-scanner.strategy',
    'all'
  );
  const [resultFilters, setResultFilters] = useLocalStorage<ScannerResultFilters>(
    'swing-scanner.daily-scanner.result-filters.v1',
    defaultScannerResultFilters,
    normalizeScannerResultFilters
  );
  const [scannerColumnWidths, setScannerColumnWidths] = useLocalStorage<ScannerColumnWidths>(
    'swing-scanner.daily-scanner.column-widths.v1',
    { ...defaultScannerColumnWidths },
    normalizeScannerColumnWidths
  );
  const [scannerColumnVisibility, setScannerColumnVisibility] =
    useLocalStorage<ScannerColumnVisibility>(
      'swing-scanner.daily-scanner.column-visibility.v1',
      { ...defaultScannerColumnVisibility },
      normalizeScannerColumnVisibility
    );
  const [activeTicker, setActiveTicker] = useLocalStorage<string | null>(
    'swing-scanner.daily-scanner.active-ticker.v1',
    null,
    normalizeOptionalTicker
  );
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [candidateSort, setCandidateSort] = useState<CandidateSort>({
    key: 'score',
    direction: 'desc'
  });
  const [form, setForm] = useState<ScanRequest>({
    universe: 'all',
    history_period: '1y',
    min_price: 10,
    max_price: 200,
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
  const isFundamentalStrategy = selectedStrategy === 'undervalued';
  const valuationMode =
    isFundamentalStrategy ||
    (rawRows.length > 0 &&
      rawRows.every((row) =>
        String(row['Triggered Strategies'] ?? '').toLowerCase().includes('undervalued')
      ));
  const modeScannerColumns = scannerColumnsForMode(valuationMode);
  const configurableScannerColumns = modeScannerColumns.filter(
    (key) => key !== 'select' && key !== 'ticker'
  );
  const visibleScannerColumns = modeScannerColumns.filter(
    (key) => scannerColumnVisibility[key]
  );
  const visibleScannerColumnSet = new Set(visibleScannerColumns);
  const scannerTableWidth = visibleScannerColumns.reduce(
    (total, key) => total + scannerColumnWidths[key],
    0
  );
  const filteredRows = useMemo(
    () =>
      rawRows.filter(
        (row) =>
          rowMatchesStrategy(row, selectedStrategy) &&
          rowMatchesDisplaySettings(row, displaySettings) &&
          rowMatchesScannerResultFilters(row, resultFilters)
      ),
    [displaySettings, rawRows, resultFilters, selectedStrategy]
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
  const activeCandidate =
    sortedCandidates.find((candidate) => candidate.ticker === activeTicker) ?? null;
  const activeCandidateRow = activeCandidate
    ? rawRows.find((row) => String(row.Ticker ?? '').toUpperCase() === activeCandidate.ticker)
    : undefined;
  const selectedCandidates = sortedCandidates.filter((candidate) => selectedTickers.has(candidate.id));
  const selectedRows = filteredRows.filter((row) =>
    selectedTickers.has(String(row.Ticker ?? '').toUpperCase())
  );
  const selectedCount = selectedCandidates.length;
  const exportScope = selectedCount > 0 ? `${selectedCount} selected` : `${sortedCandidates.length} filtered`;
  const activeResultFilterCount = countActiveScannerResultFilters(resultFilters);
  const allConfigurableColumnsVisible = configurableScannerColumns.every(
    (key) => scannerColumnVisibility[key]
  );
  const percent = progressPercent(job?.progress);
  const activeStrategies = strategies.data?.filter((strategy) => strategy.category === 'entry') ?? [];
  const anyCachedPrice = candidates.some((candidate) => candidate.priceSource === 'Cached Close');
  const resultsPriceAsOf = sharedCandidateValue(candidates.map((candidate) => candidate.priceAsOf));
  const resultsPriceSource = sharedCandidateValue(candidates.map((candidate) => candidate.priceSource));
  const currentRunId = currentJobRunId ?? latestWatchlistRunId;

  useEffect(() => {
    setRefreshedRows(null);
  }, [job?.job_id, latestWatchlist.data?.run_id]);

  useEffect(() => {
    if (
      job?.status !== 'complete' ||
      currentJobRunId === null ||
      currentJobRunId === latestWatchlistRunId
    ) {
      return;
    }

    void latestWatchlist.refetch();
  }, [currentJobRunId, job?.status, latestWatchlist.refetch, latestWatchlistRunId]);

  useEffect(() => {
    const jobRows = scanRowsFromJob(job);

    if (
      !job?.job_id ||
      job.status !== 'complete' ||
      !jobRows ||
      jobRows.length === 0 ||
      valuationMode ||
      autoRefreshedJobId.current === job.job_id
    ) {
      return;
    }

    autoRefreshedJobId.current = job.job_id;
    void refreshVisiblePrices(
      jobRows.filter(
        (row) =>
          rowMatchesStrategy(row, selectedStrategy) &&
          rowMatchesDisplaySettings(row, displaySettings) &&
          rowMatchesScannerResultFilters(row, resultFilters)
      )
    );
  }, [displaySettings, job, resultFilters, selectedStrategy, valuationMode]);

  async function submitScan() {
    setSelectedTickers(new Set());
    setRefreshedRows(null);
    const response = await startScan.mutateAsync({
      ...form,
      strategy: selectedStrategy,
      market_data_provider: marketDataSettings.primaryProvider,
      min_price: isFundamentalStrategy ? null : emptyNumberToNull(form.min_price),
      max_price: isFundamentalStrategy ? null : emptyNumberToNull(form.max_price),
      warm_market_data_cache: isFundamentalStrategy ? false : form.warm_market_data_cache
    });
    if (isFundamentalStrategy) {
      setCandidateSort({ key: 'marginOfSafety', direction: 'desc' });
    }
    setJobId(response.job_id);
  }

  async function cancelScan() {
    if (!jobId) {
      return;
    }

    await cancelJob.mutateAsync(jobId);
  }

  async function refreshVisiblePrices(rowsToRefresh = filteredRows) {
    if (rowsToRefresh.length === 0) {
      return;
    }

    const response = await refreshPrices.mutateAsync({
      rows: rowsToRefresh,
      run_id: currentRunId,
      market_data_provider: marketDataSettings.primaryProvider,
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
    if (!selectedTickers.has(ticker)) {
      selectDailyTicker(ticker);
    }
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

  function selectDailyTicker(ticker: string) {
    setActiveTicker(ticker);
    rememberRecentTicker(ticker, 'daily-scanner');
  }

  function openSelectedFundamentals() {
    if (!activeCandidate) {
      return;
    }

    selectDailyTicker(activeCandidate.ticker);
    navigate(
      fundamentalsPath(
        activeCandidate.ticker,
        currentRunId,
        valuationMode ? 'undervalued' : selectedStrategy
      )
    );
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

  async function exportCsv() {
    setCsvError('');
    const rowsToExport = selectedCandidates.length > 0 ? selectedCandidates : sortedCandidates;
    try { await downloadCandidatesCsv(rowsToExport, files); }
    catch (error) { setCsvError(error instanceof Error ? error.message : 'CSV export failed.'); }
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
    if (valuationMode) {
      return;
    }
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

  function changeSort(key: CandidateSortKey) {
    setCandidateSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc'
    }));
  }

  function changeResultFilter<K extends keyof ScannerResultFilters>(
    key: K,
    value: ScannerResultFilters[K]
  ) {
    setResultFilters((current) => ({ ...current, [key]: value }));
  }

  function clearResultFilters() {
    setResultFilters(defaultScannerResultFilters);
  }

  function startColumnResize(
    key: ScannerColumnKey,
    event: ReactPointerEvent<HTMLDivElement>
  ) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = scannerColumnWidths[key];
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    function handleMove(moveEvent: PointerEvent) {
      const nextWidth = clampScannerColumnWidth(
        startWidth + moveEvent.clientX - startX
      );
      setScannerColumnWidths((current) => ({ ...current, [key]: nextWidth }));
    }

    function handleUp() {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      window.removeEventListener('pointercancel', handleUp);
    }

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    window.addEventListener('pointercancel', handleUp);
  }

  function resizeColumnBy(key: ScannerColumnKey, delta: number) {
    setScannerColumnWidths((current) => ({
      ...current,
      [key]: clampScannerColumnWidth(current[key] + delta)
    }));
  }

  function autoFitColumn(key: ScannerColumnKey) {
    const table = scannerResultsTableRef.current;
    const columnIndex = visibleScannerColumns.indexOf(key);
    if (!table || columnIndex < 0) return;

    const column = table.querySelectorAll('col')[columnIndex] as
      | HTMLTableColElement
      | undefined;
    if (!column) return;

    const previousTableLayout = table.style.tableLayout;
    const previousTableWidth = table.style.width;
    const previousTableMinWidth = table.style.minWidth;
    const previousColumnWidth = column.style.width;
    let measuredWidth = scannerColumnWidths[key];

    try {
      table.style.tableLayout = 'auto';
      table.style.width = 'max-content';
      table.style.minWidth = '0';
      column.style.width = 'auto';
      void table.offsetWidth;
      const contentWidths = Array.from(table.rows)
        .map((row) => row.cells[columnIndex]?.scrollWidth ?? 0)
        .filter((width) => width > 0);
      measuredWidth = contentWidths.length > 0
        ? Math.max(...contentWidths)
        : defaultScannerColumnWidths[key];
    } finally {
      table.style.tableLayout = previousTableLayout;
      table.style.width = previousTableWidth;
      table.style.minWidth = previousTableMinWidth;
      column.style.width = previousColumnWidth;
    }

    setScannerColumnWidths((current) => ({
      ...current,
      [key]: clampScannerColumnWidth(measuredWidth + 2)
    }));
  }

  function toggleScannerColumn(key: ScannerColumnKey) {
    setScannerColumnVisibility((current) => ({
      ...current,
      [key]: !current[key]
    }));
  }

  function showAllScannerColumns() {
    setScannerColumnVisibility((current) => ({
      ...current,
      ...Object.fromEntries(configurableScannerColumns.map((key) => [key, true]))
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
              disabled={activeJob || isFundamentalStrategy}
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
              disabled={activeJob || isFundamentalStrategy}
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
              disabled={activeJob || isFundamentalStrategy}
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
              disabled={activeJob || isFundamentalStrategy}
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
              disabled={activeJob || isFundamentalStrategy}
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
              disabled={activeJob || isFundamentalStrategy}
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
              disabled={activeJob || isFundamentalStrategy}
            />
          </label>
        </div>

        {isFundamentalStrategy && (
          <div className="alert alert-warning">
            <Info size={18} />
            <span>
              SEC valuation mode ignores price limits and technical rules. It returns stocks
              whose base DCF fair value is at least 15% above the current price.
            </span>
          </div>
        )}

        <div className="scanner-toolbar">
          <div className="segmented-control" aria-label="Strategy filter">
            <button
              className={selectedStrategy === 'all' ? 'active' : ''}
              onClick={() => setSelectedStrategy('all')}
              disabled={activeJob}
            >
              All Technical
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
          {activeJob && (
            <button
              className="secondary-button danger-button"
              onClick={() => void cancelScan()}
              disabled={cancelJob.isPending || job?.cancel_requested}
            >
              <Square size={18} />
              {job?.cancel_requested ? 'Stopping...' : 'Stop Scan'}
            </button>
          )}
        </div>

        {startScan.isError && (
          <div className="alert alert-danger">
            <AlertTriangle size={18} />
            <span>{startScan.error.message}</span>
          </div>
        )}
        {cancelJob.isError && (
          <div className="alert alert-danger">
            <AlertTriangle size={18} />
            <span>{cancelJob.error.message}</span>
          </div>
        )}
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
            <div className="results-metadata">
              <span><strong>Price as of:</strong> {resultsPriceAsOf}</span>
              <span><strong>Source:</strong> {resultsPriceSource}</span>
            </div>
          </div>
          <div className="button-row inline-actions">
            {activeCandidate && (
              <SavedWatchlistButton
                ticker={activeCandidate.ticker}
                source="daily-scanner"
                data={candidateSnapshot(activeCandidate, activeCandidateRow)}
                label="Watchlists"
              />
            )}
            <button
              className="secondary-button"
              type="button"
              onClick={openSelectedFundamentals}
              disabled={!activeCandidate}
              title={
                activeCandidate
                  ? `Open fundamentals for ${activeCandidate.ticker}`
                  : 'Select a scanner result row first'
              }
            >
              <BriefcaseBusiness size={18} />
              Fundamentals{activeCandidate ? `: ${activeCandidate.ticker}` : ''}
            </button>
            <details className="column-chooser">
              <summary className="secondary-button">Columns</summary>
              <div className="column-chooser-menu" aria-label="Visible scanner columns">
                <strong>Show or hide columns</strong>
                <span className="column-chooser-note">Ticker and row selection remain visible.</span>
                <div className="column-chooser-options">
                  {configurableScannerColumns.map((key) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={scannerColumnVisibility[key]}
                        onChange={() => toggleScannerColumn(key)}
                      />
                      {scannerColumnLabels[key]}
                    </label>
                  ))}
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={showAllScannerColumns}
                  disabled={allConfigurableColumnsVisible}
                >
                  Show All
                </button>
              </div>
            </details>
            <button
              className="secondary-button"
              onClick={() => void refreshVisiblePrices()}
              disabled={
                sortedCandidates.length === 0 || refreshPrices.isPending || valuationMode
              }
              title={valuationMode ? 'Rerun the valuation scan to refresh prices and fair-value comparisons' : undefined}
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
              disabled={sortedCandidates.length === 0 || valuationMode}
              title={valuationMode ? 'Point-in-time fundamental valuation is not supported by the technical backtester' : undefined}
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

        {csvError && <div className="alert alert-danger" role="alert">{csvError}</div>}
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
              <FileActionButton reportId={generateDailyReport.data.report.id}>
                Download report
              </FileActionButton>
            </span>
          </div>
        )}

        <div className="scanner-result-filter-bar" aria-label="Scanner result filters">
          <div className="scanner-result-filter-grid">
            <MultiSelectFilter
              label="Validation"
              allLabel="All validation statuses"
              selected={resultFilters.validation}
              options={validationResultFilterOptions}
              onChange={(values) => changeResultFilter('validation', values)}
            />
            <MultiSelectFilter
              label="Business Quality"
              allLabel="All quality levels"
              selected={resultFilters.quality}
              options={qualityResultFilterOptions}
              onChange={(values) => changeResultFilter('quality', values)}
            />
            <MultiSelectFilter
              label="DCF Estimate"
              allLabel="All DCF estimates"
              selected={resultFilters.dcf}
              options={dcfResultFilterOptions}
              onChange={(values) => changeResultFilter('dcf', values)}
            />
            <MultiSelectFilter
              label="Risk"
              allLabel="All risk levels"
              selected={resultFilters.risk}
              options={riskResultFilterOptions}
              onChange={(values) => changeResultFilter('risk', values)}
            />
            <label>
              Minimum Price
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="No minimum"
                value={resultFilters.minPrice ?? ''}
                onChange={(event) =>
                  changeResultFilter('minPrice', priceFilterNumberOrNull(event.target.value))
                }
              />
            </label>
            <label>
              Maximum Price
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="No maximum"
                value={resultFilters.maxPrice ?? ''}
                onChange={(event) =>
                  changeResultFilter('maxPrice', priceFilterNumberOrNull(event.target.value))
                }
              />
            </label>
          </div>
          <button
            className="secondary-button"
            type="button"
            onClick={clearResultFilters}
            disabled={activeResultFilterCount === 0}
          >
            Clear Filters{activeResultFilterCount > 0 ? ` (${activeResultFilterCount})` : ''}
          </button>
        </div>

        <div className="selection-strip">
          <span>{selectedCount > 0 ? `${selectedCount} selected` : 'No rows selected'}</span>
          <span>
            {valuationMode
              ? 'Ranked by base-case DCF margin of safety'
              : `Min stop ${displaySettings.minStopDistancePercent}% · Min 5D range ${displaySettings.minFiveDayRange}`}
          </span>
        </div>

        <div className="table-wrap">
          <table
            ref={scannerResultsTableRef}
            className="data-table scanner-results-table"
            style={{ width: scannerTableWidth, minWidth: '100%' }}
          >
            <colgroup>
              {visibleScannerColumns.map((key) => (
                <col key={key} style={{ width: scannerColumnWidths[key] }} />
              ))}
            </colgroup>
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
                <SortableHeader
                  label="Ticker"
                  sortKey="ticker"
                  columnKey="ticker"
                  sort={candidateSort}
                  onSort={changeSort}
                  onResize={startColumnResize}
                  onResizeBy={resizeColumnBy}
                  onAutoFit={autoFitColumn}
                />
                {visibleScannerColumnSet.has('strategy') && (
                  <SortableHeader
                    label="Strategy"
                    sortKey="strategy"
                    columnKey="strategy"
                    sort={candidateSort}
                    onSort={changeSort}
                    onResize={startColumnResize}
                    onResizeBy={resizeColumnBy}
                    onAutoFit={autoFitColumn}
                  />
                )}
                {visibleScannerColumnSet.has('score') && (
                  <SortableHeader
                    label={valuationMode ? 'Strategy Score' : 'Score'}
                    sortKey="score"
                    columnKey="score"
                    sort={candidateSort}
                    onSort={changeSort}
                    onResize={startColumnResize}
                    onResizeBy={resizeColumnBy}
                    onAutoFit={autoFitColumn}
                  />
                )}
                {visibleScannerColumnSet.has('currentPrice') && (
                  <SortableHeader
                    label={
                    <span className="th-with-info">
                      Current Price
                      <CurrentPriceInfo />
                    </span>
                    }
                    sortKey="currentPrice"
                    columnKey="currentPrice"
                    resizeLabel="Current Price"
                    sort={candidateSort}
                    onSort={changeSort}
                    onResize={startColumnResize}
                    onResizeBy={resizeColumnBy}
                    onAutoFit={autoFitColumn}
                  />
                )}
                {valuationMode && (
                  <>
                    {visibleScannerColumnSet.has('fairValue') && (
                      <SortableHeader
                        label="Fair Value"
                        sortKey="fairValue"
                        columnKey="fairValue"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                    {visibleScannerColumnSet.has('dcfUpside') && (
                      <SortableHeader
                        label="DCF Upside"
                        sortKey="marginOfSafety"
                        columnKey="dcfUpside"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                  </>
                )}
                {visibleScannerColumnSet.has('validation') && (
                  <SortableHeader
                    label="Validation"
                    sortKey="validationScore"
                    columnKey="validation"
                    sort={candidateSort}
                    onSort={changeSort}
                    onResize={startColumnResize}
                    onResizeBy={resizeColumnBy}
                    onAutoFit={autoFitColumn}
                  />
                )}
                {visibleScannerColumnSet.has('quality') && (
                  <SortableHeader
                    label="Business Quality"
                    sortKey="qualityScore"
                    columnKey="quality"
                    sort={candidateSort}
                    onSort={changeSort}
                    onResize={startColumnResize}
                    onResizeBy={resizeColumnBy}
                    onAutoFit={autoFitColumn}
                  />
                )}
                {visibleScannerColumnSet.has('dcfEstimate') && (
                  <SortableHeader
                    label="DCF Estimate"
                    sortKey="marginOfSafety"
                    columnKey="dcfEstimate"
                    sort={candidateSort}
                    onSort={changeSort}
                    onResize={startColumnResize}
                    onResizeBy={resizeColumnBy}
                    onAutoFit={autoFitColumn}
                  />
                )}
                {visibleScannerColumnSet.has('risk') && (
                  <SortableHeader
                    label="Risk"
                    sortKey="riskScore"
                    columnKey="risk"
                    sort={candidateSort}
                    onSort={changeSort}
                    onResize={startColumnResize}
                    onResizeBy={resizeColumnBy}
                    onAutoFit={autoFitColumn}
                  />
                )}
                {!valuationMode && (
                  <>
                    {visibleScannerColumnSet.has('relativeStrength') && (
                      <SortableHeader
                        label="RS"
                        sortKey="relativeStrength"
                        columnKey="relativeStrength"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                    {visibleScannerColumnSet.has('relativeVolume') && (
                      <SortableHeader
                        label="RVOL"
                        sortKey="relativeVolume"
                        columnKey="relativeVolume"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                    {visibleScannerColumnSet.has('atr') && (
                      <SortableHeader
                        label="ATR"
                        sortKey="atr"
                        columnKey="atr"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                    {visibleScannerColumnSet.has('fiveDayRange') && (
                      <SortableHeader
                        label="5D Range"
                        sortKey="fiveDayRange"
                        columnKey="fiveDayRange"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                    {visibleScannerColumnSet.has('entry') && (
                      <SortableHeader
                        label="Entry"
                        sortKey="entryArea"
                        columnKey="entry"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                    {visibleScannerColumnSet.has('stop') && (
                      <SortableHeader
                        label="Stop"
                        sortKey="stop"
                        columnKey="stop"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                    {visibleScannerColumnSet.has('target') && (
                      <SortableHeader
                        label="Target/Exit"
                        sortKey="targetExit"
                        columnKey="target"
                        sort={candidateSort}
                        onSort={changeSort}
                        onResize={startColumnResize}
                        onResizeBy={resizeColumnBy}
                        onAutoFit={autoFitColumn}
                      />
                    )}
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sortedCandidates.map((candidate) => (
                <tr
                  key={candidate.id}
                  className={candidate.ticker === activeTicker ? 'selected-row selectable-row' : 'selectable-row'}
                  aria-selected={candidate.ticker === activeTicker}
                  tabIndex={0}
                  onClick={() => selectDailyTicker(candidate.ticker)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      selectDailyTicker(candidate.ticker);
                    }
                  }}
                >
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedTickers.has(candidate.id)}
                      onChange={() => toggleTicker(candidate.id)}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={`Select ${candidate.ticker}`}
                    />
                  </td>
                  <td className="ticker-cell">
                    <Link
                      className="ticker-link"
                      onClick={(event) => {
                        event.stopPropagation();
                        selectDailyTicker(candidate.ticker);
                      }}
                      to="/candidates"
                      state={{
                        ticker: candidate.ticker,
                        maximized: true
                      } satisfies CandidateDetailState}
                    >
                      {candidate.ticker}
                    </Link>
                    {candidate.companyName && <span className="company-name">{candidate.companyName}</span>}
                  </td>
                  {visibleScannerColumnSet.has('strategy') && <td>{candidate.strategy}</td>}
                  {visibleScannerColumnSet.has('score') && <td>{candidate.score}</td>}
                  {visibleScannerColumnSet.has('currentPrice') && <td>{candidate.currentPrice}</td>}
                  {valuationMode && (
                    <>
                      {visibleScannerColumnSet.has('fairValue') && <td>{candidate.fairValue}</td>}
                      {visibleScannerColumnSet.has('dcfUpside') && <td>{candidate.marginOfSafety}</td>}
                    </>
                  )}
                  {visibleScannerColumnSet.has('validation') && (
                    <FundamentalSummaryCell
                      label={candidate.validationLabel}
                      value={scoreOutOf100(candidate.validationScore)}
                    />
                  )}
                  {visibleScannerColumnSet.has('quality') && (
                    <FundamentalSummaryCell
                      label={candidate.qualityLabel}
                      value={scoreOutOf100(candidate.qualityScore)}
                    />
                  )}
                  {visibleScannerColumnSet.has('dcfEstimate') && (
                    <FundamentalSummaryCell
                      label={candidate.dcfLabel}
                      value={candidate.marginOfSafety}
                    />
                  )}
                  {visibleScannerColumnSet.has('risk') && (
                    <FundamentalSummaryCell
                      label={candidate.riskLabel}
                      value={scoreOutOf100(candidate.riskScore)}
                    />
                  )}
                  {!valuationMode && (
                    <>
                      {visibleScannerColumnSet.has('relativeStrength') && <td>{candidate.relativeStrength}</td>}
                      {visibleScannerColumnSet.has('relativeVolume') && <td>{candidate.relativeVolume}</td>}
                      {visibleScannerColumnSet.has('atr') && <td>{candidate.atr}</td>}
                      {visibleScannerColumnSet.has('fiveDayRange') && <td>{candidate.fiveDayRange}</td>}
                      {visibleScannerColumnSet.has('entry') && <td>{candidate.entryArea}</td>}
                      {visibleScannerColumnSet.has('stop') && <td>{candidate.stop}</td>}
                      {visibleScannerColumnSet.has('target') && <td>{candidate.targetExit}</td>}
                    </>
                  )}
                </tr>
              ))}
              {sortedCandidates.length === 0 && (
                <tr>
                  <td colSpan={visibleScannerColumns.length} className="empty-cell">
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
  const [recentSelectionAtEntry] = useState(() => loadRecentTickerSelection());
  const incomingTicker = candidateState?.ticker ?? recentSelectionAtEntry?.ticker ?? null;
  const incomingSavedWatchlistId =
    candidateState?.savedWatchlistId ??
    (candidateState === null ? recentSelectionAtEntry?.savedWatchlistId ?? null : null);
  const maximizeIncomingTicker =
    candidateState?.maximized ?? (candidateState === null && incomingTicker !== null);
  const savedWatchlistContext = useSavedWatchlist(incomingSavedWatchlistId);
  const latestWatchlist = useLatestWatchlist();
  const cacheOverview = useCacheOverview();
  const candidateResultsTableRef = useRef<HTMLTableElement | null>(null);
  const [displaySettings] = useScannerDisplaySettings();
  const [marketDataSettings] = useSavedSetting<MarketDataSettings>(
    'swing-scanner.market-data-settings.v2',
    defaultMarketDataSettings
  );
  const [resultFilters, setResultFilters] = useLocalStorage<ScannerResultFilters>(
    'swing-scanner.candidates.result-filters.v1',
    defaultScannerResultFilters,
    normalizeScannerResultFilters
  );
  const [candidateSort, setCandidateSort] = useLocalStorage<CandidateSort>(
    'swing-scanner.candidates.sort.v1',
    { key: 'score', direction: 'desc' }
  );
  const [candidateColumnWidths, setCandidateColumnWidths] =
    useLocalStorage<ScannerColumnWidths>(
      'swing-scanner.candidates.column-widths.v1',
      { ...defaultScannerColumnWidths },
      normalizeScannerColumnWidths
    );
  const [candidateColumnVisibility, setCandidateColumnVisibility] =
    useLocalStorage<ScannerColumnVisibility>(
      'swing-scanner.candidates.column-visibility.v1',
      { ...defaultScannerColumnVisibility },
      normalizeScannerColumnVisibility
    );
  const updateTradeLevels = useUpdateCandidateTradeLevels();
  const rows = latestWatchlist.data?.rows ?? [];
  const allCandidates = useMemo(
    () =>
      rows.map((row, index) =>
        candidateFromWatchlistRow(row, index, cacheOverview.data?.latest_bar_date)
      ),
    [cacheOverview.data?.latest_bar_date, rows]
  );
  const savedWatchlistCandidates = useMemo(
    () =>
      (savedWatchlistContext.data?.items ?? []).map((item, index) =>
        candidateFromWatchlistRow(
          { ...item.data, Ticker: item.ticker },
          index,
          cacheOverview.data?.latest_bar_date
        )
      ),
    [cacheOverview.data?.latest_bar_date, savedWatchlistContext.data?.items]
  );
  const availableChartCandidates = incomingSavedWatchlistId !== null
    ? savedWatchlistCandidates
    : allCandidates;
  const valuationMode =
    rows.length > 0 &&
    rows.every((row) =>
      String(row['Triggered Strategies'] ?? '').toLowerCase().includes('undervalued')
    );
  const candidateColumns: ScannerColumnKey[] = scannerColumnsForMode(valuationMode).filter(
    (key) => key !== 'select'
  );
  const configurableCandidateColumns = candidateColumns.filter((key) => key !== 'ticker');
  const visibleCandidateColumns = candidateColumns.filter(
    (key) => candidateColumnVisibility[key]
  );
  const candidateTableWidth = visibleCandidateColumns.reduce(
    (total, key) => total + candidateColumnWidths[key],
    0
  );
  const filteredRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          rowMatchesDisplaySettings(row, displaySettings) &&
          rowMatchesScannerResultFilters(row, resultFilters)
      ),
    [displaySettings, resultFilters, rows]
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
  const activeResultFilterCount = countActiveScannerResultFilters(resultFilters);
  const allConfigurableColumnsVisible = configurableCandidateColumns.every(
    (key) => candidateColumnVisibility[key]
  );
  const [selectedTicker, setSelectedTicker] = useLocalStorage<string | null>(
    'swing-scanner.candidates.selected-ticker',
    incomingTicker
  );
  const selectedFromAvailableCandidates =
    availableChartCandidates.find((candidate) => candidate.ticker === selectedTicker) ?? null;
  const chartCandidates = incomingSavedWatchlistId !== null
    ? availableChartCandidates
    : selectedFromAvailableCandidates &&
        !sortedCandidates.some(
          (candidate) => candidate.ticker === selectedFromAvailableCandidates.ticker
        )
      ? [selectedFromAvailableCandidates, ...sortedCandidates]
      : sortedCandidates;
  const appliedCandidateState = useRef<string | null>(null);
  useEffect(() => {
    if (!incomingTicker) {
      return;
    }

    const stateKey = `${incomingTicker}:${maximizeIncomingTicker}:${incomingSavedWatchlistId ?? ''}`;
    if (appliedCandidateState.current === stateKey) {
      return;
    }
    if (
      maximizeIncomingTicker &&
      !availableChartCandidates.some((candidate) => candidate.ticker === incomingTicker)
    ) {
      return;
    }

    appliedCandidateState.current = stateKey;
    setSelectedTicker(incomingTicker);
    rememberRecentTicker(incomingTicker, 'candidates', incomingSavedWatchlistId);
    if (maximizeIncomingTicker) {
      openMaximizedTicker(incomingTicker);
    }
  }, [
    availableChartCandidates,
    incomingSavedWatchlistId,
    incomingTicker,
    maximizeIncomingTicker,
    setSelectedTicker
  ]);
  const selected =
    chartCandidates.find((candidate) => candidate.ticker === selectedTicker) ??
    chartCandidates[0];
  const [edits, setEdits] = useCandidateEdits();
  const selectedEdits = selected ? edits[selected.ticker] : undefined;
  const [chartFrequency, setChartFrequency] = useLocalStorage<ChartFrequency>(
    'swing-scanner.candidates.chart-frequency',
    defaultChartFrequency
  );
  const chartRange = chartFrequencyOption(chartFrequency);
  const historyQuery = useMarketDataHistory(
    selected?.ticker ?? null,
    marketDataSettings.primaryProvider,
    chartRange.period,
    chartRange.interval
  );
  const entry = selectedEdits?.entry ?? selected?.entryArea ?? 'n/a';
  const stop = selectedEdits?.stop ?? selected?.stop ?? 'n/a';
  const target = selectedEdits?.target ?? selected?.targetExit ?? 'n/a';
  const chartHeight = selectedEdits?.chartHeight ?? 300;
  const chartZoom = selectedEdits?.chartZoom ?? 1;
  const chartPanBars = selectedEdits?.chartPanBars ?? 0;
  const chartPricePan = selectedEdits?.chartPricePan ?? 0;
  const maximizedChartHeight = selectedEdits?.maximizedChartHeight;
  const maximizedChartWidth = selectedEdits?.maximizedChartWidth;
  const [detailPanelWidth, setDetailPanelWidth] = useLocalStorage<number>(
    'swing-scanner.candidates.detail-panel-width',
    520
  );
  const previousChartHeight = selectedEdits?.previousChartHeight;
  const chartMaximized = Boolean(previousChartHeight);

  function selectCandidateTicker(ticker: string) {
    setSelectedTicker(ticker);
    rememberRecentTicker(ticker, 'candidates', incomingSavedWatchlistId);
  }

  function updateSelected(changes: Partial<CandidateTradeEdits>) {
    if (!selected) {
      return;
    }

    const defaults: CandidateTradeEdits = {
      entry: selected.entryArea,
      stop: selected.stop,
      target: selected.targetExit,
      chartHeight,
      chartPanBars,
      chartPricePan,
      maximizedChartHeight,
      maximizedChartWidth
    };

    setEdits((current) => ({
      ...current,
      [selected.ticker]: {
        ...defaults,
        ...current[selected.ticker],
        ...changes
      }
    }));
  }

  function updateChartLevel(level: ChartLevelKey, value: number) {
    const roundedValue = value.toFixed(2);

    if (level === 'entry') {
      const currentEntry = parseDisplayNumber(entry);
      const currentStop = parseDisplayNumber(stop);
      const currentTarget = parseDisplayNumber(target);
      const delta = currentEntry === null ? 0 : value - currentEntry;

      updateSelected({
        entry: roundedValue,
        stop: currentStop === null ? stop : (currentStop + delta).toFixed(2),
        target: currentTarget === null ? target : (currentTarget + delta).toFixed(2)
      });
      return;
    }

    if (level === 'stop') {
      updateSelected({ stop: roundedValue });
      return;
    }

    updateSelected({ target: roundedValue });
  }

  function updateChartFrequency(frequency: ChartFrequency) {
    setChartFrequency(frequency);
    updateSelected({
      chartZoom: 1,
      chartPanBars: 0,
      chartPricePan: 0
    });
  }

  function selectMaximizedTicker(ticker: string) {
    const nextCandidate = availableChartCandidates.find((candidate) => candidate.ticker === ticker);
    if (!nextCandidate || nextCandidate.ticker === selected?.ticker) {
      return;
    }

    setEdits((current) => {
      const existing = current[nextCandidate.ticker];
      const nextChartHeight = existing?.chartHeight ?? 300;

      return {
        ...current,
        [nextCandidate.ticker]: {
          entry: existing?.entry ?? nextCandidate.entryArea,
          stop: existing?.stop ?? nextCandidate.stop,
          target: existing?.target ?? nextCandidate.targetExit,
          chartHeight: nextChartHeight,
          chartZoom: 1,
          chartPanBars: 0,
          chartPricePan: 0,
          maximizedChartHeight: viewportChartHeight(),
          maximizedChartWidth: viewportChartWidth(),
          previousChartHeight: nextChartHeight
        }
      };
    });
    selectCandidateTicker(nextCandidate.ticker);
  }

  function openMaximizedTicker(ticker: string) {
    const nextCandidate = availableChartCandidates.find((candidate) => candidate.ticker === ticker);
    if (!nextCandidate) {
      return;
    }

    setEdits((current) => {
      const existing = current[nextCandidate.ticker];
      const nextChartHeight = existing?.chartHeight ?? 300;

      return {
        ...current,
        [nextCandidate.ticker]: {
          entry: existing?.entry ?? nextCandidate.entryArea,
          stop: existing?.stop ?? nextCandidate.stop,
          target: existing?.target ?? nextCandidate.targetExit,
          chartHeight: nextChartHeight,
          chartZoom: existing?.chartZoom ?? 1,
          chartPanBars: existing?.chartPanBars ?? 0,
          chartPricePan: existing?.chartPricePan ?? 0,
          maximizedChartHeight: existing?.maximizedChartHeight ?? viewportChartHeight(),
          maximizedChartWidth: existing?.maximizedChartWidth ?? viewportChartWidth(),
          previousChartHeight: existing?.previousChartHeight ?? nextChartHeight
        }
      };
    });
    selectCandidateTicker(nextCandidate.ticker);
  }

  function traverseMaximizedCandidates(direction: -1 | 1) {
    if (!selected || chartCandidates.length < 2) {
      return;
    }

    const selectedIndex = chartCandidates.findIndex(
      (candidate) => candidate.ticker === selected.ticker
    );
    const nextIndex =
      (selectedIndex + direction + chartCandidates.length) % chartCandidates.length;
    selectMaximizedTicker(chartCandidates[nextIndex].ticker);
  }

  function changeSort(key: CandidateSortKey) {
    setCandidateSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc'
    }));
  }

  function changeResultFilter<K extends keyof ScannerResultFilters>(
    key: K,
    value: ScannerResultFilters[K]
  ) {
    setResultFilters((current) => ({ ...current, [key]: value }));
  }

  function clearResultFilters() {
    setResultFilters(defaultScannerResultFilters);
  }

  function startColumnResize(
    key: ScannerColumnKey,
    event: ReactPointerEvent<HTMLDivElement>
  ) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = candidateColumnWidths[key];
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    function handleMove(moveEvent: PointerEvent) {
      const nextWidth = clampScannerColumnWidth(
        startWidth + moveEvent.clientX - startX
      );
      setCandidateColumnWidths((current) => ({ ...current, [key]: nextWidth }));
    }

    function handleUp() {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      window.removeEventListener('pointercancel', handleUp);
    }

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    window.addEventListener('pointercancel', handleUp);
  }

  function resizeColumnBy(key: ScannerColumnKey, delta: number) {
    setCandidateColumnWidths((current) => ({
      ...current,
      [key]: clampScannerColumnWidth(current[key] + delta)
    }));
  }

  function autoFitColumn(key: ScannerColumnKey) {
    const table = candidateResultsTableRef.current;
    const columnIndex = visibleCandidateColumns.indexOf(key);
    if (!table || columnIndex < 0) return;

    const column = table.querySelectorAll('col')[columnIndex] as
      | HTMLTableColElement
      | undefined;
    if (!column) return;

    const previousTableLayout = table.style.tableLayout;
    const previousTableWidth = table.style.width;
    const previousTableMinWidth = table.style.minWidth;
    const previousColumnWidth = column.style.width;
    let measuredWidth = candidateColumnWidths[key];

    try {
      table.style.tableLayout = 'auto';
      table.style.width = 'max-content';
      table.style.minWidth = '0';
      column.style.width = 'auto';
      void table.offsetWidth;
      const contentWidths = Array.from(table.rows)
        .map((row) => row.cells[columnIndex]?.scrollWidth ?? 0)
        .filter((width) => width > 0);
      measuredWidth =
        contentWidths.length > 0
          ? Math.max(...contentWidths)
          : defaultScannerColumnWidths[key];
    } finally {
      table.style.tableLayout = previousTableLayout;
      table.style.width = previousTableWidth;
      table.style.minWidth = previousTableMinWidth;
      column.style.width = previousColumnWidth;
    }

    setCandidateColumnWidths((current) => ({
      ...current,
      [key]: clampScannerColumnWidth(measuredWidth + 2)
    }));
  }

  function toggleCandidateColumn(key: ScannerColumnKey) {
    setCandidateColumnVisibility((current) => ({
      ...current,
      [key]: !current[key]
    }));
  }

  function showAllCandidateColumns() {
    setCandidateColumnVisibility((current) => ({
      ...current,
      ...Object.fromEntries(configurableCandidateColumns.map((key) => [key, true]))
    }));
  }

  function startDetailResize(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = detailPanelWidth;

    function handleMove(moveEvent: PointerEvent) {
      const nextWidth = Math.min(Math.max(startWidth - (moveEvent.clientX - startX), 420), 900);
      setDetailPanelWidth(nextWidth);
    }

    function handleUp() {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    }

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
  }

  function toggleChartMaximize() {
    if (chartMaximized) {
      updateSelected({
        chartHeight: previousChartHeight ?? chartHeight,
        previousChartHeight: undefined
      });
      return;
    }

    updateSelected({
      previousChartHeight: chartHeight,
      maximizedChartHeight: maximizedChartHeight ?? viewportChartHeight(),
      maximizedChartWidth: maximizedChartWidth ?? viewportChartWidth()
    });
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

  const layoutStyle = {
    '--candidate-detail-width': `${detailPanelWidth}px`
  } as CSSProperties;
  const selectedChart = selected ? (
    <CandidateDailyBarChart
      height={chartHeight}
      zoom={chartZoom}
      ticker={selected.ticker}
      companyName={selected.companyName}
      tickerOptions={chartCandidates.map((candidate) => ({
        ticker: candidate.ticker,
        strategy: candidate.strategy
      }))}
      onTickerChange={selectMaximizedTicker}
      onPreviousTicker={() => traverseMaximizedCandidates(-1)}
      onNextTicker={() => traverseMaximizedCandidates(1)}
      frequency={chartFrequency}
      onFrequencyChange={updateChartFrequency}
      history={historyQuery.data?.rows ?? []}
      loading={historyQuery.isLoading || historyQuery.isFetching}
      error={historyQuery.error?.message}
      entry={entry}
      stop={stop}
      target={target}
      onLevelChange={updateChartLevel}
      onZoomChange={(zoom) => updateSelected({ chartZoom: zoom })}
      panBars={chartPanBars}
      pricePan={chartPricePan}
      onPanChange={(pan) => updateSelected(pan)}
      maximized={chartMaximized}
      onToggleMaximize={toggleChartMaximize}
      onHeightChange={(height) => updateSelected({ chartHeight: height })}
      width={detailPanelWidth}
      onWidthChange={setDetailPanelWidth}
      maximizedHeight={maximizedChartHeight}
      maximizedWidth={maximizedChartWidth}
      onMaximizedSizeChange={(changes) => updateSelected(changes)}
    />
  ) : null;

  return (
    <>
      <div className="content-grid candidate-layout" style={layoutStyle}>
        <section className="panel candidate-list-panel" aria-labelledby="candidate-list-title">
          <div className="panel-header">
            <div>
              <h2 id="candidate-list-title">Candidates</h2>
              <p>
                {sortedCandidates.length} displayed candidates from {rows.length} saved rows
              </p>
            </div>
            <details className="column-chooser">
              <summary className="secondary-button">Columns</summary>
              <div className="column-chooser-menu" aria-label="Visible candidate columns">
                <strong>Show or hide columns</strong>
                <span className="column-chooser-note">Ticker remains visible.</span>
                <div className="column-chooser-options">
                  {configurableCandidateColumns.map((key) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={candidateColumnVisibility[key]}
                        onChange={() => toggleCandidateColumn(key)}
                      />
                      {scannerColumnLabels[key]}
                    </label>
                  ))}
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={showAllCandidateColumns}
                  disabled={allConfigurableColumnsVisible}
                >
                  Show All
                </button>
              </div>
            </details>
          </div>

          <div className="scanner-result-filter-bar" aria-label="Candidate result filters">
            <div className="scanner-result-filter-grid">
              <MultiSelectFilter
                label="Validation"
                allLabel="All validation statuses"
                selected={resultFilters.validation}
                options={validationResultFilterOptions}
                onChange={(values) => changeResultFilter('validation', values)}
              />
              <MultiSelectFilter
                label="Business Quality"
                allLabel="All quality levels"
                selected={resultFilters.quality}
                options={qualityResultFilterOptions}
                onChange={(values) => changeResultFilter('quality', values)}
              />
              <MultiSelectFilter
                label="DCF Estimate"
                allLabel="All DCF estimates"
                selected={resultFilters.dcf}
                options={dcfResultFilterOptions}
                onChange={(values) => changeResultFilter('dcf', values)}
              />
              <MultiSelectFilter
                label="Risk"
                allLabel="All risk levels"
                selected={resultFilters.risk}
                options={riskResultFilterOptions}
                onChange={(values) => changeResultFilter('risk', values)}
              />
              <label>
                Minimum Price
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="No minimum"
                  value={resultFilters.minPrice ?? ''}
                  onChange={(event) =>
                    changeResultFilter('minPrice', priceFilterNumberOrNull(event.target.value))
                  }
                />
              </label>
              <label>
                Maximum Price
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="No maximum"
                  value={resultFilters.maxPrice ?? ''}
                  onChange={(event) =>
                    changeResultFilter('maxPrice', priceFilterNumberOrNull(event.target.value))
                  }
                />
              </label>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={clearResultFilters}
              disabled={activeResultFilterCount === 0}
            >
              Clear Filters{activeResultFilterCount > 0 ? ` (${activeResultFilterCount})` : ''}
            </button>
          </div>

          <div className="table-wrap">
            <table
              ref={candidateResultsTableRef}
              className="data-table scanner-results-table candidate-results-table"
              style={{ width: candidateTableWidth, minWidth: '100%' }}
            >
              <colgroup>
                {visibleCandidateColumns.map((key) => (
                  <col key={key} style={{ width: candidateColumnWidths[key] }} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  {visibleCandidateColumns.map((key) => (
                    <ScannerCandidateHeader
                      key={key}
                      columnKey={key}
                      valuationMode={valuationMode}
                      sort={candidateSort}
                      onSort={changeSort}
                      onResize={startColumnResize}
                      onResizeBy={resizeColumnBy}
                      onAutoFit={autoFitColumn}
                    />
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedCandidates.map((candidate) => (
                  <tr
                    key={candidate.ticker}
                    className={candidate.ticker === selected?.ticker ? 'selected-row' : ''}
                    onClick={() => selectCandidateTicker(candidate.ticker)}
                  >
                    {visibleCandidateColumns.map((key) => (
                      <ScannerCandidateCell
                        key={key}
                        columnKey={key}
                        candidate={candidate}
                        onTickerClick={openMaximizedTicker}
                      />
                    ))}
                  </tr>
                ))}
                {sortedCandidates.length === 0 && (
                  <tr>
                    <td colSpan={visibleCandidateColumns.length} className="empty-cell">
                      No candidates match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <div
          className="candidate-panel-resizer"
          role="separator"
          aria-label="Resize candidate detail panel"
          onPointerDown={startDetailResize}
        />

        <section className="panel" aria-labelledby="candidate-detail-title">
          <div className="panel-header">
            <div>
              <h2 id="candidate-detail-title">{selected?.ticker ?? 'Candidate Detail'}</h2>
              <p>{selected?.strategy ?? 'Select a candidate'}</p>
            </div>
            {selected && (
              <div className="button-row inline-actions">
                <SavedWatchlistButton
                  ticker={selected.ticker}
                  source="candidates"
                  data={candidateSnapshot(
                    selected,
                    rows.find((row) => String(row.Ticker ?? '').toUpperCase() === selected.ticker) ??
                      savedWatchlistContext.data?.items.find(
                        (item) => item.ticker === selected.ticker
                      )?.data
                  )}
                />
                <Link
                  className="link-button"
                  onClick={() =>
                    rememberRecentTicker(
                      selected.ticker,
                      'candidates',
                      incomingSavedWatchlistId
                    )
                  }
                  to={candidateFundamentalsPath(
                    selected.ticker,
                    latestWatchlist.data?.run_id ?? null,
                    incomingSavedWatchlistId
                  )}
                >
                  Fundamental Analysis
                </Link>
              </div>
            )}
          </div>

          {selected ? (
            <div className="detail-stack">
              {!chartMaximized && selectedChart}
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
      {selected && chartMaximized && (
        <div className="chart-maximized-shell" role="dialog" aria-label={`${selected.ticker} maximized chart`}>
          <div className="chart-maximized-watchlist-action">
            <SavedWatchlistButton
              ticker={selected.ticker}
              source="candidates-chart"
              data={candidateSnapshot(
                selected,
                rows.find(
                  (row) => String(row.Ticker ?? '').toUpperCase() === selected.ticker
                ) ??
                  savedWatchlistContext.data?.items.find(
                    (item) => item.ticker === selected.ticker
                  )?.data
              )}
              label="Watchlists"
            />
          </div>
          {selectedChart}
        </div>
      )}
    </>
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
              {(strategies.data ?? [])
                .filter((strategy) => strategy.category === 'entry' && strategy.backtestable)
                .map((strategy) => (
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
  const savedWatchlists = useSavedWatchlists();
  const [selectedWatchlistId, setSelectedWatchlistId] = useLocalStorage<number | null>(
    'swing-scanner.journal.selected-watchlist.v1',
    null,
    normalizePositiveIntegerOrNull
  );
  const watchlistOptions = savedWatchlists.data?.watchlists ?? [];
  const activeWatchlistId = watchlistOptions.some(
    (watchlist) => watchlist.id === selectedWatchlistId
  )
    ? selectedWatchlistId
    : watchlistOptions[0]?.id ?? null;
  const selectedWatchlist = useSavedWatchlist(activeWatchlistId);
  useEffect(() => {
    if (activeWatchlistId !== selectedWatchlistId) {
      setSelectedWatchlistId(activeWatchlistId);
    }
  }, [activeWatchlistId, selectedWatchlistId, setSelectedWatchlistId]);
  const candidates = useMemo(
    () =>
      (selectedWatchlist.data?.items ?? []).map((item, index) =>
        candidateFromWatchlistRow(
          { ...item.data, Ticker: item.ticker },
          index
        )
      ),
    [selectedWatchlist.data?.items]
  );
  const [plannedTrades, setPlannedTrades] = useBusinessCollection('plannedTrades');
  const [selectedPlannedTradeIds, setSelectedPlannedTradeIds] = useLocalStorage<string[]>(
    'swing-scanner.journal.selected-planned-trades.v1',
    [],
    normalizeStringArray
  );
  const selectedPlannedTradeSet = new Set(
    selectedPlannedTradeIds.filter((id) => plannedTrades.some((trade) => trade.id === id))
  );

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
    setSelectedPlannedTradeIds((current) => current.filter((tradeId) => tradeId !== id));
  }

  function togglePlannedTrade(id: string) {
    setSelectedPlannedTradeIds((current) =>
      current.includes(id)
        ? current.filter((tradeId) => tradeId !== id)
        : [...current, id]
    );
  }

  function toggleAllPlannedTrades() {
    const allSelected = plannedTrades.length > 0 && plannedTrades.every(
      (trade) => selectedPlannedTradeSet.has(trade.id)
    );
    setSelectedPlannedTradeIds(allSelected ? [] : plannedTrades.map((trade) => trade.id));
  }

  function removeSelectedTrades() {
    if (selectedPlannedTradeSet.size === 0) return;
    setPlannedTrades((current) =>
      current.filter((trade) => !selectedPlannedTradeSet.has(trade.id))
    );
    setSelectedPlannedTradeIds([]);
  }

  function addAllCandidates() {
    setPlannedTrades((current) => {
      const existingTickers = new Set(current.map((trade) => trade.ticker));
      const additions = candidates
        .filter((candidate) => !existingTickers.has(candidate.ticker))
        .map(plannedTradeFromCandidate);
      return [...additions, ...current];
    });
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
              <p>Editable trades created from saved watchlists</p>
            </div>
            <button
              className="danger-button"
              type="button"
              disabled={selectedPlannedTradeSet.size === 0}
              onClick={removeSelectedTrades}
            >
              <Trash2 size={16} />
              Remove Selected{selectedPlannedTradeSet.size > 0
                ? ` (${selectedPlannedTradeSet.size})`
                : ''}
            </button>
          </div>
          <div className="table-wrap compact-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="Select all planned trades"
                      checked={plannedTrades.length > 0 && plannedTrades.every(
                        (trade) => selectedPlannedTradeSet.has(trade.id)
                      )}
                      onChange={toggleAllPlannedTrades}
                    />
                  </th>
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
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${trade.ticker}`}
                        checked={selectedPlannedTradeSet.has(trade.id)}
                        onChange={() => togglePlannedTrade(trade.id)}
                      />
                    </td>
                    <td className="ticker-cell">{trade.ticker}</td>
                    <td>{trade.strategy}</td>
                    <td>{trade.plannedAt}</td>
                    <td>{trade.entry}</td>
                    <td>{trade.stop}</td>
                    <td>{trade.target}</td>
                    <td>
                      <button className="link-button danger-link" onClick={() => deleteTrade(trade.id)}>
                        <Trash2 size={15} />
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
                {plannedTrades.length === 0 && (
                  <tr>
                    <td colSpan={8} className="empty-cell">No planned trades yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel" aria-labelledby="add-from-watchlist-title">
          <div className="panel-header">
            <div>
              <h2 id="add-from-watchlist-title">Add From Watchlist</h2>
              <p>Creates planned trades that can later be reconciled with broker fills</p>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={addAllCandidates}
              disabled={candidates.length === 0 || candidates.every((candidate) =>
                plannedTrades.some((trade) => trade.ticker === candidate.ticker)
              )}
            >
              <Save size={16} />
              Add All
            </button>
          </div>
          <label className="journal-watchlist-select">
            Watchlist
            <select
              value={activeWatchlistId ?? ''}
              onChange={(event) => setSelectedWatchlistId(Number(event.target.value) || null)}
            >
              {watchlistOptions.length === 0 && <option value="">No saved watchlists</option>}
              {watchlistOptions.map((watchlist) => (
                <option key={watchlist.id} value={watchlist.id}>
                  {watchlist.name} ({watchlist.item_count})
                </option>
              ))}
            </select>
          </label>
          {savedWatchlists.isError && (
            <AlertMessage tone="danger" message={savedWatchlists.error.message} />
          )}
          {selectedWatchlist.isError && (
            <AlertMessage tone="danger" message={selectedWatchlist.error.message} />
          )}
          <div className="candidate-add-list">
            {candidates.map((candidate) => (
              <button
                key={candidate.ticker}
                className="candidate-add-row"
                onClick={() => addCandidate(candidate)}
                disabled={plannedTrades.some((trade) => trade.ticker === candidate.ticker)}
              >
                <span>
                  <strong>{candidate.ticker}</strong>
                  <small>{candidate.strategy}</small>
                </span>
                {plannedTrades.some((trade) => trade.ticker === candidate.ticker)
                  ? <CheckCircle2 size={16} />
                  : <Save size={16} />}
              </button>
            ))}
            {selectedWatchlist.isLoading && <p className="muted-text">Loading watchlist…</p>}
            {!selectedWatchlist.isLoading && candidates.length === 0 && (
              <p className="muted-text">
                {watchlistOptions.length === 0
                  ? <>Create a <Link to="/watchlists">saved watchlist</Link> to add planned trades.</>
                  : 'This watchlist does not contain any tickers.'}
              </p>
            )}
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
  const [marketDataSettings] = useSavedSetting<MarketDataSettings>(
    'swing-scanner.market-data-settings.v2',
    defaultMarketDataSettings
  );
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
      market_data_provider: marketDataSettings.primaryProvider,
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

function CurrentPriceInfo() {
  const anchorRef = useRef<HTMLSpanElement | null>(null);
  const tooltipId = useId();
  const [tooltipPosition, setTooltipPosition] = useState<{
    left: number;
    top: number;
    width: number;
  } | null>(null);

  function hideTooltip() {
    setTooltipPosition(null);
  }

  function showTooltip() {
    const anchor = anchorRef.current;
    if (!anchor) return;

    const bounds = anchor.getBoundingClientRect();
    const width = Math.min(360, Math.max(160, window.innerWidth - 24));
    const centeredLeft = bounds.left + bounds.width / 2 - width / 2;
    const left = Math.min(
      Math.max(12, centeredLeft),
      Math.max(12, window.innerWidth - width - 12)
    );

    setTooltipPosition({
      left,
      top: bounds.bottom + 8,
      width
    });
  }

  return (
    <>
      <span
        ref={anchorRef}
        className="current-price-info-icon"
        aria-label={currentPriceInfoText}
        aria-describedby={tooltipPosition ? tooltipId : undefined}
        role="img"
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
      >
        <Info size={14} aria-hidden="true" />
      </span>
      {tooltipPosition &&
        createPortal(
          <span
            id={tooltipId}
            className="current-price-tooltip"
            role="tooltip"
            style={tooltipPosition}
          >
            {currentPriceInfoText}
          </span>,
          document.body
        )}
    </>
  );
}

function ScannerCandidateHeader({
  columnKey,
  valuationMode,
  sort,
  onSort,
  onResize,
  onResizeBy,
  onAutoFit
}: {
  columnKey: ScannerColumnKey;
  valuationMode: boolean;
  sort: CandidateSort;
  onSort: (key: CandidateSortKey) => void;
  onResize: (key: ScannerColumnKey, event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizeBy: (key: ScannerColumnKey, delta: number) => void;
  onAutoFit: (key: ScannerColumnKey) => void;
}) {
  const label = scannerColumnHeaderLabel(columnKey, valuationMode);

  return (
    <SortableHeader
      label={label}
      sortKey={scannerColumnSortKey(columnKey)}
      columnKey={columnKey}
      resizeLabel={scannerColumnLabels[columnKey]}
      sort={sort}
      onSort={onSort}
      onResize={onResize}
      onResizeBy={onResizeBy}
      onAutoFit={onAutoFit}
    />
  );
}

function ScannerCandidateCell({
  columnKey,
  candidate,
  onTickerClick
}: {
  columnKey: ScannerColumnKey;
  candidate: DisplayCandidate;
  onTickerClick: (ticker: string) => void;
}) {
  switch (columnKey) {
    case 'ticker':
      return (
        <td className="ticker-cell">
          <button
            className="ticker-link ticker-link-button"
            type="button"
            aria-label={`Open ${candidate.ticker} maximized chart`}
            title={`Open ${candidate.ticker} maximized chart`}
            onClick={(event) => {
              event.stopPropagation();
              onTickerClick(candidate.ticker);
            }}
          >
            {candidate.ticker}
          </button>
          {candidate.companyName && (
            <span className="company-name">{candidate.companyName}</span>
          )}
        </td>
      );
    case 'strategy':
      return <td>{candidate.strategy}</td>;
    case 'score':
      return <td>{candidate.score}</td>;
    case 'currentPrice':
      return <td>{candidate.currentPrice}</td>;
    case 'fairValue':
      return <td>{candidate.fairValue}</td>;
    case 'dcfUpside':
      return <td>{candidate.marginOfSafety}</td>;
    case 'validation':
      return (
        <FundamentalSummaryCell
          label={candidate.validationLabel}
          value={scoreOutOf100(candidate.validationScore)}
        />
      );
    case 'quality':
      return (
        <FundamentalSummaryCell
          label={candidate.qualityLabel}
          value={scoreOutOf100(candidate.qualityScore)}
        />
      );
    case 'dcfEstimate':
      return (
        <FundamentalSummaryCell
          label={candidate.dcfLabel}
          value={candidate.marginOfSafety}
        />
      );
    case 'risk':
      return (
        <FundamentalSummaryCell
          label={candidate.riskLabel}
          value={scoreOutOf100(candidate.riskScore)}
        />
      );
    case 'relativeStrength':
      return <td>{candidate.relativeStrength}</td>;
    case 'relativeVolume':
      return <td>{candidate.relativeVolume}</td>;
    case 'atr':
      return <td>{candidate.atr}</td>;
    case 'fiveDayRange':
      return <td>{candidate.fiveDayRange}</td>;
    case 'entry':
      return <td>{candidate.entryArea}</td>;
    case 'stop':
      return <td>{candidate.stop}</td>;
    case 'target':
      return <td>{candidate.targetExit}</td>;
    case 'select':
      return null;
  }
}

function scannerColumnSortKey(columnKey: ScannerColumnKey): CandidateSortKey {
  switch (columnKey) {
    case 'select':
    case 'ticker':
      return 'ticker';
    case 'strategy':
      return 'strategy';
    case 'score':
      return 'score';
    case 'currentPrice':
      return 'currentPrice';
    case 'fairValue':
      return 'fairValue';
    case 'dcfUpside':
    case 'dcfEstimate':
      return 'marginOfSafety';
    case 'validation':
      return 'validationScore';
    case 'quality':
      return 'qualityScore';
    case 'risk':
      return 'riskScore';
    case 'relativeStrength':
      return 'relativeStrength';
    case 'relativeVolume':
      return 'relativeVolume';
    case 'atr':
      return 'atr';
    case 'fiveDayRange':
      return 'fiveDayRange';
    case 'entry':
      return 'entryArea';
    case 'stop':
      return 'stop';
    case 'target':
      return 'targetExit';
  }
}

function scannerColumnHeaderLabel(
  columnKey: ScannerColumnKey,
  valuationMode: boolean
): ReactNode {
  switch (columnKey) {
    case 'score':
      return valuationMode ? 'Strategy Score' : 'Score';
    case 'currentPrice':
      return (
        <span className="th-with-info">
          Current Price
          <CurrentPriceInfo />
        </span>
      );
    case 'relativeStrength':
      return 'RS';
    case 'relativeVolume':
      return 'RVOL';
    case 'select':
      return '';
    default:
      return scannerColumnLabels[columnKey];
  }
}

function SortableHeader({
  label,
  sortKey,
  columnKey,
  resizeLabel,
  sort,
  onSort,
  onResize,
  onResizeBy,
  onAutoFit
}: {
  label: ReactNode;
  sortKey: CandidateSortKey;
  columnKey: ScannerColumnKey;
  resizeLabel?: string;
  sort: CandidateSort;
  onSort: (key: CandidateSortKey) => void;
  onResize: (key: ScannerColumnKey, event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizeBy: (key: ScannerColumnKey, delta: number) => void;
  onAutoFit: (key: ScannerColumnKey) => void;
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
      <ColumnResizeHandle
        label={resizeLabel ?? String(label)}
        columnKey={columnKey}
        onResize={onResize}
        onResizeBy={onResizeBy}
        onAutoFit={onAutoFit}
      />
    </th>
  );
}

function ColumnResizeHandle({
  label,
  columnKey,
  onResize,
  onResizeBy,
  onAutoFit
}: {
  label: string;
  columnKey: ScannerColumnKey;
  onResize: (key: ScannerColumnKey, event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizeBy: (key: ScannerColumnKey, delta: number) => void;
  onAutoFit: (key: ScannerColumnKey) => void;
}) {
  return (
    <div
      className="column-resize-handle"
      role="separator"
      aria-label={`Resize ${label} column`}
      aria-orientation="vertical"
      title={`Drag to resize ${label}; double-click to fit content`}
      tabIndex={0}
      onPointerDown={(event) => onResize(columnKey, event)}
      onDoubleClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onAutoFit(columnKey);
      }}
      onKeyDown={(event) => {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
        event.preventDefault();
        event.stopPropagation();
        onResizeBy(columnKey, event.key === 'ArrowLeft' ? -8 : 8);
      }}
    />
  );
}

function FundamentalSummaryCell({ label, value }: { label: string; value: string | null }) {
  const calculated = label !== 'Not calculated';
  return (
    <td className="fundamental-summary-cell">
      <strong>{label}</strong>
      {calculated && value && value !== 'n/a' && <span>{value}</span>}
    </td>
  );
}

function scoreOutOf100(value: string): string | null {
  return value === 'n/a' ? null : `${value}/100`;
}

function countActiveScannerResultFilters(filters: ScannerResultFilters): number {
  const classificationCount = [
    filters.validation,
    filters.quality,
    filters.dcf,
    filters.risk
  ].filter((value) => value.length > 0).length;

  return classificationCount +
    (filters.minPrice === null ? 0 : 1) +
    (filters.maxPrice === null ? 0 : 1);
}

function scannerColumnsForMode(valuationMode: boolean): ScannerColumnKey[] {
  const summaryColumns: ScannerColumnKey[] = [
    'validation',
    'quality',
    'dcfEstimate',
    'risk'
  ];
  return valuationMode
    ? [
        'select',
        'ticker',
        'strategy',
        'score',
        'currentPrice',
        'fairValue',
        'dcfUpside',
        ...summaryColumns
      ]
    : [
        'select',
        'ticker',
        'strategy',
        'score',
        'currentPrice',
        ...summaryColumns,
        'relativeStrength',
        'relativeVolume',
        'atr',
        'fiveDayRange',
        'entry',
        'stop',
        'target'
      ];
}

function fundamentalsPath(
  ticker: string,
  runId: number | null,
  strategy: string
): string {
  const params = new URLSearchParams({ ticker, strategy });
  if (runId !== null) params.set('run_id', String(runId));
  return `/fundamentals?${params.toString()}`;
}

function candidateFundamentalsPath(
  ticker: string,
  runId: number | null,
  savedWatchlistId: number | null
): string {
  const params = new URLSearchParams({ ticker, strategy: 'all' });
  if (savedWatchlistId !== null) {
    params.set('watchlist_id', String(savedWatchlistId));
  } else if (runId !== null) {
    params.set('run_id', String(runId));
  }
  return `/fundamentals?${params.toString()}`;
}

function candidateSnapshot(
  candidate: DisplayCandidate,
  raw?: WatchlistRow
): WatchlistRow {
  return {
    'Company Name': candidate.companyName,
    'Triggered Strategies': candidate.strategy,
    'Composite Score': candidate.score,
    'Current Price': candidate.currentPrice,
    'Fair Value': candidate.fairValue,
    'Margin of Safety': candidate.marginOfSafety,
    'Validation Label': candidate.validationLabel,
    'Validation Score': candidate.validationScore,
    'Quality Label': candidate.qualityLabel,
    'Quality Score': candidate.qualityScore,
    'Valuation Label': candidate.dcfLabel,
    'Risk Level': candidate.riskLabel,
    'Risk Score': candidate.riskScore,
    'Entry Area': candidate.entryArea,
    'Suggested Stop': candidate.stop,
    'Target/Exit': candidate.targetExit,
    ...(raw ?? {}),
    Ticker: candidate.ticker
  };
}

function viewportChartHeight() {
  if (typeof window === 'undefined') {
    return 640;
  }

  return Math.max(360, window.innerHeight - 48);
}

function viewportChartWidth() {
  if (typeof window === 'undefined') {
    return 900;
  }

  const sidebarWidth = window.matchMedia('(max-width: 980px)').matches ? 0 : 232;
  return Math.max(420, window.innerWidth - sidebarWidth - 48);
}

function formatChartTime(value: string, frequency: ChartFrequency) {
  const date = new Date(value.includes('T') ? value : `${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  if (frequency === '1d') {
    return new Intl.DateTimeFormat(undefined, {
      hour: 'numeric',
      minute: '2-digit'
    }).format(date);
  }

  if (frequency === '1w') {
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      hour: 'numeric',
      minute: '2-digit'
    }).format(date);
  }

  if (frequency === '5y') {
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      year: 'numeric'
    }).format(date);
  }

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric'
  }).format(date);
}

function CandidateDailyBarChart({
  ticker,
  companyName,
  tickerOptions,
  onTickerChange,
  onPreviousTicker,
  onNextTicker,
  history,
  height,
  zoom,
  frequency,
  onFrequencyChange,
  loading,
  error,
  entry,
  stop,
  target,
  onLevelChange,
  onZoomChange,
  panBars,
  pricePan,
  onPanChange,
  maximized,
  onToggleMaximize,
  onHeightChange,
  width,
  onWidthChange,
  maximizedHeight,
  maximizedWidth,
  onMaximizedSizeChange
}: {
  ticker: string;
  companyName: string;
  tickerOptions: { ticker: string; strategy: string }[];
  onTickerChange: (ticker: string) => void;
  onPreviousTicker: () => void;
  onNextTicker: () => void;
  history: MarketDataHistoryPoint[];
  height: number;
  zoom: number;
  frequency: ChartFrequency;
  onFrequencyChange: (frequency: ChartFrequency) => void;
  loading: boolean;
  error?: string;
  entry: string;
  stop: string;
  target: string;
  onLevelChange: (level: ChartLevelKey, value: number) => void;
  onZoomChange: (zoom: number) => void;
  panBars: number;
  pricePan: number;
  onPanChange: (pan: Partial<Pick<CandidateTradeEdits, 'chartPanBars' | 'chartPricePan'>>) => void;
  maximized: boolean;
  onToggleMaximize: () => void;
  onHeightChange?: (height: number) => void;
  width?: number;
  onWidthChange?: (width: number) => void;
  maximizedHeight?: number;
  maximizedWidth?: number;
  onMaximizedSizeChange?: (changes: Partial<Pick<CandidateTradeEdits, 'maximizedChartHeight' | 'maximizedChartWidth'>>) => void;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const priceScaleWidth = 76;
  const timeAxisHeight = 34;
  const frequencyBarHeight = maximized ? 58 : 0;
  const chartFooterHeight = timeAxisHeight + frequencyBarHeight;
  const frequencyOption = chartFrequencyOption(frequency);
  const maximizedMinHeight = 360;
  const maximizedMinWidth = 420;
  const maximizedMaxHeight = 6000;
  const maximizedMaxWidth = 8000;
  const dimensionZoomFactor = 1.25;
  const [chartContainerWidth, setChartContainerWidth] = useState(1000);
  const [maximizedViewport, setMaximizedViewport] = useState({
    scrollLeft: 0,
    scrollTop: 0,
    width: viewportChartWidth(),
    height: viewportChartHeight()
  });
  const resolvedMaximizedHeight = maximizedHeight ?? viewportChartHeight();
  const resolvedMaximizedWidth = maximizedWidth ?? viewportChartWidth();
  const maximizedFitHeight = Math.max(maximizedMinHeight, maximizedViewport.height);
  const maximizedFitWidth = Math.max(maximizedMinWidth, maximizedViewport.width);
  const maximizedDisplayHeight = Math.max(resolvedMaximizedHeight, maximizedFitHeight);
  const maximizedDisplayWidth = Math.max(resolvedMaximizedWidth, maximizedFitWidth);
  const chartHeight = maximized ? maximizedDisplayHeight : Math.max(240, height);
  const chartWidth = Math.max(
    320,
    (maximized ? resolvedMaximizedWidth : chartContainerWidth) - priceScaleWidth
  );
  const plotSvgHeight = Math.max(
    180,
    (maximized ? resolvedMaximizedHeight : chartHeight) - chartFooterHeight
  );
  const chartZoom = Math.min(Math.max(zoom, 1), 8);
  const padding = { top: 22, right: 18, bottom: 28, left: 28 };
  const bars = history
    .map((row) => ({
      ...row,
      open: row.open ?? row.close,
      high: row.high ?? row.close,
      low: row.low ?? row.close
    }))
    .filter((row) => Number.isFinite(row.close));
  const levelValues = [
    { key: 'target' as const, label: 'Target', value: parseDisplayNumber(target), danger: false },
    { key: 'entry' as const, label: 'Entry', value: parseDisplayNumber(entry), danger: false },
    { key: 'stop' as const, label: 'Stop', value: parseDisplayNumber(stop), danger: true }
  ].filter((level): level is { key: ChartLevelKey; label: string; value: number; danger: boolean } =>
    typeof level.value === 'number'
  );
  const priceValues = [
    ...bars.flatMap((bar) => [bar.high, bar.low, bar.open, bar.close]),
    ...bars.flatMap((bar) => [bar.sma_50, bar.sma_200]),
    ...levelValues.map((level) => level.value)
  ].filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  const fallbackPrice = levelValues[0]?.value ?? 1;
  const minPrice = priceValues.length > 0 ? Math.min(...priceValues) : fallbackPrice;
  const maxPrice = priceValues.length > 0 ? Math.max(...priceValues) : fallbackPrice;
  const pricePadding = Math.max((maxPrice - minPrice) * 0.06, maxPrice * 0.01, 1);
  const baseDomainMin = minPrice - pricePadding;
  const baseDomainMax = maxPrice + pricePadding;
  const domainMin = baseDomainMin + pricePan;
  const domainMax = baseDomainMax + pricePan;
  const plotWidth = chartWidth - padding.left - padding.right;
  const plotHeight = plotSvgHeight - padding.top - padding.bottom;
  const visibleCount = bars.length > 0
    ? Math.min(bars.length, Math.max(20, Math.ceil(bars.length / chartZoom)))
    : 0;
  // Keep one plot-width of horizontal breathing room on both sides. A smaller
  // future-side allowance made a leftward drag appear to stop immediately when
  // the chart was already positioned at the newest bar.
  const overscrollBars = visibleCount;
  const minPanBars = -overscrollBars;
  const maxPanBars = Math.max(0, bars.length - visibleCount) + overscrollBars;
  const clampedPanBars = Math.min(Math.max(panBars, minPanBars), maxPanBars);
  const visibleStartFloat = visibleCount > 0 ? bars.length - visibleCount - clampedPanBars : 0;
  const visibleSliceStart = Math.max(0, Math.floor(visibleStartFloat) - 1);
  const visibleSliceEnd = visibleCount > 0
    ? Math.min(bars.length, Math.ceil(visibleStartFloat + visibleCount) + 1)
    : 0;
  const visibleBars = visibleCount > 0
    ? bars.slice(visibleSliceStart, visibleSliceEnd).map((bar, index) => ({
        bar,
        sourceIndex: visibleSliceStart + index
      }))
    : [];
  const latestVisibleIndex = Math.min(
    bars.length - 1,
    Math.max(0, Math.round(visibleStartFloat + visibleCount - 1))
  );
  const latestVisiblePrice = bars[latestVisibleIndex]?.close;
  const xStep = visibleCount > 1 ? plotWidth / (visibleCount - 1) : plotWidth;
  const candleBodyWidth = Math.max(3, Math.min(12, xStep * 0.62));
  const maxVisibleVolume = Math.max(
    0,
    ...visibleBars.map(({ bar }) => bar.volume ?? 0)
  );
  const volumeAreaHeight = Math.max(32, plotHeight * 0.18);
  const movingAverageLines = [
    { key: 'sma_50' as const, label: 'MA 50', className: 'ma-50' },
    { key: 'sma_200' as const, label: 'MA 200', className: 'ma-200' }
  ].map((average) => ({
    ...average,
    points: visibleBars
      .filter(
        ({ bar }) =>
          typeof bar[average.key] === 'number' && Number.isFinite(bar[average.key])
      )
      .map(({ bar, sourceIndex }) =>
        `${xForSourceIndex(sourceIndex)},${yFor(bar[average.key] as number)}`
      )
      .join(' ')
  }));
  const fixedYAxisLeft = maximized
    ? pinnedTrailingPosition({
        scrollOffset: maximizedViewport.scrollLeft,
        viewportLength: maximizedViewport.width,
        reservedLength: priceScaleWidth,
        chartLength: maximizedDisplayWidth
      })
    : undefined;
  const fixedXAxisTop = maximized
    ? pinnedTrailingPosition({
        scrollOffset: maximizedViewport.scrollTop,
        viewportLength: maximizedViewport.height,
        reservedLength: chartFooterHeight,
        chartLength: chartHeight
      })
    : undefined;
  const fixedFrequencyBarTop = maximized
    ? pinnedTrailingPosition({
        scrollOffset: maximizedViewport.scrollTop,
        viewportLength: maximizedViewport.height,
        reservedLength: frequencyBarHeight,
        chartLength: chartHeight
      })
    : undefined;

  useEffect(() => {
    const chartElement = chartRef.current;

    if (!chartElement || typeof ResizeObserver === 'undefined') {
      return;
    }

    const observer = new ResizeObserver(([entry]) => {
      if (!entry) {
        return;
      }

      setChartContainerWidth(entry.contentRect.width);
    });

    observer.observe(chartElement);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!maximized) {
      return;
    }

    const shellElement = chartRef.current?.closest<HTMLElement>('.chart-maximized-shell');
    if (!shellElement) {
      return;
    }
    const shell: HTMLElement = shellElement;

    let animationFrame: number | null = null;

    function updateViewport() {
      const styles = window.getComputedStyle(shell);
      const shellBounds = shell.getBoundingClientRect();
      const horizontalPadding =
        Number.parseFloat(styles.paddingLeft) + Number.parseFloat(styles.paddingRight);
      const verticalPadding =
        Number.parseFloat(styles.paddingTop) + Number.parseFloat(styles.paddingBottom);

      setMaximizedViewport({
        scrollLeft: shell.scrollLeft,
        scrollTop: shell.scrollTop,
        width: Math.max(0, shellBounds.width - horizontalPadding),
        height: Math.max(0, shellBounds.height - verticalPadding)
      });
      animationFrame = null;
    }

    function scheduleViewportUpdate() {
      if (animationFrame === null) {
        animationFrame = window.requestAnimationFrame(updateViewport);
      }
    }

    updateViewport();
    shell.addEventListener('scroll', scheduleViewportUpdate, { passive: true });
    window.addEventListener('resize', scheduleViewportUpdate);
    const observer = new ResizeObserver(scheduleViewportUpdate);
    observer.observe(shell);

    return () => {
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
      }
      shell.removeEventListener('scroll', scheduleViewportUpdate);
      window.removeEventListener('resize', scheduleViewportUpdate);
      observer.disconnect();
    };
  }, [maximized]);

  useEffect(() => {
    if (!maximized) {
      return;
    }

    const shell = chartRef.current?.closest<HTMLElement>('.chart-maximized-shell');
    if (!shell) {
      return;
    }

    shell.scrollLeft = 0;
    shell.scrollTop = 0;
  }, [maximized, ticker]);

  function xForSourceIndex(sourceIndex: number) {
    if (visibleCount <= 1) {
      return padding.left + plotWidth / 2;
    }

    return padding.left + (sourceIndex - visibleStartFloat) * xStep;
  }

  function yFor(price: number) {
    if (domainMax === domainMin) {
      return padding.top + plotHeight / 2;
    }

    return padding.top + ((domainMax - price) / (domainMax - domainMin)) * plotHeight;
  }

  function priceForClientY(clientY: number, rect: DOMRect) {
    const relativeY = Math.min(Math.max(clientY - rect.top, padding.top), padding.top + plotHeight);
    const ratio = (relativeY - padding.top) / plotHeight;
    return domainMax - ratio * (domainMax - domainMin);
  }

  function startLevelDrag(level: ChartLevelKey, event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const chart = event.currentTarget.closest<HTMLElement>('.candidate-chart');

    if (!chart) {
      return;
    }

    const rect = chart.getBoundingClientRect();

    function handleMove(moveEvent: PointerEvent) {
      onLevelChange(level, priceForClientY(moveEvent.clientY, rect));
    }

    function handleUp() {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    }

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
  }

  function startChartPan(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) {
      return;
    }

    const targetElement = event.target as HTMLElement;

    if (targetElement.closest('button, .trade-level, .chart-price-scale, .chart-price-labels, .chart-time-axis, .chart-frequency-bar, .chart-dimension-controls')) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    const chartElement = event.currentTarget;
    const pointerId = event.pointerId;
    chartElement.setPointerCapture(pointerId);
    chartElement.classList.add('panning');
    const previousBodyCursor = document.body.style.cursor;
    const previousBodyUserSelect = document.body.style.userSelect;
    document.body.style.cursor = 'grabbing';
    document.body.style.userSelect = 'none';
    const startX = event.clientX;
    const startY = event.clientY;
    const startPanBars = clampedPanBars;
    const startPricePan = pricePan;
    const domainRange = domainMax - domainMin;

    function handleMove(moveEvent: PointerEvent) {
      if (moveEvent.pointerId !== pointerId) {
        return;
      }

      moveEvent.preventDefault();
      const deltaX = moveEvent.clientX - startX;
      const deltaY = moveEvent.clientY - startY;
      const barsMoved = xStep > 0 ? deltaX / xStep : 0;
      const priceDelta = plotHeight > 0 ? (deltaY / plotHeight) * domainRange : 0;
      onPanChange({
        chartPanBars: Math.min(Math.max(startPanBars + barsMoved, minPanBars), maxPanBars),
        chartPricePan: startPricePan + priceDelta
      });
    }

    function handleUp(upEvent?: PointerEvent) {
      if (upEvent && upEvent.pointerId !== pointerId) {
        return;
      }

      if (chartElement.hasPointerCapture(pointerId)) {
        chartElement.releasePointerCapture(pointerId);
      }
      chartElement.classList.remove('panning');
      document.body.style.cursor = previousBodyCursor;
      document.body.style.userSelect = previousBodyUserSelect;
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      window.removeEventListener('pointercancel', handleUp);
      window.removeEventListener('blur', handleWindowBlur);
    }

    function handleWindowBlur() {
      handleUp();
    }

    window.addEventListener('pointermove', handleMove, { passive: false });
    window.addEventListener('pointerup', handleUp);
    window.addEventListener('pointercancel', handleUp);
    window.addEventListener('blur', handleWindowBlur);
  }

  function startPriceScaleResize(event: ReactPointerEvent<HTMLDivElement>) {
    const changeHeight: ((height: number) => void) | undefined = maximized
      ? (nextHeight) => onMaximizedSizeChange?.({ maximizedChartHeight: nextHeight })
      : onHeightChange;

    if (!changeHeight || event.button !== 0) {
      return;
    }

    const applyHeight: (height: number) => void = changeHeight;

    event.preventDefault();
    event.stopPropagation();
    const scaleElement = event.currentTarget;
    scaleElement.setPointerCapture(event.pointerId);
    const startY = event.clientY;
    const startHeight = maximized ? resolvedMaximizedHeight : chartHeight;
    const previousCursor = document.body.style.cursor;
    document.body.style.cursor = 'ns-resize';

    function handleMove(moveEvent: PointerEvent) {
      const maxHeight = maximized ? maximizedMaxHeight : 900;
      const minHeight = maximized ? maximizedMinHeight : 240;
      const nextHeight = Math.min(
        Math.max(startHeight + moveEvent.clientY - startY, minHeight),
        maxHeight
      );
      applyHeight(nextHeight);
    }

    function handleUp() {
      if (scaleElement.hasPointerCapture(event.pointerId)) {
        scaleElement.releasePointerCapture(event.pointerId);
      }
      document.body.style.cursor = previousCursor;
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      window.removeEventListener('pointercancel', handleUp);
    }

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    window.addEventListener('pointercancel', handleUp);
  }

  function startTimeAxisResize(event: ReactPointerEvent<HTMLDivElement>) {
    const changeWidth: ((nextWidth: number) => void) | undefined = maximized
      ? (nextWidth) => onMaximizedSizeChange?.({ maximizedChartWidth: nextWidth })
      : onWidthChange;

    if (!changeWidth || event.button !== 0) {
      return;
    }

    const applyWidth: (nextWidth: number) => void = changeWidth;

    event.preventDefault();
    event.stopPropagation();
    const axisElement = event.currentTarget;
    axisElement.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startWidth = maximized ? resolvedMaximizedWidth : width ?? chartContainerWidth;
    const previousCursor = document.body.style.cursor;
    document.body.style.cursor = 'ew-resize';

    function handleMove(moveEvent: PointerEvent) {
      const maxWidth = maximized ? maximizedMaxWidth : 900;
      const minWidth = maximized ? maximizedMinWidth : 420;
      const nextWidth = Math.min(
        Math.max(startWidth - (moveEvent.clientX - startX), minWidth),
        maxWidth
      );
      applyWidth(nextWidth);
    }

    function handleUp() {
      if (axisElement.hasPointerCapture(event.pointerId)) {
        axisElement.releasePointerCapture(event.pointerId);
      }
      document.body.style.cursor = previousCursor;
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      window.removeEventListener('pointercancel', handleUp);
    }

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    window.addEventListener('pointercancel', handleUp);
  }

  function zoomMaximizedDimension(axis: 'horizontal' | 'vertical', direction: 'in' | 'out') {
    if (!maximized || !onMaximizedSizeChange) {
      return;
    }

    const factor = direction === 'in' ? dimensionZoomFactor : 1 / dimensionZoomFactor;

    if (axis === 'horizontal') {
      onMaximizedSizeChange({
        maximizedChartWidth: Math.min(
          Math.max(Math.round(resolvedMaximizedWidth * factor), maximizedMinWidth),
          maximizedMaxWidth
        )
      });
      return;
    }

    onMaximizedSizeChange({
      maximizedChartHeight: Math.min(
        Math.max(Math.round(resolvedMaximizedHeight * factor), maximizedMinHeight),
        maximizedMaxHeight
      )
    });
  }

  function fitMaximizedChartToView() {
    onMaximizedSizeChange?.({
      maximizedChartHeight: maximizedFitHeight,
      maximizedChartWidth: maximizedFitWidth
    });
  }

  const timeTickCount = Math.min(5, visibleBars.length);
  const timeAxisTicks = timeTickCount > 0
    ? Array.from({ length: timeTickCount }, (_value, tickIndex) => {
        const relativeIndex = timeTickCount === 1
          ? 0
          : Math.round((tickIndex / (timeTickCount - 1)) * (visibleBars.length - 1));
        const sourceIndex = Math.min(
          bars.length - 1,
          Math.max(0, Math.round(visibleStartFloat + relativeIndex))
        );
        return { bar: bars[sourceIndex], sourceIndex };
      })
    : [];

  const gridPrices = [
    domainMax,
    (domainMax * 2 + domainMin) / 3,
    (domainMax + domainMin) / 2,
    (domainMax + domainMin * 2) / 3,
    domainMin
  ];

  return (
    <div
      ref={chartRef}
      className={maximized ? 'candidate-chart zoomable maximized' : 'candidate-chart zoomable'}
      style={{ height: chartHeight, width: maximized ? maximizedDisplayWidth : undefined }}
      onPointerDown={startChartPan}
    >
      <button
        type="button"
        className="chart-maximize-button"
        onClick={onToggleMaximize}
      >
        {maximized ? 'Restore' : 'Maximize'}
      </button>
      {maximized && (
        <div className="chart-dimension-controls" aria-label="Maximized chart zoom controls">
          <div className="chart-ticker-navigation" aria-label="Candidate ticker navigation">
            <button
              type="button"
              aria-label="Previous candidate ticker"
              title="Previous candidate"
              disabled={tickerOptions.length < 2}
              onClick={onPreviousTicker}
            >
              ‹
            </button>
            <div className="chart-ticker-selection">
              <select
                aria-label="Candidate ticker"
                value={ticker}
                onChange={(event) => onTickerChange(event.target.value)}
              >
                {tickerOptions.map((option) => (
                  <option key={option.ticker} value={option.ticker}>
                    {option.ticker} · {option.strategy}
                  </option>
                ))}
              </select>
              <strong className="chart-company-name" title={companyName || undefined}>
                {companyName || 'Company name unavailable'}
              </strong>
            </div>
            <button
              type="button"
              aria-label="Next candidate ticker"
              title="Next candidate"
              disabled={tickerOptions.length < 2}
              onClick={onNextTicker}
            >
              ›
            </button>
          </div>
          <div className="chart-dimension-group">
            <span>Horizontal</span>
            <button
              type="button"
              aria-label="Zoom chart out horizontally"
              title="Zoom out horizontally"
              onClick={() => zoomMaximizedDimension('horizontal', 'out')}
            >
              −
            </button>
            <output>{Math.round((resolvedMaximizedWidth / maximizedFitWidth) * 100)}%</output>
            <button
              type="button"
              aria-label="Zoom chart in horizontally"
              title="Zoom in horizontally"
              onClick={() => zoomMaximizedDimension('horizontal', 'in')}
            >
              +
            </button>
          </div>
          <div className="chart-dimension-group">
            <span>Vertical</span>
            <button
              type="button"
              aria-label="Zoom chart out vertically"
              title="Zoom out vertically"
              onClick={() => zoomMaximizedDimension('vertical', 'out')}
            >
              −
            </button>
            <output>{Math.round((resolvedMaximizedHeight / maximizedFitHeight) * 100)}%</output>
            <button
              type="button"
              aria-label="Zoom chart in vertically"
              title="Zoom in vertically"
              onClick={() => zoomMaximizedDimension('vertical', 'in')}
            >
              +
            </button>
          </div>
          <button
            type="button"
            className="chart-fit-button"
            onClick={fitMaximizedChartToView}
          >
            Fit view
          </button>
        </div>
      )}
      {loading && (
        <div className="chart-state" style={{ bottom: chartFooterHeight }}>
          Loading {frequencyOption.rangeLabel} · {frequencyOption.intervalLabel} bars...
        </div>
      )}
      {error && (
        <div className="chart-state danger" style={{ bottom: chartFooterHeight }}>
          Unable to load {frequencyOption.rangeLabel} history ({frequencyOption.intervalLabel} interval).
        </div>
      )}
      {!loading && !error && bars.length === 0 && (
        <div className="chart-state" style={{ bottom: chartFooterHeight }}>
          No {frequencyOption.rangeLabel} history is available for this candidate ({frequencyOption.intervalLabel} interval).
        </div>
      )}
      {visibleBars.length > 0 && (
        <>
          <svg
            className="candidate-chart-svg"
            viewBox={`0 0 ${chartWidth} ${plotSvgHeight}`}
            role="img"
            aria-label={`${frequencyOption.rangeLabel} ${frequencyOption.intervalLabel} candlestick chart`}
            preserveAspectRatio="none"
            style={
              maximized
                ? {
                    top: 0,
                    right: 'auto',
                    bottom: 'auto',
                    left: 0,
                    width: chartWidth,
                    height: plotSvgHeight
                  }
                : { bottom: chartFooterHeight, right: priceScaleWidth }
            }
          >
            {gridPrices.map((price) => {
              const y = yFor(price);
              return (
                <g key={price}>
                  <line className="chart-grid-svg" x1={padding.left} x2={chartWidth - padding.right} y1={y} y2={y} />
                </g>
              );
            })}
            {visibleBars.map(({ bar, sourceIndex }) => {
              if (!bar.volume || maxVisibleVolume <= 0) {
                return null;
              }

              const x = xForSourceIndex(sourceIndex);
              const rising = bar.close >= bar.open;
              const volumeHeight = (bar.volume / maxVisibleVolume) * volumeAreaHeight;
              return (
                <rect
                  key={`volume-${bar.date}-${sourceIndex}`}
                  className={rising ? 'chart-volume up' : 'chart-volume down'}
                  x={x - candleBodyWidth / 2}
                  y={padding.top + plotHeight - volumeHeight}
                  width={candleBodyWidth}
                  height={volumeHeight}
                />
              );
            })}
            {visibleBars.map(({ bar, sourceIndex }) => {
              const x = xForSourceIndex(sourceIndex);
              const rising = bar.close >= bar.open;
              const openY = yFor(bar.open);
              const closeY = yFor(bar.close);
              const bodyTop = Math.min(openY, closeY);
              const bodyHeight = Math.max(Math.abs(closeY - openY), 2);
              return (
                <g key={`${bar.date}-${sourceIndex}`} className={rising ? 'candlestick up' : 'candlestick down'}>
                  <line className="candlestick-wick" x1={x} x2={x} y1={yFor(bar.high)} y2={yFor(bar.low)} />
                  <rect
                    className="candlestick-body"
                    x={x - candleBodyWidth / 2}
                    y={bodyTop}
                    width={candleBodyWidth}
                    height={bodyHeight}
                    rx={1}
                  />
                </g>
              );
            })}
            {movingAverageLines.map((average) =>
              average.points ? (
                <polyline
                  key={average.key}
                  className={`chart-moving-average ${average.className}`}
                  points={average.points}
                />
              ) : null
            )}
            {levelValues.map((level) => {
              const y = yFor(level.value);
              return (
                <line
                  key={level.label}
                  className={level.danger ? 'chart-level-line danger' : 'chart-level-line'}
                  x1={padding.left}
                  x2={chartWidth - padding.right}
                  y1={y}
                  y2={y}
                />
              );
            })}
          </svg>
          <div className="chart-moving-average-legend" aria-label="Moving average legend">
            {movingAverageLines.map((average) => (
              <span key={average.key} className={average.className}>
                <i />
                {average.label}
              </span>
            ))}
          </div>
          {levelValues.map((level) => (
            <TradeLevel
              key={level.key}
              label={level.label}
              value={level.value.toFixed(2)}
              top={`${yFor(level.value)}px`}
              width={maximized ? chartWidth - padding.left : undefined}
              valueAnchorLeft={maximized ? fixedYAxisLeft : undefined}
              danger={level.danger}
              onPointerDown={(event) => startLevelDrag(level.key, event)}
            />
          ))}
          <div
            className={maximized || onHeightChange ? 'chart-price-scale resizable' : 'chart-price-scale'}
            style={{
              width: priceScaleWidth,
              right: maximized ? 'auto' : 0,
              bottom: chartFooterHeight,
              left: fixedYAxisLeft
            }}
          />
          <div
            className={maximized || onHeightChange ? 'chart-price-labels resizable' : 'chart-price-labels'}
            role="separator"
            aria-label="Resize stock chart vertically"
            aria-orientation="horizontal"
            style={{
              width: priceScaleWidth,
              right: maximized ? 'auto' : 0,
              bottom: chartFooterHeight,
              left: fixedYAxisLeft
            }}
            onPointerDownCapture={startPriceScaleResize}
          >
            {gridPrices.map((price) => (
              <span
                key={price}
                className="chart-price-label"
                style={{ top: yFor(price) }}
              >
                {price.toFixed(2)}
              </span>
            ))}
            {typeof latestVisiblePrice === 'number' && Number.isFinite(latestVisiblePrice) && (
              <strong
                className="chart-current-price"
                style={{ top: yFor(latestVisiblePrice) }}
              >
                {latestVisiblePrice.toFixed(2)}
              </strong>
            )}
          </div>
          <div
            className={maximized || onWidthChange ? 'chart-time-axis resizable' : 'chart-time-axis'}
            role="separator"
            aria-label="Resize stock chart horizontally"
            aria-orientation="vertical"
            style={{
              height: timeAxisHeight,
              right: priceScaleWidth,
              top: fixedXAxisTop,
              bottom: maximized ? 'auto' : frequencyBarHeight
            }}
            onPointerDownCapture={startTimeAxisResize}
          >
            {timeAxisTicks.map(({ bar, sourceIndex }) => (
              <span
                key={`${bar.date}-${sourceIndex}`}
                className="chart-time-label"
                style={{ left: xForSourceIndex(sourceIndex) }}
              >
                {formatChartTime(bar.date, frequency)}
              </span>
            ))}
          </div>
        </>
      )}
      {maximized && (
        <div
          className="chart-frequency-bar"
          aria-label="Chart display range"
          style={{
            top: fixedFrequencyBarTop,
            right: 'auto',
            bottom: 'auto',
            left: maximizedViewport.scrollLeft,
            width: maximizedViewport.width
          }}
        >
          <div className="chart-frequency-options">
            {chartFrequencyOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={option.value === frequency ? 'active' : ''}
                aria-pressed={option.value === frequency}
                onClick={() => onFrequencyChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="chart-interval-readout">
            <span>Interval:</span>
            <strong>{frequencyOption.intervalLabel}</strong>
          </div>
        </div>
      )}
    </div>
  );
}

function TradeLevel({
  label,
  value,
  top,
  width,
  valueAnchorLeft,
  danger = false,
  onPointerDown
}: {
  label: string;
  value: string;
  top: string;
  width?: number;
  valueAnchorLeft?: number;
  danger?: boolean;
  onPointerDown?: (event: ReactPointerEvent<HTMLDivElement>) => void;
}) {
  return (
    <div
      className={`${danger ? 'trade-level danger draggable' : 'trade-level draggable'}${valueAnchorLeft === undefined ? '' : ' pinned-value'}`}
      style={{
        top,
        right: width === undefined ? undefined : 'auto',
        width
      }}
      onPointerDown={onPointerDown}
    >
      <span>{label}</span>
      <strong
        style={
          valueAnchorLeft === undefined
            ? undefined
            : {
                position: 'absolute',
                left: valueAnchorLeft - 28,
                transform: 'translateX(-100%)'
              }
        }
      >
        {value}
      </strong>
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
            <th>Analysis summary</th>
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
              <td>
                {report.ticker
                  ? `${report.ticker} · ${report.validation_label ?? 'not validated'} · ${report.quality_label ?? 'unknown'} quality · ${report.valuation_label ?? 'unknown'} by DCF · ${report.risk_label ?? 'unknown'} risk`
                  : '—'}
              </td>
              <td>{formatFileSize(report.size_bytes)}</td>
              <td>{report.path}</td>
              <td>
                {(report.type === 'fundamental_analysis' || report.type === 'saved_watchlist') && (
                  <FileActionButton reportId={report.id} preview>
                    View
                  </FileActionButton>
                )}{' '}
                <FileActionButton reportId={report.id}>
                  Download
                </FileActionButton>
              </td>
            </tr>
          ))}
          {reports.length === 0 && (
            <tr>
              <td colSpan={7} className="empty-cell">No generated reports found.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SettingsPage() {
  const cacheOverview = useCacheOverview();
  const massiveCredential = useMassiveCredentialStatus();
  const saveMassiveCredential = useSaveMassiveCredential();
  const deleteMassiveCredential = useDeleteMassiveCredential();
  const strategies = useStrategies();
  const [displaySettings, setDisplaySettings] = useScannerDisplaySettings();
  const [recommendationSettings, setRecommendationSettings] = useSavedSetting<RecommendationSettings>(
    'swing-scanner.recommendation-settings',
    defaultRecommendationSettings
  );
  const [cacheSettings, setCacheSettings] = useSavedSetting<CacheSettings>(
    'swing-scanner.cache-settings',
    defaultCacheSettings
  );
  const [marketDataSettings, setMarketDataSettings] = useSavedSetting<MarketDataSettings>(
    'swing-scanner.market-data-settings.v2',
    defaultMarketDataSettings
  );
  const [appearanceSettings, setAppearanceSettings] = useSavedSetting<AppearanceSettings>(
    'swing-scanner.appearance-settings',
    defaultAppearanceSettings
  );
  const [massiveApiKey, setMassiveApiKey] = useState('');
  const cache = cacheOverview.data;
  const credential = massiveCredential.data;

  async function saveMassiveApiKey() {
    const apiKey = massiveApiKey.trim();

    if (!apiKey) {
      return;
    }

    await saveMassiveCredential.mutateAsync({ api_key: apiKey });
    setMarketDataSettings({
      ...marketDataSettings,
      primaryProvider: 'massive',
      backupProvider: marketDataSettings.backupProvider === 'massive' ? 'yahoo' : marketDataSettings.backupProvider
    });
    setMassiveApiKey('');
  }

  async function removeMassiveApiKey() {
    await deleteMassiveCredential.mutateAsync();
    setMassiveApiKey('');
  }

  return (
    <div className="settings-grid">
      <RuntimeReadiness />
      <SECContactSetup />
      <section className="panel" aria-labelledby="browser-backup-title">
        <div className="panel-header"><div>
          <h2 id="browser-backup-title">Original Browser Recovery Data</h2>
          <p>Saved trades, trade levels, assumptions, and settings now use the database. The original browser export is retained for migration recovery, not for backing up new edits.</p>
        </div></div>
        <div className="settings-form"><a className="secondary-button" href="/migration">Review migration and original browser export</a></div>
      </section>
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
              <option value="massive">Massive/Polygon</option>
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
              <option value="massive">Massive/Polygon</option>
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
            Massive/Polygon API Key
            <input
              type="password"
              value={massiveApiKey}
              placeholder={credential?.configured ? 'Stored locally' : 'Paste API key'}
              onChange={(event) => setMassiveApiKey(event.target.value)}
            />
          </label>
          <div className="settings-actions">
            <button
              type="button"
              className="primary-button"
              disabled={!massiveApiKey.trim() || saveMassiveCredential.isPending}
              onClick={() => void saveMassiveApiKey()}
            >
              <Save size={16} />
              Save Key
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={!credential?.configured || deleteMassiveCredential.isPending}
              onClick={() => void removeMassiveApiKey()}
            >
              <Trash2 size={16} />
              Remove
            </button>
          </div>
          <div className="settings-status">
            <span>
              {credential?.configured
                ? `Massive key configured (${credential.source?.replaceAll('_', ' ') ?? 'stored'})`
                : 'Massive key not configured'}
            </span>
            {credential?.updated_at && <span>Updated {formatDateTime(credential.updated_at)}</span>}
          </div>
          {saveMassiveCredential.isError && (
            <AlertMessage tone="danger" message={saveMassiveCredential.error.message} />
          )}
          {deleteMassiveCredential.isError && (
            <AlertMessage tone="danger" message={deleteMassiveCredential.error.message} />
          )}
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
  const outputPaths = Object.entries(progress?.output_paths ?? {});
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

      {outputPaths.length > 0 && (
        <div className="output-path-list">
          {outputPaths.map(([label]) => job && (
            <FileActionButton key={label} className="output-path-link" jobId={job.job_id} outputName={label}>
              <Download size={15} />
              {label.replaceAll('_', ' ')}
            </FileActionButton>
          ))}
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

type ChartLevelKey = 'entry' | 'stop' | 'target';

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
  maximized?: boolean;
  savedWatchlistId?: number | null;
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
  primaryProvider: 'massive',
  backupProvider: 'yahoo',
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

function useLocalStorage<T>(
  key: string,
  initialValue: T,
  normalize?: (value: unknown) => T
) {
  const [value, setValue] = useState<T>(() => {
    const stored = window.localStorage.getItem(key);

    if (!stored) {
      return initialValue;
    }

    try {
      const parsed = JSON.parse(stored) as unknown;
      return normalize ? normalize(parsed) : (parsed as T);
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

function priceFilterNumberOrNull(value: string): number | null {
  const parsed = inputNumberOrNull(value);
  return parsed !== null && parsed >= 0 ? parsed : null;
}

function normalizeOptionalTicker(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }

  const ticker = value.trim().toUpperCase();
  return ticker || null;
}

function normalizePositiveIntegerOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
    ? value
    : null;
}

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? [...new Set(value.filter((item): item is string => typeof item === 'string'))]
    : [];
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

function sharedCandidateValue(values: string[]): string {
  const meaningfulValues = new Set(
    values.map((value) => value.trim()).filter((value) => value && value !== 'n/a')
  );

  if (meaningfulValues.size === 0) {
    return 'n/a';
  }

  if (meaningfulValues.size > 1) {
    return 'Mixed';
  }

  return meaningfulValues.values().next().value ?? 'n/a';
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
  return (
    typeof candidate.ticker === 'string' &&
    candidate.ticker.trim() !== '' &&
    (candidate.maximized === undefined || typeof candidate.maximized === 'boolean') &&
    (candidate.savedWatchlistId === undefined ||
      candidate.savedWatchlistId === null ||
      (typeof candidate.savedWatchlistId === 'number' &&
        Number.isInteger(candidate.savedWatchlistId)))
  );
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

function downloadCandidatesCsv(candidates: DisplayCandidate[], files: FileActions) {
  const header = [
    'Ticker',
    'Strategy',
    'Score',
    'Current Price',
    'Price As Of',
    'Price Source',
    'Validation',
    'Validation Score',
    'Business Quality',
    'Quality Score',
    'DCF Valuation',
    'Risk',
    'Risk Score',
    'Fair Value',
    'DCF Upside',
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
    candidate.validationLabel,
    candidate.validationScore,
    candidate.qualityLabel,
    candidate.qualityScore,
    candidate.dcfLabel,
    candidate.riskLabel,
    candidate.riskScore,
    candidate.fairValue,
    candidate.marginOfSafety,
    candidate.relativeStrength,
    candidate.relativeVolume,
    candidate.atr,
    candidate.entryArea,
    candidate.stop,
    candidate.targetExit
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  return files.save(blob, 'scanner_candidates.csv');
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
