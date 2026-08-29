import { describe, expect, it } from 'vitest';
import { pinnedTrailingPosition } from './chartViewport';

describe('pinnedTrailingPosition', () => {
  it('keeps an axis on the visible trailing edge while scrolling', () => {
    expect(
      pinnedTrailingPosition({
        scrollOffset: 0,
        viewportLength: 1000,
        reservedLength: 76,
        chartLength: 2000
      })
    ).toBe(924);
    expect(
      pinnedTrailingPosition({
        scrollOffset: 500,
        viewportLength: 1000,
        reservedLength: 76,
        chartLength: 2000
      })
    ).toBe(1424);
  });

  it('does not move an axis past the end of the chart', () => {
    expect(
      pinnedTrailingPosition({
        scrollOffset: 1200,
        viewportLength: 1000,
        reservedLength: 76,
        chartLength: 2000
      })
    ).toBe(1924);
  });
});
