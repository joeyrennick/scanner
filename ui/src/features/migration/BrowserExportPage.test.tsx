import { webcrypto } from 'node:crypto';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BrowserExportPage } from './BrowserExportPage';
import { isMigrationPaused } from '../../lib/browserExport';

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('crypto', webcrypto);
  URL.createObjectURL = vi.fn(() => 'blob:fixture-export');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('requires confirmation, exports from the current browser, and keeps the pause after download', async () => {
  render(<BrowserExportPage />);
  const button = screen.getByRole('button', { name: 'Pause editing and export records' });
  expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(button);
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('0 Planned Trades'));
  expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledOnce();
  expect(isMigrationPaused()).toBe(true);
  expect(screen.getByRole('button', { name: 'Resume with imported database' })).toBeDisabled();
});

it('leaves malformed records intact and reports the problem without downloading', async () => {
  localStorage.setItem('planned-trades', '{broken');
  render(<BrowserExportPage />);
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: 'Pause editing and export records' }));
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('invalid JSON'));
  expect(localStorage.getItem('planned-trades')).toBe('{broken');
  expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
});
