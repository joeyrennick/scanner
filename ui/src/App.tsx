import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  Database,
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
import { useStrategies } from './api/strategies';
import type { CacheWarmupRequest, JobResponse } from './api/types';
import { formatDuration, formatNumber, isJobActive, progressPercent } from './lib/progress';
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
        <Route path="daily-scanner" element={<PlaceholderPage title="Daily Scanner" />} />
        <Route path="candidates" element={<PlaceholderPage title="Candidates" />} />
        <Route path="backtest" element={<PlaceholderPage title="Backtest" />} />
        <Route path="portfolio" element={<PlaceholderPage title="Portfolio" />} />
        <Route path="journal" element={<PlaceholderPage title="Journal" />} />
        <Route path="reports" element={<PlaceholderPage title="Reports" />} />
        <Route path="cache-warmup" element={<CacheWarmupPage />} />
        <Route path="settings" element={<PlaceholderPage title="Settings" />} />
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
