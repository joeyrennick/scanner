import { useCallback, useMemo, useRef, useState } from 'react';
import { useBusinessCollection, useBusinessStore } from './BusinessRecordsProvider';
import type { CandidateLevels, Update } from '../../lib/businessRecords';

export type CandidateTradeEdits = Omit<CandidateLevels, 'id'> & {
  chartHeight: number; chartZoom?: number; chartPanBars?: number; chartPricePan?: number;
  maximizedChartHeight?: number; maximizedChartWidth?: number; previousChartHeight?: number;
};
type ChartPreferences = Partial<Omit<CandidateTradeEdits, 'entry' | 'stop' | 'target'>>;
const preferenceKey = 'swing-scanner.candidates.chart-preferences.v1';
const chartFields = ['chartHeight', 'chartZoom', 'chartPanBars', 'chartPricePan', 'maximizedChartHeight', 'maximizedChartWidth', 'previousChartHeight'] as const;

export function chartPreferences(value: unknown): Record<string, ChartPreferences> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value).map(([id, row]) => [id,
    Object.fromEntries(chartFields.flatMap((field) => {
      const number = row?.[field];
      return typeof number === 'number' && Number.isFinite(number) ? [[field, number]] : [];
    }))
  ]));
}

function loadPreferences() {
  try {
    return chartPreferences(JSON.parse(localStorage.getItem(preferenceKey)
      ?? localStorage.getItem('swing-scanner.candidates.chart-state') ?? '{}'));
  } catch { return {}; }
}

function combine(records: CandidateLevels[], preferences: Record<string, ChartPreferences>) {
  // Legacy trade levels are intentionally NOT a fallback for database records.
  return Object.fromEntries(records.map(({ id, ...levels }) => [id, {
    chartHeight: 300, ...preferences[id], ...levels
  }])) as Record<string, CandidateTradeEdits>;
}

export function useCandidateEdits() {
  const store = useBusinessStore();
  const [records, update] = useBusinessCollection('candidateEdits');
  const [preferences, setPreferences] = useState(loadPreferences);
  const preferencesRef = useRef(preferences);
  const edits = useMemo(() => combine(records, preferences), [records, preferences]);
  const setEdits = useCallback((next: Update<Record<string, CandidateTradeEdits>>) => {
    const current = combine(store.getSnapshot().data.candidateEdits, preferencesRef.current);
    const updated = typeof next === 'function' ? next(current) : next;
    update(Object.entries(updated).map(([id, row]) => ({ id, entry: row.entry, stop: row.stop, target: row.target })));
    const chart = chartPreferences(updated);
    preferencesRef.current = chart;
    setPreferences(chart);
    localStorage.setItem(preferenceKey, JSON.stringify(chart));
  }, [store, update]);
  return [edits, setEdits] as const;
}
