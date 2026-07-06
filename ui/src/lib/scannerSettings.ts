import { useEffect, useState } from 'react';

export type ScannerDisplaySettings = {
  minStopDistancePercent: number;
  minFiveDayRange: number;
};

export const defaultScannerDisplaySettings: ScannerDisplaySettings = {
  minStopDistancePercent: 1,
  minFiveDayRange: 10
};

const storageKey = 'swing-scanner.display-settings';

export function readScannerDisplaySettings(): ScannerDisplaySettings {
  if (typeof window === 'undefined') {
    return defaultScannerDisplaySettings;
  }

  const stored = window.localStorage.getItem(storageKey);

  if (!stored) {
    return defaultScannerDisplaySettings;
  }

  try {
    return normalizeScannerDisplaySettings(JSON.parse(stored));
  } catch {
    return defaultScannerDisplaySettings;
  }
}

export function saveScannerDisplaySettings(settings: ScannerDisplaySettings) {
  window.localStorage.setItem(
    storageKey,
    JSON.stringify(normalizeScannerDisplaySettings(settings))
  );
}

export function useScannerDisplaySettings() {
  const [settings, setSettings] = useState(readScannerDisplaySettings);

  useEffect(() => {
    const listener = () => setSettings(readScannerDisplaySettings());
    window.addEventListener('storage', listener);
    return () => window.removeEventListener('storage', listener);
  }, []);

  function updateSettings(next: ScannerDisplaySettings) {
    const normalized = normalizeScannerDisplaySettings(next);
    saveScannerDisplaySettings(normalized);
    setSettings(normalized);
  }

  return [settings, updateSettings] as const;
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
