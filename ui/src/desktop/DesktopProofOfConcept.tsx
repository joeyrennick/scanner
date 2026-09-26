import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, LoaderCircle, RefreshCw } from 'lucide-react';
import { ApiError } from '../api/client';
import { connectDesktop, type RuntimeInfo } from '../platform/runtime';
import { tauriHost } from '../platform/tauriHost';

interface DesktopHealth {
  status: string;
  application: string;
  mode: string;
  sidecar_version: string;
  python_version: string;
  architecture: string;
  process_id: number;
  dependencies: Record<string, string>;
}

type StartupState =
  | { status: 'starting' }
  | { status: 'connected'; config: { baseUrl: string; mode: string }; health: DesktopHealth; info: RuntimeInfo }
  | { status: 'failed'; message: string };

const readinessAttempts = 75;
const readinessDelayMs = 200;

export function DesktopProofOfConcept() {
  const [startup, setStartup] = useState<StartupState>({ status: 'starting' });
  const [attempt, setAttempt] = useState(0);

  const connect = useCallback(async () => {
    setStartup({ status: 'starting' });

    try {
      const { config, runtime } = await connectDesktop(tauriHost, attempt !== 0);

      for (let readinessAttempt = 0; readinessAttempt < readinessAttempts; readinessAttempt += 1) {
        try {
          const health = await runtime.api.request<DesktopHealth>('/api/desktop/health');
          const info = await runtime.readInfo();
          setStartup({ status: 'connected', config, health, info });
          return;
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) {
            throw error;
          }
          await delay(readinessDelayMs);
        }
      }

      throw new Error('The packaged backend did not become ready within 15 seconds.');
    } catch (error) {
      setStartup({ status: 'failed', message: errorMessage(error) });
    }
  }, [attempt]);

  useEffect(() => {
    void connect();
  }, [connect]);

  return (
    <main className="desktop-poc-shell">
      <section className="desktop-poc-card" aria-live="polite">
        <div className="desktop-poc-kicker">Phase 0 · Mac packaging proof of concept</div>
        <h1>Swing Scanner</h1>

        {startup.status === 'starting' ? (
          <div className="desktop-poc-status">
            <LoaderCircle className="desktop-poc-spinner" aria-hidden="true" />
            <div>
              <h2>Starting the packaged backend</h2>
              <p>Selecting a private port, launching FastAPI, and checking native dependencies.</p>
            </div>
          </div>
        ) : null}

        {startup.status === 'failed' ? (
          <div className="desktop-poc-status desktop-poc-status-error">
            <AlertTriangle aria-hidden="true" />
            <div>
              <h2>Backend startup failed</h2>
              <p>{startup.message}</p>
              <button className="primary-button" type="button" onClick={() => setAttempt((value) => value + 1)}>
                <RefreshCw aria-hidden="true" />
                Retry backend
              </button>
            </div>
          </div>
        ) : null}

        {startup.status === 'connected' ? (
          <>
            <div className="desktop-poc-status desktop-poc-status-success">
              <CheckCircle2 aria-hidden="true" />
              <div>
                <h2>Packaged backend connected</h2>
                <p>The native window completed an authenticated request to the Python sidecar.</p>
              </div>
            </div>

            <dl className="desktop-poc-details">
              <div>
                <dt>Mode</dt>
                <dd>{startup.health.mode}</dd>
              </div>
              <div>
                <dt>Private endpoint</dt>
                <dd>{startup.config.baseUrl}</dd>
              </div>
              <div>
                <dt>Backend process</dt>
                <dd>{startup.health.process_id}</dd>
              </div>
              <div>
                <dt>Runtime</dt>
                <dd>
                  Python {startup.health.python_version} · {startup.health.architecture}
                </dd>
              </div>
            </dl>

            <div className="desktop-poc-dependencies">
              <h2>Dependency smoke check</h2>
              <ul>
                {Object.entries(startup.health.dependencies).map(([name, version]) => (
                  <li key={name}>
                    <span>{name}</span>
                    <strong>{version}</strong>
                  </li>
                ))}
              </ul>
            </div>

            <p className="desktop-poc-footnote">
              Runtime API v{startup.info.schema_version} connected. This packaging proof does not yet expose the full scanner workflow or native file dialogs.
            </p>
          </>
        ) : null}
      </section>
    </main>
  );
}

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
