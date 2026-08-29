import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  useAnalyzeFundamentals,
  useClassifyWatchlistRisk,
  useGenerateFundamentalReport
} from '../../api/fundamentals';
import { useJob } from '../../api/jobs';
import { useLatestWatchlist, useWatchlistRun } from '../../api/scans';
import type { AnalysisCheck, FundamentalAnalysis, ValidationCheck, WatchlistRow } from '../../api/types';
import { formatDuration, formatNumber, progressPercent } from '../../lib/progress';
import { useScannerDisplaySettings, type ScannerDisplaySettings } from '../../lib/scannerSettings';
import { rowMatchesDisplaySettings, rowMatchesStrategy } from '../../lib/watchlist';

type Tab = 'summary' | 'validation' | 'quality' | 'valuation' | 'risk' | 'financials';
type RiskFilter = 'all' | 'low' | 'moderate' | 'high' | 'unknown';
type ValidationFilter = 'all' | 'validated' | 'needs_review' | 'rejected' | 'not_calculated';
type SavedState = {
  version: 1;
  ticker: string;
  tickerDraft: string;
  runId: number | null;
  strategy: string;
  risk: RiskFilter;
  validation: ValidationFilter;
  classificationJobId: string | null;
  tab: Tab;
  scrollY: number;
  assumptionsByTicker: Record<string, Record<string, number>>;
};

const storageKey = 'swing-scanner.fundamentals.v1';
const candidateStrategies = ['pullback', 'breakout', 'bounce', 'undervalued'] as const;
const defaultState: SavedState = {
  version: 1,
  ticker: '',
  tickerDraft: '',
  runId: null,
  strategy: 'all',
  risk: 'all',
  validation: 'all',
  classificationJobId: null,
  tab: 'summary',
  scrollY: 0,
  assumptionsByTicker: {}
};

