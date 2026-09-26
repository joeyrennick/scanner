import { isMigrationPaused } from '../lib/browserExport';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  bearerToken?: string;
  fetcher?: typeof fetch;
  pauseDuringBrowserBackup?: boolean;
}

export interface ApiFile {
  blob: Blob;
  name: string;
  mediaType: string;
}

export type ApiClient = ReturnType<typeof createApiClient>;

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = options.baseUrl ?? '';
  const bearerToken = options.bearerToken;
  const fetcher = options.fetcher ?? fetch;

  async function responseFor(path: string, init?: RequestInit): Promise<Response> {
    if (!path.startsWith('/api/') || path.includes('#')) {
      throw new ApiError(400, 'An application API path is required.');
    }
    if (options.pauseDuringBrowserBackup && typeof window !== 'undefined' && isMigrationPaused()) {
      throw new ApiError(503, 'Browser editing is paused for backup. Resume from the browser export page.');
    }
    const headers = new Headers(init?.headers);
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    if (bearerToken) headers.set('Authorization', `Bearer ${bearerToken}`);
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      // Never follow a file or API redirect while carrying a launch credential.
      redirect: 'error',
      headers: Object.fromEntries(headers.entries())
    });

    if (!response.ok) {
      let message = response.statusText;

      try {
        const body = await response.json();
        message = typeof body.detail === 'string' ? body.detail : message;
      } catch {
        // Keep HTTP status text when response body is not JSON.
      }

      throw new ApiError(response.status, message);
    }

    return response;
  }

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    return (await responseFor(path, init)).json() as Promise<T>;
  }

  async function requestFile(path: string): Promise<ApiFile> {
    const response = await responseFor(path);
    const disposition = response.headers.get('Content-Disposition') ?? '';
    const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition)?.[1];
    let name = /filename="([^"]+)"/i.exec(disposition)?.[1] ?? 'scanner-report';
    if (encoded) {
      try { name = decodeURIComponent(encoded); } catch { /* Keep safe fallback. */ }
    }
    name = name.replace(/[\\/\u0000-\u001f\u007f]/g, '_').slice(0, 255);
    const blob = await response.blob();
    return { blob, name, mediaType: (response.headers.get('Content-Type') ?? '').split(';')[0].toLowerCase() };
  }

  return { request, requestFile };
}

export const apiClient = createApiClient({ pauseDuringBrowserBackup: true });
