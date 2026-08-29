import { describe, expect, it } from 'vitest';
import {
  chartFrequencyOption,
  chartFrequencyOptions,
  defaultChartFrequency
} from './chartFrequency';

describe('chart frequency options', () => {
  it('uses the requested default intervals for every chart range', () => {
    expect(
      Object.fromEntries(
        chartFrequencyOptions.map((option) => [option.value, option.interval])
      )
    ).toEqual({
      '1d': '5m',
      '1w': '15m',
      '1mo': '1d',
      ytd: '1d',
      '1y': '1d',
      '5y': '1d'
    });
  });

  it('defaults to the existing one-year display', () => {
    expect(defaultChartFrequency).toBe('1y');
    expect(chartFrequencyOption(defaultChartFrequency).period).toBe('1y');
  });
});
