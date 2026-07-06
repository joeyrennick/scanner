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

export interface StrategyMetadata {
  key: string;
  display_name: string;
  category: string;
  default_config: Record<string, unknown>;
  fields: Array<{
    name: string;
    type: string;
    default: unknown;
    allowed_values: unknown[] | null;
  }>;
}
