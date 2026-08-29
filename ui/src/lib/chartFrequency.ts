export type ChartFrequency = '1d' | '1w' | '1mo' | 'ytd' | '1y' | '5y';

export type ChartFrequencyOption = {
  value: ChartFrequency;
  label: string;
  period: string;
  interval: '5m' | '15m' | '1d';
  intervalLabel: string;
  rangeLabel: string;
};

export const chartFrequencyOptions: ChartFrequencyOption[] = [
  {
    value: '1d',
    label: '1D',
    period: '1d',
    interval: '5m',
    intervalLabel: '5 min',
    rangeLabel: '1 day'
  },
  {
    value: '1w',
    label: '1W',
    period: '5d',
    interval: '15m',
    intervalLabel: '15 min',
    rangeLabel: '1 week'
  },
  {
    value: '1mo',
    label: '1M',
    period: '1mo',
    interval: '1d',
    intervalLabel: '1 Day',
    rangeLabel: '1 month'
  },
  {
    value: 'ytd',
    label: 'YTD',
    period: 'ytd',
    interval: '1d',
    intervalLabel: '1 Day',
    rangeLabel: 'year to date'
  },
  {
    value: '1y',
    label: '1Y',
    period: '1y',
    interval: '1d',
    intervalLabel: '1 Day',
    rangeLabel: '1 year'
  },
  {
    value: '5y',
    label: '5Y',
    period: '5y',
    interval: '1d',
    intervalLabel: '1 Day',
    rangeLabel: '5 years'
  }
];

export const defaultChartFrequency: ChartFrequency = '1y';

export function chartFrequencyOption(value: ChartFrequency): ChartFrequencyOption {
  return (
    chartFrequencyOptions.find((option) => option.value === value) ??
    chartFrequencyOptions.find((option) => option.value === defaultChartFrequency)!
  );
}
