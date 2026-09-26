import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { createApiClient } from '../../api/client';
import { loadSetup, type SetupStatus } from '../../api/setup';
import { createRuntime } from '../../platform/runtime';
import { PlatformProvider } from '../../platform/PlatformProvider';
import { SECContactSetup } from './SECContactSetup';

afterEach(cleanup);
const missing: SetupStatus = {
  configuration: { schema_version: 1, revision: 0, sec_identity: null },
  sec_configured: false, sec_source: 'missing', sec_user_agent: '', sec_error: null
};
const saved: SetupStatus = {
  configuration: { schema_version: 1, revision: 1, sec_identity: { application_name: 'Swing Scanner', contact_email: 'user@example.com' } },
  sec_configured: true, sec_source: 'saved', sec_user_agent: 'Swing Scanner user@example.com', sec_error: null
};

function mount(fetcher: typeof fetch) {
  const runtime = createRuntime('browser', createApiClient({ fetcher }), { save: vi.fn(), preparePreview: vi.fn() });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<PlatformProvider runtime={runtime}><QueryClientProvider client={queryClient}><SECContactSetup /></QueryClientProvider></PlatformProvider>);
}
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

it('loads without saving, explains contact use, and leaves the email for the user to choose', async () => {
  const fetcher = vi.fn(async () => response(missing));
  mount(fetcher);
  await screen.findByLabelText('Contact email');
  expect(screen.getByLabelText('Contact email')).toHaveValue('');
  expect(screen.getByLabelText('Application or organization name')).toHaveValue('Swing Scanner');
  expect(screen.getByText(/This is not a password/)).toHaveTextContent('sends them to the SEC');
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/setup');
  expect(screen.getByRole('button', { name: 'Save SEC contact' })).toBeDisabled();
});

it('saves explicitly through the injected client, with revision and no browser storage changes', async () => {
  const fetcher = vi.fn(async (_path, init) => response(init?.method === 'PUT' ? saved : missing));
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  try {
    mount(fetcher);
    fireEvent.change(await screen.findByLabelText('Contact email'), { target: { value: 'user@example.com' } });
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Save SEC contact' }));
    await screen.findByText(/Contact saved on this Mac/);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ expected_revision: 0, sec_identity: saved.configuration.sec_identity });
    expect(fetcher.mock.calls[1][0]).toBe('/api/v1/setup');
    expect(storage).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Save SEC contact' })).toBeDisabled();
  } finally { storage.mockRestore(); }
});

it.each(['conflict', 'network'])('retains the draft after %s and requires an explicit reload before retry', async (failure) => {
  let committed = false;
  const fetcher = vi.fn(async (_path, init) => {
    if (init?.method === 'PUT') {
      committed = true;
      if (failure === 'network') throw new Error('Connection interrupted');
      return response({ detail: 'Setup changed in another window' }, 409);
    }
    return response(committed ? saved : missing);
  });
  mount(fetcher);
  fireEvent.change(await screen.findByLabelText('Contact email'), { target: { value: 'draft@example.com' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save SEC contact' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Contact email')).toHaveValue('draft@example.com');
  expect(screen.getByRole('button', { name: 'Save SEC contact' })).toBeDisabled();
  await act(async () => {});
  expect(fetcher).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft and reload saved setup' }));
  await waitFor(() => expect(screen.getByLabelText('Contact email')).toHaveValue('user@example.com'));
  expect(fetcher).toHaveBeenCalledTimes(3);
});

it('shows load failure without enabling a blank replacement form', async () => {
  mount(async () => response({ detail: 'Configuration is unsupported; preserve it' }, 409));
  await screen.findByRole('alert');
  expect(screen.queryByLabelText('Contact email')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Retry loading setup' })).toBeEnabled();
});

it('discloses an environment override and does not copy its identity into the saved form', async () => {
  mount(async () => response({ ...missing, sec_source: 'environment', sec_configured: true, sec_user_agent: 'Launcher launcher@example.com' }));
  await screen.findByRole('note');
  expect(screen.getByLabelText('Contact email')).toHaveValue('');
  expect(screen.getByRole('note')).toHaveTextContent('overrides saved contact details');
  expect(screen.getByText('Launcher launcher@example.com')).toBeInTheDocument();
});

it('does not replace a draft when the window regains focus', async () => {
  const fetcher = vi.fn(async () => response(missing));
  mount(fetcher);
  fireEvent.change(await screen.findByLabelText('Contact email'), { target: { value: 'draft@example.com' } });
  fireEvent.focus(window);
  await act(async () => {});
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText('Contact email')).toHaveValue('draft@example.com');
});

it.each([null, {}, { ...missing, configuration: { ...missing.configuration, schema_version: 2 } },
  { ...missing, configuration: { ...missing.configuration, revision: true } },
  { ...missing, sec_source: 'guess' }])('rejects unsupported setup contracts', async (value) => {
  await expect(loadSetup(createApiClient({ fetcher: async () => response(value) }))).rejects.toThrow('Unsupported application setup');
});
