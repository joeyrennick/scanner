import { describe, expect, it } from 'vitest';
import {
  defaultScannerColumnVisibility,
  defaultScannerColumnWidths,
  maximumScannerColumnWidth,
  minimumScannerColumnWidth,
  normalizeScannerColumnVisibility,
  normalizeScannerColumnWidths
} from './scannerColumns';

describe('scanner column widths', () => {
  it('restores saved widths and fills missing columns from defaults', () => {
    expect(
      normalizeScannerColumnWidths({
        ticker: 220,
        validation: 190
      })
    ).toEqual({
      ...defaultScannerColumnWidths,
      ticker: 220,
      validation: 190
    });
  });

  it('rejects invalid widths and clamps extreme saved values', () => {
    const widths = normalizeScannerColumnWidths({
      ticker: Number.NaN,
      strategy: 'wide',
      validation: 1,
      risk: 10_000
    });

    expect(widths.ticker).toBe(defaultScannerColumnWidths.ticker);
    expect(widths.strategy).toBe(defaultScannerColumnWidths.strategy);
    expect(widths.validation).toBe(minimumScannerColumnWidth);
    expect(widths.risk).toBe(maximumScannerColumnWidth);
  });

  it('restores column visibility and defaults missing or invalid entries', () => {
    expect(
      normalizeScannerColumnVisibility({
        validation: false,
        risk: false,
        quality: 'hidden'
      })
    ).toEqual({
      ...defaultScannerColumnVisibility,
      validation: false,
      risk: false
    });
  });

  it('keeps row selection and ticker identity columns visible', () => {
    const visibility = normalizeScannerColumnVisibility({
      select: false,
      ticker: false,
      strategy: false
    });

    expect(visibility.select).toBe(true);
    expect(visibility.ticker).toBe(true);
    expect(visibility.strategy).toBe(false);
  });
});
