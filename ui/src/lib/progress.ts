import type { JobProgress, JobResponse } from '../api/types';

export function progressPercent(progress: JobProgress | null | undefined): number {
  if (!progress?.symbols_total || progress.symbols_total <= 0) {
    return 0;
  }

  const checked = progress.symbols_checked ?? 0;
  return Math.min(100, Math.max(0, Math.round((checked / progress.symbols_total) * 100)));
}

export function isJobActive(job: JobResponse | null | undefined): boolean {
  return job?.status === 'queued' || job?.status === 'running';
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) {
    return 'n/a';
  }

  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) {
    return 'n/a';
  }

  return new Intl.NumberFormat().format(value);
}
