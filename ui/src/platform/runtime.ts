import { apiClient, createApiClient, type ApiClient } from '../api/client';
import { browserFilePresenter, createFileActions, type FileActions, type FilePresenter } from './files';

export interface RuntimeInfo {
  schema_version: 1;
  application: 'Swing Scanner';
  mode: 'browser' | 'desktop-proof-of-concept';
  api_versions: number[];
  compatibility_api: '/api' | null;
  capabilities: {
    scanner_workflows: boolean; business_records: boolean; report_files: boolean;
    job_output_files: boolean; legacy_credential_controls: boolean;
    native_keychain: boolean; native_file_dialogs: boolean; desktop_lifecycle: boolean;
  };
  paths: { data: string; cache: string; reports: string; logs: string; exports: string };
}

export interface PlatformRuntime {
  kind: 'browser' | 'desktop';
  api: ApiClient;
  files: FileActions;
  readInfo(): Promise<RuntimeInfo>;
}

export function createRuntime(kind: PlatformRuntime['kind'], api: ApiClient, presenter: FilePresenter): PlatformRuntime {
  return { kind, api, files: createFileActions(api, presenter), async readInfo() {
    const info = await api.request<RuntimeInfo>('/api/v1/runtime');
    if (info.schema_version !== 1 || info.application !== 'Swing Scanner'
        || !Array.isArray(info.api_versions) || !info.api_versions.includes(1)
        || !['browser', 'desktop-proof-of-concept'].includes(info.mode)
        || !['/api', null].includes(info.compatibility_api)
        || !info.capabilities || !info.paths
        || ['scanner_workflows', 'business_records', 'report_files', 'job_output_files',
          'legacy_credential_controls', 'native_keychain', 'native_file_dialogs', 'desktop_lifecycle']
          .some((key) => typeof info.capabilities[key as keyof RuntimeInfo['capabilities']] !== 'boolean')
        || ['data', 'cache', 'reports', 'logs', 'exports'].some((key) =>
          typeof info.paths[key as keyof RuntimeInfo['paths']] !== 'string')) {
      throw new Error('This backend does not support the Scanner runtime contract.');
    }
    return info;
  } };
}

export const browserRuntime = createRuntime('browser', apiClient, browserFilePresenter);

export interface DesktopRuntimeConfig { baseUrl: string; bearerToken: string; mode: string }
export interface DesktopHost {
  configure(restart: boolean): Promise<DesktopRuntimeConfig>;
}

export async function connectDesktop(host: DesktopHost, restart = false, fetcher?: typeof fetch) {
  const config = await host.configure(restart);
  const endpoint = new URL(config.baseUrl);
  if (endpoint.protocol !== 'http:' || endpoint.hostname !== '127.0.0.1'
      || !endpoint.port || endpoint.username || endpoint.password
      || endpoint.pathname !== '/' || endpoint.search || endpoint.hash
      || config.bearerToken.length < 32) {
    throw new Error('The desktop host returned an invalid private connection.');
  }
  const api = createApiClient({ baseUrl: endpoint.origin, bearerToken: config.bearerToken, fetcher });
  // The Phase 0 host does not yet offer native file dialogs or the scanner routes.
  // Do not silently use a browser download fallback in a native window.
  const unavailable: FilePresenter = {
    save() { throw new Error('Native file saving is not available in the packaging proof.'); },
    preparePreview() { throw new Error('Native preview is not available in the packaging proof.'); }
  };
  return { config: { baseUrl: endpoint.origin, mode: config.mode }, runtime: createRuntime('desktop', api, unavailable) };
}