export function FundamentalAnalysisPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [state, setStateBase] = useState<SavedState>(() => loadFundamentalState(searchParams));
  const analyze = useAnalyzeFundamentals();
  const classifyRisk = useClassifyWatchlistRisk();
  const report = useGenerateFundamentalReport();
  const [displaySettings] = useScannerDisplaySettings();
  const watchlist = useLatestWatchlist();
  const selectedRun = useWatchlistRun(state.runId);
  const candidateSource = state.runId !== null ? selectedRun.data : watchlist.data;
  const restoredScroll = useRef(false);
  const reconciledCandidateSource = useRef<string | null>(null);
  const refreshedRiskJob = useRef<string | null>(null);
  const riskJobQuery = useJob(state.classificationJobId);
  const riskJob = riskJobQuery.data;

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
    () => candidateRows(candidateSource?.rows ?? [], state.strategy, displaySettings, state.risk, state.validation),
    [candidateSource?.rows, displaySettings, state.risk, state.strategy, state.validation]
  );
  const reconciledStrategy = useMemo(
    () => candidateStrategyForRows(candidateSource?.rows ?? [], state.strategy, displaySettings, state.risk, state.validation),
    [candidateSource?.rows, displaySettings, state.risk, state.strategy, state.validation]
  );
  const candidateSourceKey = candidateSource
    ? `${candidateSource.run_id ?? candidateSource.path}:${candidateSource.created_at ?? ''}`
    : null;
  const candidateIndex = candidates.findIndex((row) => tickerForRow(row) === state.ticker);
  const riskCounts = useMemo(
    () => candidateRiskCounts(candidateSource?.rows ?? [], state.strategy, displaySettings),
    [candidateSource?.rows, displaySettings, state.strategy]
  );
  const validationCounts = useMemo(
    () => candidateValidationCounts(candidateSource?.rows ?? [], state.strategy, displaySettings, state.risk),
    [candidateSource?.rows, displaySettings, state.risk, state.strategy]
  );
  const assumptions = state.assumptionsByTicker[state.ticker] ?? {};
  const analysis = analyze.data?.ticker === state.ticker ? analyze.data : null;

  useEffect(() => {
    const next = new URLSearchParams();
    if (state.ticker) next.set('ticker', state.ticker);
    if (state.runId !== null) next.set('run_id', String(state.runId));
    if (state.strategy !== 'all') next.set('strategy', state.strategy);
    if (state.risk !== 'all') next.set('risk', state.risk);
    if (state.validation !== 'all') next.set('validation', state.validation);
    if (state.tab !== 'summary') next.set('tab', state.tab);
    if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, state.risk, state.runId, state.strategy, state.tab, state.ticker, state.validation]);

  useEffect(() => {
    if (!state.ticker) return;
    analyze.mutate({
      ticker: state.ticker,
      assumptions,
      runId: candidateSource?.run_id ?? state.runId
    });
    // Re-run only when the selected ticker changes; assumptions apply through Recalculate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.ticker]);

  useEffect(() => {
    if (!selectedRun.isError) return;
    updateState((current) => ({
      ...current,
      runId: null
    }));
  }, [selectedRun.isError, updateState]);

  useEffect(() => {
    if (
      !riskJob?.job_id ||
      riskJob.status !== 'complete' ||
      refreshedRiskJob.current === riskJob.job_id
    ) {
      return;
    }
    refreshedRiskJob.current = riskJob.job_id;
    void watchlist.refetch();
    if (state.runId !== null) void selectedRun.refetch();
  }, [riskJob?.job_id, riskJob?.status, selectedRun.refetch, state.runId, watchlist.refetch]);

  useEffect(() => {
    if (
      candidateSourceKey === null ||
      reconciledCandidateSource.current === candidateSourceKey
    ) {
      return;
    }
    reconciledCandidateSource.current = candidateSourceKey;
    if (reconciledStrategy === state.strategy) return;
    const matching = candidateRows(
      candidateSource?.rows ?? [],
      reconciledStrategy,
      displaySettings,
      state.risk,
      state.validation
    );
    const nextTicker = candidateTickerForStrategy(matching, state.ticker);
    updateState((current) => ({
      ...current,
      strategy: reconciledStrategy,
      ticker: nextTicker ?? current.ticker,
      tickerDraft: nextTicker ?? current.tickerDraft,
      scrollY: 0
    }));
  }, [
    candidateSourceKey,
    candidateSource?.rows,
    displaySettings,
    reconciledStrategy,
    state.risk,
    state.strategy,
    state.ticker,
    state.validation,
    updateState
  ]);

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

  function changeCandidateStrategy(strategy: string) {
    const selection = candidateSelectionForStrategy(
      candidateSource?.rows ?? [],
      watchlist.data?.rows ?? [],
      strategy,
      state.runId,
      displaySettings,
      state.risk,
      state.validation
    );
    const nextTicker = candidateTickerForStrategy(selection.matchingRows, state.ticker);
    updateState((current) => ({
      ...current,
      runId: selection.runId,
      strategy,
      ticker: nextTicker ?? '',
      tickerDraft: nextTicker ?? current.tickerDraft,
      scrollY: 0
    }));
  }

  function changeRiskFilter(risk: RiskFilter) {
    const matching = candidateRows(
      candidateSource?.rows ?? [],
      state.strategy,
      displaySettings,
      risk,
      state.validation
    );
    const nextTicker = candidateTickerForStrategy(matching, state.ticker);
    updateState((current) => ({
      ...current,
      risk,
      ticker: nextTicker ?? '',
      tickerDraft: nextTicker ?? current.tickerDraft,
      scrollY: 0
    }));
  }

  function changeValidationFilter(validation: ValidationFilter) {
    const matching = candidateRows(
      candidateSource?.rows ?? [],
      state.strategy,
      displaySettings,
      state.risk,
      validation
    );
    const nextTicker = candidateTickerForStrategy(matching, state.ticker);
    updateState((current) => ({
      ...current,
      validation,
      ticker: nextTicker ?? '',
      tickerDraft: nextTicker ?? current.tickerDraft,
      scrollY: 0
    }));
  }

  async function classifyCandidateRisk() {
    const response = await classifyRisk.mutateAsync({
      run_id: candidateSource?.run_id ?? state.runId
    });
    updateState((current) => ({
      ...current,
      classificationJobId: response.job_id
    }));
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
            onChange={(event) => changeCandidateStrategy(event.target.value)}
          >
            <option value="all">All candidates</option>
            <option value="pullback">Pullback</option>
            <option value="breakout">Breakout</option>
            <option value="bounce">Bounce</option>
            <option value="undervalued">DCF candidates</option>
          </select>
        </label>
        <label>
          Risk
          <select
            value={state.risk}
            onChange={(event) => changeRiskFilter(event.target.value as RiskFilter)}
          >
            <option value="all">All risk levels</option>
            <option value="low">Low ({riskCounts.low})</option>
            <option value="moderate">Moderate ({riskCounts.moderate})</option>
            <option value="high">High ({riskCounts.high})</option>
            <option value="unknown">Risk not calculated ({riskCounts.unknown})</option>
          </select>
        </label>
        <label>
          Validation
          <select
            value={state.validation}
            onChange={(event) => changeValidationFilter(event.target.value as ValidationFilter)}
          >
            <option value="all">All validation statuses</option>
            <option value="validated">Validated ({validationCounts.validated})</option>
            <option value="needs_review">Needs review ({validationCounts.needs_review})</option>
            <option value="rejected">Rejected ({validationCounts.rejected})</option>
            <option value="not_calculated">Not calculated ({validationCounts.not_calculated})</option>
          </select>
        </label>
        <div className="candidate-navigator">
          <button type="button" onClick={() => moveCandidate(-1)} disabled={!candidates.length}>← Previous</button>
          <select value={candidateIndex >= 0 ? state.ticker : ''} onChange={(event) => selectTicker(event.target.value)}>
            <option value="">Select candidate</option>
            {candidates.map((row) => {
              const ticker = tickerForRow(row);
              const validation = validationLabelForRow(row);
              return <option key={ticker} value={ticker}>{ticker} · {validation}</option>;
            })}
          </select>
          <span>{candidateIndex >= 0 ? `${candidateIndex + 1} of ${candidates.length}` : `${candidates.length} candidates`}</span>
          <button type="button" onClick={() => moveCandidate(1)} disabled={!candidates.length}>Next →</button>
        </div>
      </section>

      {(riskCounts.unknown > 0 || validationCounts.not_calculated > 0) && (
        <section className="panel alert warning">
          <span>
            {riskCounts.unknown} candidates need five-year risk analysis and{' '}
            {validationCounts.not_calculated} need automated validation. A DCF candidate
            is not validated until these checks finish.
          </span>
          <button
            className="secondary-button"
            type="button"
            disabled={classifyRisk.isPending || riskJob?.status === 'queued' || riskJob?.status === 'running'}
            onClick={() => void classifyCandidateRisk()}
          >
            {riskJob?.status === 'queued' || riskJob?.status === 'running'
              ? `Classifying ${riskJob.progress.symbols_checked ?? 0}/${riskJob.progress.symbols_total ?? riskCounts.unknown}…`
              : 'Calculate Risk & Validation'}
          </button>
        </section>
      )}
      {classifyRisk.isError && <section className="panel alert danger">{classifyRisk.error.message}</section>}
      {riskJobQuery.isError && <section className="panel alert danger">Unable to load classification progress: {riskJobQuery.error.message}</section>}
      {riskJob && <FundamentalClassificationProgress job={riskJob} />}
      {riskJob?.status === 'failed' && <section className="panel alert danger">{riskJob.error ?? 'Risk classification failed.'}</section>}

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
              <p className="muted-text">
                Data as of {analysis.data_as_of ?? 'n/a'} · Confidence {analysis.confidence} · {analysis.source}
              </p>
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
            {(['summary', 'validation', 'quality', 'valuation', 'risk', 'financials'] as Tab[]).map((tab) => (
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
          {state.tab === 'validation' && <ValidationPanel analysis={analysis} />}
          {state.tab === 'quality' && <ChecksPanel title="Business Quality" score={analysis.quality.score} label={analysis.quality.label} checks={analysis.quality.checks} />}
          {state.tab === 'risk' && <ChecksPanel title="Risk" score={analysis.risk.score} label={analysis.risk.label} checks={analysis.risk.checks} />}
          {state.tab === 'valuation' && (
            <ValuationPanel
              analysis={analysis}
              assumptions={assumptions}
              onChange={updateAssumption}
              onRecalculate={() => analyze.mutate({
                ticker: state.ticker,
                assumptions,
                runId: candidateSource?.run_id ?? state.runId
              })}
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
      <ScoreCard title="Automated Validation" value={`${analysis.validation.score}/100`} label={analysis.validation.label} />
      <ScoreCard title="Business Quality" value={`${analysis.quality.score}/100`} label={analysis.quality.label} />
      <ScoreCard title="DCF Estimate" value={percent(analysis.valuation.margin_of_safety)} label={dcfLabel(analysis.valuation.label)} />
      <ScoreCard title="Risk" value={`${analysis.risk.score}/100`} label={analysis.risk.label} />
    </div>
  );
}

function FundamentalClassificationProgress({ job }: { job: NonNullable<ReturnType<typeof useJob>['data']> }) {
  const progress = job.progress;
  const percent = progressPercent(progress);
  const statusLabel = job.status.replaceAll('_', ' ');
  return (
    <section className="panel progress-panel fundamental-progress" aria-labelledby="fundamental-progress-title">
      <div className="panel-header">
        <div>
          <h2 id="fundamental-progress-title">Fundamental Validation Progress</h2>
          <p>{job.message || 'Preparing candidate classification'}</p>
        </div>
        <span className={`status-pill ${job.status}`}>{statusLabel}</span>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Fundamental validation progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="progress-summary">
        <strong>{progress.current_step ?? 'Starting classification'}</strong>
        <span>{percent}%</span>
      </div>
      <div className="fundamental-progress-details">
        <span><strong>{formatNumber(progress.symbols_checked)}</strong> checked</span>
        <span><strong>{formatNumber(progress.symbols_total)}</strong> total</span>
        <span><strong>{formatNumber(progress.symbols_kept)}</strong> completed</span>
        <span><strong>{formatNumber(progress.symbols_skipped)}</strong> skipped</span>
        <span><strong>{formatDuration(progress.elapsed_seconds)}</strong> elapsed</span>
      </div>
    </section>
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

function ValidationPanel({ analysis }: { analysis: FundamentalAnalysis }) {
  const validation = analysis.validation;
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Automated Validation</h2>
          <p>{validation.label} · {validation.score}/100 · {validation.model === 'dcf' ? 'Standard DCF model' : 'Sector-specific model needed'}</p>
        </div>
      </div>
      <p className="muted-text">
        This validates the data, model fit, quality, risk-adjusted margin of safety, independent value support,
        and bear case. It does not replace reading the company&apos;s filings.
      </p>
      <div className="check-list">
        {validation.checks.map((check) => (
          <div key={check.name} className={`analysis-check validation-check ${check.status}`}>
            <div><strong>{check.name}</strong><small>{check.explanation}</small></div>
            <span>{formatValidationValue(check)}</span>
            <em>{check.status}</em>
          </div>
        ))}
      </div>
      {validation.manual_filing_review_required && (
        <div className="manual-review">
          <h3>Required filing review</h3>
          <ul>{validation.manual_review_items.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
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
  const risk = params.get('risk');
  const validation = params.get('validation');
  return {
    ...saved,
    ticker: (params.get('ticker') ?? saved.ticker).toUpperCase(),
    tickerDraft: (params.get('ticker') ?? saved.tickerDraft ?? saved.ticker).toUpperCase(),
    runId: params.has('run_id') ? numberOrNull(params.get('run_id')) : null,
    strategy: params.get('strategy') ?? saved.strategy,
    risk: isRiskFilter(risk) ? risk : saved.risk,
    validation: isValidationFilter(validation) ? validation : saved.validation,
    tab: isTab(tab) ? tab : saved.tab
  };
}

export function candidateRows(
  rows: WatchlistRow[],
  strategy: string,
  displaySettings: ScannerDisplaySettings,
  risk: RiskFilter = 'all',
  validation: ValidationFilter = 'all'
) {
  return rows.filter(
    (row) =>
      tickerForRow(row) &&
      rowMatchesStrategy(row, strategy) &&
      rowMatchesDisplaySettings(row, displaySettings) &&
      rowMatchesRisk(row, risk) &&
      rowMatchesValidation(row, validation)
  );
}

export function candidateTickerForStrategy(
  matchingRows: WatchlistRow[],
  currentTicker: string
): string | null {
  const normalizedCurrent = currentTicker.toUpperCase();
  if (matchingRows.some((row) => tickerForRow(row) === normalizedCurrent)) {
    return normalizedCurrent;
  }
  return matchingRows.length > 0 ? tickerForRow(matchingRows[0]) : null;
}

export function candidateStrategyForRows(
  rows: WatchlistRow[],
  requestedStrategy: string,
  displaySettings: ScannerDisplaySettings,
  risk: RiskFilter = 'all',
  validation: ValidationFilter = 'all'
): string {
  if (
    rows.length === 0 ||
    candidateRows(rows, requestedStrategy, displaySettings, risk, validation).length > 0
  ) {
    return requestedStrategy;
  }

  const visibleRows = candidateRows(rows, 'all', displaySettings, risk, validation);
  if (visibleRows.length === 0) {
    return requestedStrategy;
  }

  const availableStrategies = candidateStrategies.filter((strategy) =>
    visibleRows.some((row) => rowMatchesStrategy(row, strategy))
  );
  return availableStrategies.length === 1 ? availableStrategies[0] : 'all';
}

export function candidateSelectionForStrategy(
  currentRows: WatchlistRow[],
  latestRows: WatchlistRow[],
  strategy: string,
  currentRunId: number | null,
  displaySettings: ScannerDisplaySettings,
  risk: RiskFilter = 'all',
  validation: ValidationFilter = 'all'
): { matchingRows: WatchlistRow[]; runId: number | null } {
  const matchingRows = candidateRows(currentRows, strategy, displaySettings, risk, validation);
  if (strategy === 'all' || matchingRows.length > 0 || currentRunId === null) {
    return { matchingRows, runId: currentRunId };
  }

  const latestMatches = candidateRows(latestRows, strategy, displaySettings, risk, validation);
  return latestMatches.length > 0
    ? { matchingRows: latestMatches, runId: null }
    : { matchingRows, runId: currentRunId };
}

export function rowMatchesRisk(row: WatchlistRow, risk: RiskFilter): boolean {
  if (risk === 'all') return true;
  const level = String(row['Risk Level'] ?? '').trim().toLowerCase();
  if (risk === 'unknown') {
    return !['low', 'moderate', 'high'].includes(level);
  }
  return level === risk;
}

export function rowMatchesValidation(row: WatchlistRow, validation: ValidationFilter): boolean {
  if (validation === 'all') return true;
  const status = String(row['Validation Status'] ?? '').trim().toLowerCase();
  if (validation === 'not_calculated') {
    return !['validated', 'needs_review', 'rejected'].includes(status);
  }
  return status === validation;
}

export function candidateRiskCounts(
  rows: WatchlistRow[],
  strategy: string,
  displaySettings: ScannerDisplaySettings
): Record<Exclude<RiskFilter, 'all'>, number> {
  const visibleRows = candidateRows(rows, strategy, displaySettings, 'all');
  return visibleRows.reduce<Record<Exclude<RiskFilter, 'all'>, number>>(
    (counts, row) => {
      const level = String(row['Risk Level'] ?? '').trim().toLowerCase();
      const key = ['low', 'moderate', 'high'].includes(level)
        ? (level as 'low' | 'moderate' | 'high')
        : 'unknown';
      counts[key] += 1;
      return counts;
    },
    { low: 0, moderate: 0, high: 0, unknown: 0 }
  );
}

export function candidateValidationCounts(
  rows: WatchlistRow[],
  strategy: string,
  displaySettings: ScannerDisplaySettings,
  risk: RiskFilter = 'all'
): Record<Exclude<ValidationFilter, 'all'>, number> {
  const visibleRows = candidateRows(rows, strategy, displaySettings, risk, 'all');
  return visibleRows.reduce<Record<Exclude<ValidationFilter, 'all'>, number>>(
    (counts, row) => {
      const status = String(row['Validation Status'] ?? '').trim().toLowerCase();
      const key = ['validated', 'needs_review', 'rejected'].includes(status)
        ? (status as 'validated' | 'needs_review' | 'rejected')
        : 'not_calculated';
      counts[key] += 1;
      return counts;
    },
    { validated: 0, needs_review: 0, rejected: 0, not_calculated: 0 }
  );
}

function tickerForRow(row: WatchlistRow) { return String(row.Ticker ?? row.Symbol ?? '').toUpperCase(); }
function validationLabelForRow(row: WatchlistRow) {
  const status = String(row['Validation Status'] ?? '').trim().toLowerCase();
  if (status === 'validated') return 'Validated';
  if (status === 'needs_review') return 'Needs review';
  if (status === 'rejected') return 'Rejected';
  return 'Not calculated';
}
function isTab(value: string | null): value is Tab { return ['summary', 'validation', 'quality', 'valuation', 'risk', 'financials'].includes(value ?? ''); }
function isRiskFilter(value: string | null): value is RiskFilter { return ['all', 'low', 'moderate', 'high', 'unknown'].includes(value ?? ''); }
function isValidationFilter(value: string | null): value is ValidationFilter { return ['all', 'validated', 'needs_review', 'rejected', 'not_calculated'].includes(value ?? ''); }
function numberOrNull(value: string | null) { const parsed = Number(value); return value && Number.isFinite(parsed) ? parsed : null; }
function numberValue(value: unknown) { return typeof value === 'number' ? value : null; }
function money(value: number | null) { return value === null ? 'n/a' : `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`; }
function compactMoney(value: unknown) { return typeof value !== 'number' ? 'n/a' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(value); }
function percent(value: number | null) { return value === null ? 'n/a' : `${(value * 100).toFixed(1)}%`; }
function formatCheckValue(check: AnalysisCheck) { if (check.value === null) return 'n/a'; if (check.unit === 'percent' && typeof check.value === 'number') return percent(check.value); if (check.unit === 'multiple' && typeof check.value === 'number') return `${check.value.toFixed(2)}×`; return String(check.value); }
function dcfLabel(label: string) { return `${label} by DCF only`; }
function formatValidationValue(check: ValidationCheck) {
  if (check.value === null || check.value === undefined) return 'n/a';
  if (check.name.includes('margin') || check.name === 'Bear-case resilience') {
    return typeof check.value === 'number' ? percent(check.value) : String(check.value);
  }
  if (check.name === 'Financial period recency' && typeof check.value === 'number') return `${check.value} days`;
  if (check.name === 'Business quality' && typeof check.value === 'number') return `${check.value}/100`;
  if (typeof check.value === 'object') {
    return Object.entries(check.value as Record<string, unknown>)
      .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${typeof value === 'number' ? percent(value) : value ?? 'n/a'}`)
      .join(' · ');
  }
  return String(check.value);
}
