import type { WatchlistRow } from '../api/types';

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
    entryArea: formatCurrency(price),
    stop: formatCurrency(stop),
    targetExit: formatCurrency(targetFromPriceAndStop(price, stop)),
    holdTime: stringValue(row['Hold Time']) || '5 trading days'
  };
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
