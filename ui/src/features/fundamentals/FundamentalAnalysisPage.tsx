import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAnalyzeFundamentals, useGenerateFundamentalReport } from '../../api/fundamentals';
import { useLatestWatchlist, useWatchlistRun } from '../../api/scans';
import type { AnalysisCheck, FundamentalAnalysis, WatchlistRow } from '../../api/types';

type Tab = 'summary' | 'quality' | 'valuation' | 'risk' | 'financials';
type SavedState = {
  version: 1;
  ticker: string;
  tickerDraft: string;
  runId: number | null;
  strategy: string;
  tab: Tab;
  scrollY: number;
  assumptionsByTicker: Record<string, Record<string, number>>;
};

const storageKey = 'swing-scanner.fundamentals.v1';
const defaultState: SavedState = {
  version: 1,
  ticker: '',
  tickerDraft: '',
  runId: null,
  strategy: 'all',
  tab: 'summary',
  scrollY: 0,
  assumptionsByTicker: {}
};

export function FundamentalAnalysisPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [state, setStateBase] = useState<SavedState>(() => loadFundamentalState(searchParams));
  const analyze = useAnalyzeFundamentals();
  const report = useGenerateFundamentalReport();
  const watchlist = useLatestWatchlist();
  const selectedRun = useWatchlistRun(state.runId);
  const candidateSource = selectedRun.data ?? watchlist.data;
  const restoredScroll = useRef(false);

  const saveState = useCallback((next: SavedState) => {
    localStorage.setItem(storageKey, JSON.stringify(next));
    return next;
  }, []);
  const updateState = useCallback(
    (update: (current: SavedState) => SavedState) => {
      setStateBase((current) => saveState(update(current)));
    },
    [saveState]
  );

  const candidates = useMemo(
    () => candidateRows(candidateSource?.rows ?? [], state.strategy),
    [candidateSource?.rows, state.strategy]
  );
  const candidateIndex = candidates.findIndex((row) => tickerForRow(row) === state.ticker);
  const assumptions = state.assumptionsByTicker[state.ticker] ?? {};
  const analysis = analyze.data?.ticker === state.ticker ? analyze.data : null;

  useEffect(() => {
    const next = new URLSearchParams();
    if (state.ticker) next.set('ticker', state.ticker);
    if (state.runId !== null) next.set('run_id', String(state.runId));
    if (state.strategy !== 'all') next.set('strategy', state.strategy);
    if (state.tab !== 'summary') next.set('tab', state.tab);
    if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, state.runId, state.strategy, state.tab, state.ticker]);

  useEffect(() => {
    if (!state.ticker) return;
    analyze.mutate({ ticker: state.ticker, assumptions });
    // Re-run only when the selected ticker changes; assumptions apply through Recalculate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.ticker]);

  useEffect(() => {
    if (!watchlist.data) return;
    const runId = watchlist.data.run_id ?? null;
    if (state.runId === null && runId !== null) {
      updateState((current) => ({ ...current, runId }));
    }
  }, [state.runId, updateState, watchlist.data]);

  useEffect(() => {
    if (!selectedRun.isError) return;
    updateState((current) => ({
      ...current,
      runId: watchlist.data?.run_id ?? null
    }));
  }, [selectedRun.isError, updateState, watchlist.data?.run_id]);

  useEffect(() => {
    if (!analysis || Object.keys(assumptions).length > 0) return;
    updateState((current) => ({
      ...current,
      assumptionsByTicker: {
        ...current.assumptionsByTicker,
        [state.ticker]: analysis.valuation.assumptions
      }
    }));
  }, [analysis, assumptions, state.ticker, updateState]);

  useEffect(() => {
    if (restoredScroll.current) return;
    restoredScroll.current = true;
    requestAnimationFrame(() => window.scrollTo(0, state.scrollY));
  }, [state.scrollY]);

  useEffect(() => {
    const persistPosition = () => {
      setStateBase((current) => saveState({ ...current, scrollY: window.scrollY }));
    };
    window.addEventListener('pagehide', persistPosition);
    document.addEventListener('visibilitychange', persistPosition);
    return () => {
      persistPosition();
      window.removeEventListener('pagehide', persistPosition);
      document.removeEventListener('visibilitychange', persistPosition);
    };
  }, [saveState]);

  function selectTicker(ticker: string) {
    const normalized = ticker.trim().toUpperCase();
    if (!normalized) return;
    updateState((current) => ({ ...current, ticker: normalized, tickerDraft: normalized, scrollY: 0 }));
  }

  function moveCandidate(offset: number) {
    if (candidates.length === 0) return;
    const start = candidateIndex >= 0 ? candidateIndex : 0;
    const index = (start + offset + candidates.length) % candidates.length;
    selectTicker(tickerForRow(candidates[index]));
  }

  function updateAssumption(name: string, value: number) {
    updateState((current) => ({
      ...current,
      assumptionsByTicker: {
        ...current.assumptionsByTicker,
        [state.ticker]: {
          ...(current.assumptionsByTicker[state.ticker] ?? {}),
          [name]: value
        }
      }
    }));
  }

  return (
    <div className="page-stack fundamental-page">
      <section className="panel fundamental-toolbar" aria-label="Fundamental analysis controls">
        <form
          className="ticker-search"
          onSubmit={(event) => {
            event.preventDefault();
            selectTicker(state.tickerDraft);
          }}
        >
          <label>
            Ticker
            <input
              value={state.tickerDraft}
              onChange={(event) => updateState((current) => ({ ...current, tickerDraft: event.target.value.toUpperCase() }))}
              placeholder="AAPL"
            />
          </label>
          <button className="primary-button" type="submit">Analyze</button>
        </form>
        <label>
          Candidate strategy
          <select
            value={state.strategy}
            onChange={(event) => updateState((current) => ({ ...current, strategy: event.target.value }))}
          >
            <option value="all">All candidates</option>
            <option value="pullback">Pullback</option>
            <option value="breakout">Breakout</option>
            <option value="bounce">Bounce</option>
          </select>
        </label>
        <div className="candidate-navigator">
          <button type="button" onClick={() => moveCandidate(-1)} disabled={!candidates.length}>← Previous</button>
          <select value={candidateIndex >= 0 ? state.ticker : ''} onChange={(event) => selectTicker(event.target.value)}>
            <option value="">Select candidate</option>
            {candidates.map((row) => {
              const ticker = tickerForRow(row);
              return <option key={ticker} value={ticker}>{ticker}</option>;
            })}
          </select>
          <span>{candidateIndex >= 0 ? `${candidateIndex + 1} of ${candidates.length}` : `${candidates.length} candidates`}</span>
          <button type="button" onClick={() => moveCandidate(1)} disabled={!candidates.length}>Next →</button>
        </div>
      </section>

      {analyze.isPending && <section className="panel"><p>Loading fundamental data for {state.ticker}…</p></section>}
      {analyze.isError && <section className="panel alert danger">{analyze.error.message}</section>}
      {!state.ticker && <section className="panel empty-state"><h2>Select a company</h2><p>Choose a scanner candidate or enter a ticker to begin.</p></section>}

      {analysis && (
        <>
          <section className="panel company-summary">
            <div>
              <p className="eyebrow">{analysis.ticker} · {analysis.company.sector || 'Sector unavailable'}</p>
              <h2>{analysis.company.name || analysis.ticker}</h2>
              <p>{analysis.company.description || 'Company description unavailable.'}</p>
              <p className="muted-text">Data as of {analysis.data_as_of ?? 'n/a'} · Confidence {analysis.confidence}</p>
            </div>
            <div className="company-actions">
              <strong>{money(analysis.current_price)}</strong>
              <button
                className="primary-button"
                type="button"
                disabled={report.isPending}
                onClick={() => report.mutate({ ticker: analysis.ticker, analysis, pageState: state })}
              >
                {report.isPending ? 'Creating PDF…' : 'Create PDF Report'}
              </button>
              <Link className="link-button" to="/reports">Reports</Link>
            </div>
          </section>

          {report.data && (
            <section className="panel success-message">
              Report created. <a href={`/api/reports/${report.data.report.id}/download`}>Download PDF</a>
            </section>
          )}
          {report.isError && <section className="panel alert danger">{report.error.message}</section>}
          {analysis.warnings.length > 0 && <section className="panel alert warning">{analysis.warnings.join(' ')}</section>}

          <nav className="analysis-tabs" aria-label="Analysis sections">
            {(['summary', 'quality', 'valuation', 'risk', 'financials'] as Tab[]).map((tab) => (
              <button
                key={tab}
                className={state.tab === tab ? 'active' : ''}
                onClick={() => updateState((current) => ({ ...current, tab }))}
              >
                {tab[0].toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </nav>

          {state.tab === 'summary' && <Summary analysis={analysis} />}
          {state.tab === 'quality' && <ChecksPanel title="Business Quality" score={analysis.quality.score} label={analysis.quality.label} checks={analysis.quality.checks} />}
          {state.tab === 'risk' && <ChecksPanel title="Risk" score={analysis.risk.score} label={analysis.risk.label} checks={analysis.risk.checks} />}
          {state.tab === 'valuation' && (
            <ValuationPanel
              analysis={analysis}
              assumptions={assumptions}
              onChange={updateAssumption}
              onRecalculate={() => analyze.mutate({ ticker: state.ticker, assumptions })}
            />
          )}
          {state.tab === 'financials' && <FinancialHistory analysis={analysis} />}
        </>
      )}
    </div>
  );
}

function Summary({ analysis }: { analysis: FundamentalAnalysis }) {
  return (
    <div className="analysis-card-grid">
      <ScoreCard title="Business Quality" value={`${analysis.quality.score}/100`} label={analysis.quality.label} />
      <ScoreCard title="Valuation" value={percent(analysis.valuation.margin_of_safety)} label={analysis.valuation.label} />
      <ScoreCard title="Risk" value={`${analysis.risk.score}/100`} label={analysis.risk.label} />
    </div>
  );
}

function ScoreCard({ title, value, label }: { title: string; value: string; label: string }) {
  return <section className="panel score-card"><p>{title}</p><strong>{value}</strong><span>{label}</span></section>;
}

function ChecksPanel({ title, score, label, checks }: { title: string; score: number; label: string; checks: AnalysisCheck[] }) {
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>{title}</h2><p>{label} · {score}/100</p></div></div>
      <div className="check-list">
        {checks.map((check) => <div key={check.name} className={`analysis-check ${check.status}`}><strong>{check.name}</strong><span>{formatCheckValue(check)}</span><em>{check.status}</em></div>)}
      </div>
    </section>
  );
}

function ValuationPanel({ analysis, assumptions, onChange, onRecalculate }: { analysis: FundamentalAnalysis; assumptions: Record<string, number>; onChange: (name: string, value: number) => void; onRecalculate: () => void }) {
  const fields = [
    ['bear_growth_rate', 'Bear growth', true],
    ['base_growth_rate', 'Base growth', true],
    ['bull_growth_rate', 'Bull growth', true],
    ['discount_rate', 'Discount rate', true],
    ['terminal_growth_rate', 'Terminal growth', true],
    ['projection_years', 'Projection years', false]
  ] as const;
  return (
    <div className="valuation-layout">
      <section className="panel">
        <div className="panel-header"><div><h2>Valuation assumptions</h2><p>Saved automatically for {analysis.ticker}</p></div></div>
        <div className="assumption-grid">
          {fields.map(([name, label, isPercent]) => (
            <label key={name}>{label}<input type="number" step={isPercent ? '0.005' : '1'} value={isPercent ? ((assumptions[name] ?? analysis.valuation.assumptions[name]) * 100) : (assumptions[name] ?? analysis.valuation.assumptions[name])} onChange={(event) => onChange(name, Number(event.target.value) / (isPercent ? 100 : 1))} /></label>
          ))}
        </div>
        <button className="primary-button" onClick={onRecalculate}>Recalculate</button>
      </section>
      <section className="panel">
        <h2>Scenario values</h2>
        <div className="scenario-grid">
          {analysis.valuation.scenarios.map((scenario) => <div key={scenario.name}><span>{scenario.name}</span><strong>{money(scenario.fair_value)}</strong><em>{percent(scenario.upside)}</em></div>)}
        </div>
      </section>
    </div>
  );
}

function FinancialHistory({ analysis }: { analysis: FundamentalAnalysis }) {
  return (
    <section className="panel">
      <h2>Annual financial history</h2>
      <div className="table-wrap"><table className="data-table"><thead><tr><th>Year</th><th>Revenue</th><th>Operating income</th><th>Free cash flow</th><th>Debt</th><th>Operating margin</th></tr></thead><tbody>{analysis.financial_history.map((row) => <tr key={String(row.period_end)}><td>{row.fiscal_year ?? row.period_end}</td><td>{compactMoney(row.revenue)}</td><td>{compactMoney(row.operating_income)}</td><td>{compactMoney(row.free_cash_flow)}</td><td>{compactMoney(row.debt)}</td><td>{percent(numberValue(row.operating_margin))}</td></tr>)}</tbody></table></div>
    </section>
  );
}

export function loadFundamentalState(params: URLSearchParams): SavedState {
  let saved = defaultState;
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) ?? 'null');
    if (parsed?.version === 1) saved = { ...defaultState, ...parsed };
  } catch {
    localStorage.removeItem(storageKey);
  }
  const tab = params.get('tab');
  return {
    ...saved,
    ticker: (params.get('ticker') ?? saved.ticker).toUpperCase(),
    tickerDraft: (params.get('ticker') ?? saved.tickerDraft ?? saved.ticker).toUpperCase(),
    runId: numberOrNull(params.get('run_id')) ?? saved.runId,
    strategy: params.get('strategy') ?? saved.strategy,
    tab: isTab(tab) ? tab : saved.tab
  };
}

export function candidateRows(rows: WatchlistRow[], strategy: string) {
  if (strategy === 'all') return rows.filter((row) => tickerForRow(row));
  return rows.filter((row) => String(row['Triggered Strategies'] ?? '').toLowerCase().includes(strategy));
}
function tickerForRow(row: WatchlistRow) { return String(row.Ticker ?? row.Symbol ?? '').toUpperCase(); }
function isTab(value: string | null): value is Tab { return ['summary', 'quality', 'valuation', 'risk', 'financials'].includes(value ?? ''); }
function numberOrNull(value: string | null) { const parsed = Number(value); return value && Number.isFinite(parsed) ? parsed : null; }
function numberValue(value: unknown) { return typeof value === 'number' ? value : null; }
function money(value: number | null) { return value === null ? 'n/a' : `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`; }
function compactMoney(value: unknown) { return typeof value !== 'number' ? 'n/a' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(value); }
function percent(value: number | null) { return value === null ? 'n/a' : `${(value * 100).toFixed(1)}%`; }
function formatCheckValue(check: AnalysisCheck) { if (check.value === null) return 'n/a'; if (check.unit === 'percent' && typeof check.value === 'number') return percent(check.value); if (check.unit === 'multiple' && typeof check.value === 'number') return `${check.value.toFixed(2)}×`; return String(check.value); }
