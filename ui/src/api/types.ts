export type JobStatus = 'queued' | 'running' | 'complete' | 'failed' | 'stopped';

export interface CacheOverview {
  provider: string | null;
  cached_tickers: number;
  cached_bars: number;
  earliest_bar_date: string | null;
  latest_bar_date: string | null;
  last_successful_refresh: string | null;
  days_since_refresh: number | null;
}

export interface MarketDataCredentialStatus {
  provider: string;
  configured: boolean;
  source: string | null;
  updated_at: string | null;
}

export interface MarketDataCredentialRequest {
  api_key: string;
}

export interface MarketDataHistoryPoint {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
}

export interface MarketDataHistoryResponse {
  ticker: string;
  provider: string;
  period: string;
  rows: MarketDataHistoryPoint[];
}

export interface JobProgress {
  current_step: string | null;
  total_steps: number | null;
  symbols_total: number | null;
  symbols_checked: number | null;
  symbols_kept: number | null;
  symbols_skipped: number | null;
  provider_batches_attempted: number | null;
  provider_batch_limit: number | null;
  provider_symbols_attempted: number | null;
  provider_symbol_limit: number | null;
  elapsed_seconds: number | null;
  estimated_seconds_remaining: number | null;
  rate_limited: boolean;
  output_paths: Record<string, string>;
}

export interface JobResponse extends JobProgress {
  job_id: string;
  job_type: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  message: string;
  result: Record<string, unknown> | null;
  error: string | null;
  cancel_requested: boolean;
  progress: JobProgress;
}

export interface CacheWarmupRequest {
  universe: string;
  tickers?: string[];
  market_data_provider?: string;
  history_period: string;
  batch_size: number;
  max_provider_batches: number | null;
  batch_delay_ms: number;
  cache_only_preview: boolean;
  stop_on_rate_limit: boolean;
}

export interface ScanRequest {
  universe: string;
  strategy?: string;
  market_data_provider?: string;
  history_period: string;
  min_price?: number | null;
  max_price?: number | null;
  warm_market_data_cache: boolean;
  cache_warmup_batch_size: number;
  cache_warmup_max_provider_batches?: number | null;
  cache_warmup_batch_delay_ms: number;
}

export type WatchlistRow = Record<string, string | number | boolean | null>;

export interface WatchlistResponse {
  exists: boolean;
  path: string;
  run_id?: number | null;
  created_at?: string | null;
  rows: WatchlistRow[];
}

export interface WatchlistRiskClassificationRequest {
  run_id?: number | null;
  market_data_provider?: string;
}

export interface WatchlistPriceRefreshRequest {
  rows: WatchlistRow[];
  run_id?: number | null;
  market_data_provider?: string;
  period?: string;
  reward_risk_multiple?: number;
  suggested_hold_days?: number;
}

export interface WatchlistPriceRefreshResponse {
  rows: WatchlistRow[];
  refreshed_count: number;
  fallback_count: number;
}

export interface CandidateTradeLevelsRequest {
  run_id?: number | null;
  entry_area?: number | null;
  suggested_stop?: number | null;
  target_exit?: number | null;
  reset?: boolean;
}

export interface CandidateTradeLevelsResponse {
  run_id: number;
  ticker: string;
  row: WatchlistRow;
}

export interface BacktestRequest {
  ticker?: string | null;
  universe?: string | null;
  tickers?: string[] | null;
  strategy: string;
  history_period: string;
  hold_days: number;
  min_history_days: number;
  allow_overlapping_trades: boolean;
  entry_reset_policy: string;
}

export interface PortfolioSimulationRequest {
  trades_csv: string;
  initial_cash: number;
  max_open_positions: number;
  max_positions_per_ticker?: number | null;
  position_size_percent: number;
  commission_per_trade: number;
  commission_per_share: number;
  slippage_percent: number;
  stop_loss_percent?: number | null;
  trailing_stop_percent?: number | null;
}

export interface ReportMetadata {
  id: string;
  name: string;
  path: string;
  type: string;
  size_bytes: number;
  modified_at: string;
  ticker?: string | null;
  data_as_of?: string | null;
  quality_label?: string | null;
  valuation_label?: string | null;
  risk_label?: string | null;
  validation_label?: string | null;
}

export type AnalysisCheck = {
  name: string;
  status: string;
  value: number | string | null;
  unit: string;
};

export type ValidationCheck = {
  name: string;
  status: 'pass' | 'review' | 'fail';
  value: unknown;
  explanation: string;
};

export interface FundamentalAnalysis {
  schema_version: number;
  ticker: string;
  generated_at: string;
  source: string;
  company: {
    name: string;
    description: string;
    market_cap: number | null;
    sector: string;
    homepage_url: string;
    employees: number | null;
  };
  current_price: number | null;
  data_as_of: string | null;
  financial_history: Array<Record<string, string | number | null>>;
  ratios: Record<string, number>;
  quality: { score: number; label: string; checks: AnalysisCheck[]; metrics: Record<string, number | null> };
  valuation: {
    label: string;
    confidence: string;
    current_price: number | null;
    margin_of_safety: number | null;
    assumptions: Record<string, number>;
    scenarios: Array<{ name: string; growth_rate: number; fair_value: number | null; upside: number | null }>;
    multiples: Record<string, number>;
  };
  risk: { score: number; label: string; complete: boolean; checks: AnalysisCheck[]; metrics: Record<string, number | null> };
  validation: {
    policy_version: number;
    status: 'validated' | 'needs_review' | 'rejected';
    label: string;
    score: number;
    checks: ValidationCheck[];
    reasons: string[];
    model: string;
    manual_filing_review_required: boolean;
    manual_review_items: string[];
  };
  warnings: string[];
  confidence: string;
}

export interface FundamentalReportResponse {
  report: ReportMetadata;
  snapshot_path: string;
}

export interface DailyScannerReportRequest {
  rows?: WatchlistRow[] | null;
  report_date?: string | null;
  archive_watchlist?: boolean;
  account_size?: number | null;
  risk_per_trade_percent?: number | null;
  suggested_hold_days?: number;
  reward_risk_multiple?: number;
}

export interface DailyScannerReportResponse {
  report: ReportMetadata;
  archived_watchlist: string | null;
}

export interface StrategyMetadata {
  key: string;
  display_name: string;
  category: string;
  evaluation_mode: string;
  backtestable: boolean;
  default_config: Record<string, unknown>;
  fields: Array<{
    name: string;
    type: string;
    default: unknown;
    allowed_values: unknown[] | null;
  }>;
}
