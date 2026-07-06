import type { WatchlistRow } from '../api/types';
import type { ScannerDisplaySettings } from './scannerSettings';

export type DisplayCandidate = {
  id: string;
  ticker: string;
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
      stringValue(row['Hold Time']) || stringValue(row['Suggested Hold Time']) || '5 trading days'
  };
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

function targetFromPriceAndStop(price?: number, stop?: number): number | undefined {
  if (price === undefined || stop === undefined || stop >= price) {
    return undefined;
  }

  return price + (price - stop) * 2;
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

function formatInteger(value: unknown): string {
  const numeric = numericValue(value);
  return numeric === undefined ? 'n/a' : String(Math.round(numeric));
}

function formatPercentLike(value: unknown): string {
  const numeric = numericValue(value);
  return numeric === undefined ? 'n/a' : `${numeric.toFixed(2)}%`;
}

function formatCell(value: unknown): string {
  const text = stringValue(value);
  return text || 'n/a';
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
