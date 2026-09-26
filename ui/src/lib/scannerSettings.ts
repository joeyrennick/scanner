import { useSavedSetting } from '../features/business/BusinessRecordsProvider';
import { useCallback, useMemo } from 'react';

export type ScannerDisplaySettings = {
  minStopDistancePercent: number;
  minFiveDayRange: number;
};

export const defaultScannerDisplaySettings: ScannerDisplaySettings = {
  minStopDistancePercent: 1,
  minFiveDayRange: 10
};

const storageKey = 'swing-scanner.display-settings';

export function useScannerDisplaySettings() {
  const [settings, setSettings] = useSavedSetting(storageKey, defaultScannerDisplaySettings);

  const updateSettings = useCallback((next: ScannerDisplaySettings) => {
    const normalized = normalizeScannerDisplaySettings(next);
    setSettings(normalized);
  }, [setSettings]);

  const normalized = useMemo(() => normalizeScannerDisplaySettings(settings), [settings]);
  return [normalized, updateSettings] as const;
}

function normalizeScannerDisplaySettings(value: unknown): ScannerDisplaySettings {
  const candidate = value as Partial<ScannerDisplaySettings>;

  return {
    minStopDistancePercent: nonNegativeNumber(
      candidate.minStopDistancePercent,
      defaultScannerDisplaySettings.minStopDistancePercent
    ),
    minFiveDayRange: nonNegativeNumber(
      candidate.minFiveDayRange,
      defaultScannerDisplaySettings.minFiveDayRange
    )
  };
}

function nonNegativeNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : fallback;
}
