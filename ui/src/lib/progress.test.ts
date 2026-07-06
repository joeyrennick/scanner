import { describe, expect, it } from 'vitest';
import { formatDuration, formatNumber, progressPercent } from './progress';

describe('progress helpers', () => {
  it('calculates bounded progress percentages', () => {
    expect(progressPercent({ symbols_total: 200, symbols_checked: 50 } as never)).toBe(25);
    expect(progressPercent({ symbols_total: 200, symbols_checked: 250 } as never)).toBe(100);
    expect(progressPercent({ symbols_total: 0, symbols_checked: 10 } as never)).toBe(0);
  });

  it('formats durations for job status displays', () => {
    expect(formatDuration(null)).toBe('n/a');
    expect(formatDuration(42)).toBe('42s');
    expect(formatDuration(125)).toBe('2m 5s');
  });

  it('formats nullable numbers', () => {
    expect(formatNumber(null)).toBe('n/a');
    expect(formatNumber(2681)).toBe('2,681');
  });
});
