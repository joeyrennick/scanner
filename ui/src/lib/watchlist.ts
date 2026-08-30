import type { WatchlistRow } from '../api/types';
import type { ScannerDisplaySettings } from './scannerSettings';

export type ValidationResultFilter =
  | 'all'
  | 'validated'
  | 'needs_review'
  | 'rejected'
  | 'not_calculated';
export type QualityResultFilter =
  | 'all'
  | 'strong'
  | 'acceptable'
  | 'weak'
  | 'not_calculated';
export type DcfResultFilter =
  | 'all'
  | 'undervalued'
  | 'fairly_valued'
  | 'overvalued'
  | 'not_calculated';
export type RiskResultFilter =
  | 'all'
  | 'low'
  | 'moderate'
  | 'high'
  | 'not_calculated';

export type ScannerResultFilters = {
  validation: Exclude<ValidationResultFilter, 'all'>[];
  quality: Exclude<QualityResultFilter, 'all'>[];
  dcf: Exclude<DcfResultFilter, 'all'>[];
  risk: Exclude<RiskResultFilter, 'all'>[];
  minPrice: number | null;
  maxPrice: number | null;
};

export const defaultScannerResultFilters: ScannerResultFilters = {
  validation: [],
  quality: [],
  dcf: [],
  risk: [],
  minPrice: null,
  maxPrice: null
};

const validationResultFilters = [
  'validated',
  'needs_review',
  'rejected',
  'not_calculated'
] as const;
const qualityResultFilters = [
  'strong',
  'acceptable',
  'weak',
  'not_calculated'
] as const;
const dcfResultFilters = [
  'undervalued',
  'fairly_valued',
  'overvalued',
  'not_calculated'
] as const;
const riskResultFilters = [
  'low',
  'moderate',
  'high',
  'not_calculated'
] as const;

export type DisplayCandidate = {
  id: string;
  ticker: string;
  companyName: string;
  sector: string;
  strategy: string;
  score: string;
  currentPrice: string;
  priceAsOf: string;
  priceSource: string;
  relativeStrength: string;
  relativeVolume: string;
  atr: string;
  fiveDayRange: string;
  entryArea: string;
  stop: string;
  targetExit: string;
  holdTime: string;
  fairValue: string;
  marginOfSafety: string;
  validationLabel: string;
  validationScore: string;
  qualityLabel: string;
  qualityScore: string;
  dcfLabel: string;
  riskLabel: string;
  riskScore: string;
  fundamentalDataAsOf: string;
  freeCashFlow: string;
};

export type CandidateSortKey = keyof Omit<DisplayCandidate, 'id'>;
export type CandidateSortDirection = 'asc' | 'desc';
export type CandidateSort = {
  key: CandidateSortKey;
  direction: CandidateSortDirection;
};

export function candidateFromWatchlistRow(
  row: WatchlistRow,
  index: number,
  latestBarDate?: string | null
): DisplayCandidate {
  const ticker = stringValue(row.Ticker) || `ROW-${index + 1}`;
  const price = numericValue(row['Current Price']) ?? numericValue(row.Price);
  const stop = numericValue(row['Suggested Stop']) ?? numericValue(row['Stop 2ATR']);
  const target = numericValue(row['Target/Exit']) ?? numericValue(row['Suggested Exit']);

  return {
    id: ticker,
    ticker,
    companyName: stringValue(row['Company Name']),
    sector: stringValue(row.Sector) || 'n/a',
    strategy: stringValue(row['Triggered Strategies']) || 'n/a',
    score: formatCell(row['Composite Score']),
    currentPrice: formatCurrency(price),
    priceAsOf: stringValue(row['Price As Of']) || latestBarDate || 'n/a',
    priceSource: stringValue(row['Price Source']) || 'Cached Close',
    relativeStrength: formatPercentLike(row['Relative Strength']),
    relativeVolume: formatNumber(row['Relative Volume']),
    atr: formatCurrency(numericValue(row.ATR14)),
    fiveDayRange: formatInteger(row['5D Range']),
    entryArea: formatCurrency(numericValue(row['Entry Area']) ?? price),
    stop: formatCurrency(stop),
    targetExit: formatCurrency(target ?? targetFromPriceAndStop(price, stop)),
    holdTime:
      stringValue(row['Hold Time']) || stringValue(row['Suggested Hold Time']) || '5 trading days',
    fairValue: formatCurrency(numericValue(row['Fair Value'])),
    marginOfSafety: formatPercentLike(row['Margin of Safety']),
    validationLabel: validationLabel(row),
    validationScore: formatScore(row['Validation Score']),
    qualityLabel: summaryLabel(row['Quality Label']),
    qualityScore: formatScore(row['Quality Score']),
    dcfLabel: dcfSummaryLabel(row['Valuation Label']),
    riskLabel: summaryLabel(row['Risk Level']),
    riskScore: formatScore(row['Risk Score']),
    fundamentalDataAsOf: stringValue(row['SEC Data As Of']) || 'n/a',
    freeCashFlow: formatCompactCurrency(numericValue(row['Free Cash Flow']))
  };
}

