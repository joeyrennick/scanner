export const defaultScannerColumnWidths = {
  select: 44,
  ticker: 155,
  strategy: 130,
  score: 90,
  currentPrice: 125,
  fairValue: 110,
  dcfUpside: 110,
  validation: 150,
  quality: 150,
  dcfEstimate: 165,
  risk: 120,
  relativeStrength: 80,
  relativeVolume: 80,
  atr: 90,
  fiveDayRange: 95,
  entry: 100,
  stop: 100,
  target: 110
} as const;

export type ScannerColumnKey = keyof typeof defaultScannerColumnWidths;
export type ScannerColumnWidths = Record<ScannerColumnKey, number>;
export type ScannerColumnVisibility = Record<ScannerColumnKey, boolean>;

export const defaultScannerColumnVisibility = Object.keys(
  defaultScannerColumnWidths
).reduce<ScannerColumnVisibility>(
  (visibility, key) => {
    visibility[key as ScannerColumnKey] = true;
    return visibility;
  },
  {} as ScannerColumnVisibility
);

export const minimumScannerColumnWidth = 64;
export const maximumScannerColumnWidth = 480;

const scannerColumnKeys = Object.keys(defaultScannerColumnWidths) as ScannerColumnKey[];

export function normalizeScannerColumnWidths(value: unknown): ScannerColumnWidths {
  const stored = isRecord(value) ? value : {};
  return scannerColumnKeys.reduce<ScannerColumnWidths>(
    (widths, key) => {
      const candidate = stored[key];
      widths[key] = validWidth(candidate)
        ? clampScannerColumnWidth(candidate)
        : defaultScannerColumnWidths[key];
      return widths;
    },
    { ...defaultScannerColumnWidths }
  );
}

export function normalizeScannerColumnVisibility(value: unknown): ScannerColumnVisibility {
  const stored = isRecord(value) ? value : {};
  return scannerColumnKeys.reduce<ScannerColumnVisibility>(
    (visibility, key) => {
      visibility[key] = key === 'select' || key === 'ticker'
        ? true
        : typeof stored[key] === 'boolean'
          ? stored[key]
          : defaultScannerColumnVisibility[key];
      return visibility;
    },
    { ...defaultScannerColumnVisibility }
  );
}

export function clampScannerColumnWidth(value: number): number {
  return Math.round(
    Math.min(Math.max(value, minimumScannerColumnWidth), maximumScannerColumnWidth)
  );
}

function validWidth(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
