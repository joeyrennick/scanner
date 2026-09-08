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
}

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = options.baseUrl ?? '';
  const bearerToken = options.bearerToken;
  const fetcher = options.fetcher ?? fetch;

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(bearerToken ? { Authorization: `Bearer ${bearerToken}` } : {}),
        ...(init?.headers ?? {})
      }
    });

    if (!response.ok) {
      let message = response.statusText;

      try {
        const body = await response.json();
        message = body.detail ?? message;
      } catch {
        // Keep HTTP status text when response body is not JSON.
      }

      throw new ApiError(response.status, message);
    }

    return response.json() as Promise<T>;
  }

  return { request };
}

export const apiClient = createApiClient();