export function sortCandidates(
  candidates: DisplayCandidate[],
  sort: CandidateSort
): DisplayCandidate[] {
  const direction = sort.direction === 'asc' ? 1 : -1;

  return [...candidates].sort((left, right) => {
    const leftValue = sortableValue(left[sort.key]);
    const rightValue = sortableValue(right[sort.key]);

    if (leftValue === undefined && rightValue === undefined) {
      return left.ticker.localeCompare(right.ticker);
    }

    if (leftValue === undefined) {
      return 1;
    }

    if (rightValue === undefined) {
      return -1;
    }

    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return (leftValue - rightValue) * direction || left.ticker.localeCompare(right.ticker);
    }

    return (
      String(leftValue).localeCompare(String(rightValue), undefined, {
        numeric: true,
        sensitivity: 'base'
      }) * direction || left.ticker.localeCompare(right.ticker)
    );
  });
}

export function rowMatchesDisplaySettings(
  row: WatchlistRow,
  settings: ScannerDisplaySettings
): boolean {
  const stopDistance = stopDistancePercent(row);
  const fiveDayRange = numericValue(row['5D Range']);

  return (
    (stopDistance === undefined || stopDistance >= settings.minStopDistancePercent) &&
    (fiveDayRange === undefined || fiveDayRange >= settings.minFiveDayRange)
  );
}

export function mergeWatchlistRows(
  rows: WatchlistRow[],
  refreshedRows: WatchlistRow[]
): WatchlistRow[] {
  const refreshedByTicker = new Map(
    refreshedRows.map((row) => [stringValue(row.Ticker).toUpperCase(), row])
  );

  return rows.map((row) => {
    const refreshed = refreshedByTicker.get(stringValue(row.Ticker).toUpperCase());
    return refreshed ? { ...row, ...refreshed } : row;
  });
}

export function stopDistancePercent(row: WatchlistRow): number | undefined {
  const price = numericValue(row['Entry Area']) ?? numericValue(row['Current Price']) ?? numericValue(row.Price);
  const stop = numericValue(row['Suggested Stop']) ?? numericValue(row['Stop 2ATR']);

  if (price === undefined || stop === undefined || stop >= price || price <= 0) {
    return undefined;
  }

  return ((price - stop) / price) * 100;
}

export function rowMatchesStrategy(row: WatchlistRow, strategy: string): boolean {
  if (strategy === 'all') {
    return true;
  }

  const columnName = `${titleCase(strategy)} Strategy`;
  const triggeredStrategies = stringValue(row['Triggered Strategies']).toLowerCase();

  return (
    stringValue(row[columnName]).toUpperCase() === 'YES' ||
    triggeredStrategies.includes(strategy.toLowerCase())
  );
}

export function normalizeScannerResultFilters(value: unknown): ScannerResultFilters {
  const filters = isRecord(value) ? value : {};
  return {
    validation: allowedValues(filters.validation, validationResultFilters),
    quality: allowedValues(filters.quality, qualityResultFilters),
    dcf: allowedValues(filters.dcf, dcfResultFilters),
    risk: allowedValues(filters.risk, riskResultFilters),
    minPrice: normalizedPriceBound(filters.minPrice),
    maxPrice: normalizedPriceBound(filters.maxPrice)
  };
}

export function rowMatchesScannerResultFilters(
  row: WatchlistRow,
  filters: ScannerResultFilters
): boolean {
  return (
    matchesResultFilter(validationCategory(row), filters.validation) &&
    matchesResultFilter(qualityCategory(row), filters.quality) &&
    matchesResultFilter(dcfCategory(row), filters.dcf) &&
    matchesResultFilter(riskCategory(row), filters.risk) &&
    matchesPriceRange(row, filters.minPrice, filters.maxPrice)
  );
}

function matchesPriceRange(
  row: WatchlistRow,
  minPrice: number | null,
  maxPrice: number | null
): boolean {
  if (minPrice === null && maxPrice === null) {
    return true;
  }

  const price = numericValue(row['Current Price']) ?? numericValue(row.Price);
  if (price === undefined) {
    return false;
  }

  return (minPrice === null || price >= minPrice) &&
    (maxPrice === null || price <= maxPrice);
}

