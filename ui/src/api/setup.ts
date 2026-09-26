import type { ApiClient } from './client';

export interface SECIdentity { application_name: string; contact_email: string }
export interface SetupStatus {
  configuration: { schema_version: 1; revision: number; sec_identity: SECIdentity | null };
  sec_configured: boolean;
  sec_source: 'saved' | 'environment' | 'missing';
  sec_user_agent: string;
  sec_error: string | null;
}

function readStatus(value: unknown): SetupStatus {
  const status = value as SetupStatus | undefined;
  const config = status?.configuration;
  const identity = config?.sec_identity;
  if (!config || config.schema_version !== 1 || !Number.isSafeInteger(config.revision) || config.revision < 0 ||
      !(identity === null || (identity && typeof identity.application_name === 'string' && typeof identity.contact_email === 'string')) ||
      typeof status?.sec_configured !== 'boolean' || !['saved', 'environment', 'missing'].includes(status.sec_source) ||
      typeof status.sec_user_agent !== 'string' || !(status.sec_error === null || typeof status.sec_error === 'string')) {
    throw new Error('Unsupported application setup response. No settings were loaded.');
  }
  return status;
}

export async function loadSetup(api: ApiClient) {
  return readStatus(await api.request<unknown>('/api/v1/setup'));
}

export async function saveSetup(api: ApiClient, secIdentity: SECIdentity, expectedRevision: number) {
  return readStatus(await api.request<unknown>('/api/v1/setup', {
    method: 'PUT', body: JSON.stringify({ sec_identity: secIdentity, expected_revision: expectedRevision })
  }));
}