function targetFromPriceAndStop(price?: number, stop?: number): number | undefined {
  if (price === undefined || stop === undefined || stop >= price) {
    return undefined;
  }

  return price + (price - stop) * 2;
}

function validationCategory(row: WatchlistRow): Exclude<ValidationResultFilter, 'all'> {
  const status = categoryValue(row['Validation Status']);
  if (status === 'validated' || status === 'needs_review' || status === 'rejected') {
    return status;
  }

  const label = categoryValue(row['Validation Label']);
  if (label === 'validated' || label === 'validated_candidate') return 'validated';
  if (label === 'needs_review') return 'needs_review';
  if (label === 'rejected') return 'rejected';
  return 'not_calculated';
}

function qualityCategory(row: WatchlistRow): Exclude<QualityResultFilter, 'all'> {
  const label = categoryValue(row['Quality Label']);
  return label === 'strong' || label === 'acceptable' || label === 'weak'
    ? label
    : 'not_calculated';
}

function dcfCategory(row: WatchlistRow): Exclude<DcfResultFilter, 'all'> {
  const label = categoryValue(row['Valuation Label']);
  return label === 'undervalued' || label === 'fairly_valued' || label === 'overvalued'
    ? label
    : 'not_calculated';
}

function riskCategory(row: WatchlistRow): Exclude<RiskResultFilter, 'all'> {
  const label = categoryValue(row['Risk Level']);
  if (label === 'medium') return 'moderate';
  return label === 'low' || label === 'moderate' || label === 'high'
    ? label
    : 'not_calculated';
}

function matchesResultFilter<T extends string>(category: T, filters: T[]): boolean {
  return filters.length === 0 || filters.includes(category);
}

function categoryValue(value: unknown): string {
  return stringValue(value)
    .trim()
    .toLowerCase()
    .replaceAll('-', '_')
    .replaceAll(/\s+/g, '_');
}

function allowedValues<T extends string>(
  value: unknown,
  allowed: readonly T[]
): T[] {
  const values = Array.isArray(value) ? value : typeof value === 'string' ? [value] : [];
  return [...new Set(values.filter((item): item is T =>
    typeof item === 'string' && allowed.includes(item as T)
  ))];
}

function normalizedPriceBound(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? value
    : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function formatCurrency(value?: number): string {
  if (value === undefined) {
    return 'n/a';
  }

  return `$${value.toFixed(2)}`;
}

function formatNumber(value: unknown): string {
  const numeric = numericValue(value);
  return numeric === undefined ? 'n/a' : numeric.toFixed(2);
}

function formatCompactCurrency(value?: number): string {
  if (value === undefined) {
    return 'n/a';
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(value);
}

function formatInteger(value: unknown): string {
  const numeric = numericValue(value);
  return numeric === undefined ? 'n/a' : String(Math.round(numeric));
}

function formatPercentLike(value: unknown): string {
  const numeric = numericValue(value);
  return numeric === undefined ? 'n/a' : `${numeric.toFixed(2)}%`;
}

function formatScore(value: unknown): string {
  const numeric = numericValue(value);
  if (numeric === undefined) {
    return 'n/a';
  }
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1);
}

function validationLabel(row: WatchlistRow): string {
  const explicit = summaryLabel(row['Validation Label']);
  if (explicit !== 'Not calculated') {
    return explicit;
  }
  return summaryLabel(row['Validation Status']);
}

function dcfSummaryLabel(value: unknown): string {
  const label = summaryLabel(value);
  if (label === 'Not calculated' || label.toLowerCase().includes('dcf')) {
    return label;
  }
  return `${label} by DCF`;
}

function summaryLabel(value: unknown): string {
  const normalized = stringValue(value).trim().replaceAll('_', ' ');
  if (
    !normalized ||
    ['unknown', 'not calculated', 'n/a', 'none'].includes(normalized.toLowerCase())
  ) {
    return 'Not calculated';
  }
  return normalized
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

function formatCell(value: unknown): string {
  const text = stringValue(value);
  return text || 'n/a';
}

function sortableValue(value: string): number | string | undefined {
  if (!value || value === 'n/a') {
    return undefined;
  }

  const numeric = numericValue(value);

  if (numeric !== undefined) {
    return numeric;
  }

  const timestamp = Date.parse(value);

  if (Number.isFinite(timestamp)) {
    return timestamp;
  }

  return value;
}

function numericValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value !== 'string') {
    return undefined;
  }

  const parsed = Number(value.replace(/[$,%"]/g, '').replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : undefined;
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }

  return String(value);
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}
